"""
Handler for POST /users/update-user/{username}

Endpoint:   POST /users/update-user/{username}
Response:   200 OK         → UserResponse
            400 Bad Request → validation errors (no fields, invalid values)
            404 Not Found   → user does not exist
            409 Conflict    → new email already in use by another user

Supports partial updates — only fields provided in the request body are updated.
Fields not included in the request are left unchanged in the database.

Update logic:
  - If `name` is provided   → update name after trimming whitespace
  - If `email` is provided  → check uniqueness across other users, then update
  - If `password` is provided → hash with bcrypt, then update (plain text discarded)
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest
from app.utils.logger import logger, mask_sensitive
from app.utils.security import hash_password
from app.utils.validators import EMAIL_REGEX

router = APIRouter()


def _validate_payload(body: UserUpdateRequest) -> None:
    """
    Validate the partial update request body.

    Rules:
      - At least one of (name, email, password) must be present
      - If name     is provided: non-empty after strip, minimum 3 characters
      - If email    is provided: non-empty after strip, valid EMAIL_REGEX format
      - If password is provided: non-empty after strip, minimum 8 characters

    Collects ALL errors before raising (fail-all strategy) so the client
    receives a complete list in a single 400 response.

    Args:
        body (UserUpdateRequest): The parsed request payload from FastAPI.

    Raises:
        HTTPException (400): If no fields provided, or any field fails validation.
    """
    # ── Guard: at least one field must be present ─────────────────────────────
    if body.name is None and body.email is None and body.password is None:
        logger.warning("Update request rejected — no fields provided in request body")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": ["At least one of name, email, or password must be provided"]},
        )

    errors = []

    # ── Validate: name (if provided) ──────────────────────────────────────────
    if body.name is not None:
        name = body.name.strip()
        if not name:
            errors.append("name must be a non-empty string")
        elif len(name) < 3:
            errors.append("name must be at least 3 characters")

    # ── Validate: email (if provided) ─────────────────────────────────────────
    if body.email is not None:
        email = body.email.strip()
        if not email:
            errors.append("email must be a non-empty string")
        elif not EMAIL_REGEX.match(email):
            # Regex check — DB-level uniqueness is checked in the main handler
            errors.append("email is not a valid email address")

    # ── Validate: password (if provided) ─────────────────────────────────────
    if body.password is not None:
        password = body.password.strip()
        if not password:
            errors.append("password must be a non-empty string")
        elif len(password) < 8:
            errors.append("password must be at least 8 characters")

    if errors:
        logger.warning(
            f"Update payload validation failed | "
            f'{json.dumps({"errors": errors})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    logger.debug(
        f"Update payload validation passed | "
        f'{json.dumps({"fields_to_update": [f for f, v in {"name": body.name, "email": body.email, "password": body.password}.items() if v is not None]})}'
    )


@router.post(
    "/update-user/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def update_user(username: str, body: UserUpdateRequest, db: Session = Depends(get_db)):
    """
    Partially update an existing user's fields.

    Flow:
      1. Log the incoming request (password masked)
      2. Validate the payload via _validate_payload()
      3. Fetch the user from DB — raise 404 if not found
      4. For each provided field, validate and apply the update:
         - email: check uniqueness against other users before applying
         - name: strip whitespace and apply
         - password: hash with bcrypt and apply (discards plain text)
      5. Commit the transaction
      6. Return the updated user info

    Args:
        username (str):          Path parameter — the username to update.
        body (UserUpdateRequest): Parsed request body (all fields optional).
        db (Session):            SQLAlchemy session injected via FastAPI Depends(get_db).

    Returns:
        UserResponse (200): Updated user details and a success message.

    Raises:
        HTTPException (400): Validation failure (no fields, or invalid field values).
        HTTPException (404): User with given username does not exist.
        HTTPException (409): New email is already in use by another user.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    logger.info(
        f"Incoming update-user request | "
        f'{json.dumps({"username": username, "body": mask_sensitive(body.model_dump(exclude_none=True))})}'
    )

    # ── Step 1: Validate the request body ─────────────────────────────────────
    _validate_payload(body)

    # ── Step 2: Fetch the user to update ──────────────────────────────────────
    logger.debug(
        f"Fetching user from DB | "
        f'{json.dumps({"username": username})}'
    )

    # Fetch the full User ORM object (including password) so we can mutate fields
    user = db.query(User).filter(User.username == username).first()

    if not user:
        logger.warning(
            f"Update failed — user not found | "
            f'{json.dumps({"username": username})}'
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    logger.debug(
        f"User found — applying updates | "
        f'{json.dumps({"username": username})}'
    )

    # ── Step 3a: Update email (if provided) ────────────────────────────────────
    if body.email is not None:
        email = body.email.strip()

        # Check that the new email is not already used by a DIFFERENT user.
        # We exclude the current user from the conflict check (User.username != username)
        # so a user can "update" to their own existing email without a 409.
        logger.debug(
            f"Checking email uniqueness | "
            f'{json.dumps({"new_email": email, "current_username": username})}'
        )

        conflict = (
            db.query(User)
            .filter(User.email == email, User.username != username)
            .first()
        )

        if conflict:
            logger.warning(
                f"Email conflict — already in use by another user | "
                f'{json.dumps({"new_email": email, "conflicting_username": conflict.username})}'
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use by another user",
            )

        logger.debug(
            f"Email is available — updating | "
            f'{json.dumps({"new_email": email})}'
        )
        user.email = email

    # ── Step 3b: Update name (if provided) ────────────────────────────────────
    if body.name is not None:
        new_name = body.name.strip()
        logger.debug(
            f"Updating name | "
            f'{json.dumps({"username": username, "new_name": new_name})}'
        )
        user.name = new_name

    # ── Step 3c: Update password (if provided) ────────────────────────────────
    if body.password is not None:
        # Hash the new plain-text password before storing
        logger.debug(f"Updating password | {json.dumps({'username': username})}")
        user.password = hash_password(body.password.strip())

    # ── Step 4: Commit the transaction ────────────────────────────────────────
    logger.debug(
        f"Committing updates to database | "
        f'{json.dumps({"username": username})}'
    )

    try:
        db.commit()       # Write all changes to PostgreSQL
        db.refresh(user)  # Sync ORM object with the committed DB state
    except IntegrityError:
        # Race condition: another request claimed the same email between our
        # uniqueness check above and this commit.
        db.rollback()
        logger.error(
            f"IntegrityError on update — email conflict (race condition) | "
            f'{json.dumps({"username": username})}'
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already in use by another user",
        )

    # ── Step 5: Log success and return response ────────────────────────────────
    logger.info(
        f"User updated successfully | "
        f'{json.dumps({"username": user.username, "name": user.name, "email": user.email})}'
    )

    return UserResponse(
        name=user.name,
        email=user.email,
        username=user.username,
        message="User updated successfully",
    )
