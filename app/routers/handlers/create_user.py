"""
Handler for POST /users/create-user

Endpoint:   POST /users/create-user
Response:   201 Created  → UserResponse
            400 Bad Request → validation errors
            409 Conflict    → duplicate username or email

Request flow within this handler:
  1. _validate_payload()  → check field rules (length, format, etc.)
  2. Duplicate check      → query DB for existing username OR email
  3. hash_password()      → bcrypt the plain-text password
  4. db.add() + commit    → persist the new User record
  5. Return UserResponse  → name, email, username, message (no password)
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreateRequest, UserResponse
from app.utils.logger import logger, mask_sensitive
from app.utils.security import hash_password
from app.utils.validators import EMAIL_REGEX

router = APIRouter()


def _validate_payload(body: UserCreateRequest) -> None:
    """
    Validate all fields of the user creation request body.

    Rules:
      - name     : non-empty after strip, minimum 3 characters
      - email    : non-empty after strip, must match EMAIL_REGEX
      - username : non-empty after strip
      - password : non-empty after strip, minimum 8 characters

    Collects ALL validation errors before raising so the client receives
    a complete list in a single 400 response (fail-all strategy).

    Args:
        body (UserCreateRequest): The parsed request payload from FastAPI.

    Raises:
        HTTPException (400): If one or more validation rules fail.
                             `detail.errors` contains a list of error messages.
    """
    # Strip whitespace from all fields before validation
    name = body.name.strip()
    email = body.email.strip()
    username = body.username.strip()
    password = body.password.strip()

    errors = []

    # ── Validate: name ────────────────────────────────────────────────────────
    if not name:
        errors.append("name must be a non-empty string")
    elif len(name) < 3:
        # Minimum length prevents single-character or empty display names
        errors.append("name must be at least 3 characters")

    # ── Validate: email ───────────────────────────────────────────────────────
    if not email:
        errors.append("email must be a non-empty string")
    elif not EMAIL_REGEX.match(email):
        # Uses the centralized regex from app/utils/validators.py
        errors.append("email is not a valid email address")

    # ── Validate: username ────────────────────────────────────────────────────
    if not username:
        errors.append("username must be a non-empty string")

    # ── Validate: password ────────────────────────────────────────────────────
    if not password:
        errors.append("password must be a non-empty string")
    elif len(password) < 8:
        # Minimum 8 chars is a baseline security requirement
        errors.append("password must be at least 8 characters")

    if errors:
        # Log validation failure — include username for traceability (not password)
        logger.warning(
            f"Payload validation failed | "
            f'{json.dumps({"errors": errors, "username": username or None})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    logger.debug(
        f"Payload validation passed | "
        f'{json.dumps({"username": username, "email": email})}'
    )


@router.post(
    "/create-user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(body: UserCreateRequest, db: Session = Depends(get_db)):
    """
    Create a new user in the system.

    Flow:
      1. Log the incoming request (password masked)
      2. Validate input fields via _validate_payload()
      3. Query DB to check for username/email conflicts
      4. Hash the password using bcrypt
      5. Insert the new user record into the database
      6. Return the created user info with a 201 status

    Args:
        body (UserCreateRequest): Parsed request body with name, email, username, password.
        db   (Session):           SQLAlchemy session injected via FastAPI Depends(get_db).

    Returns:
        UserResponse (201): Created user details and a success message.

    Raises:
        HTTPException (400): Validation failure — see _validate_payload().
        HTTPException (409): A user with the same username or email already exists.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    # Mask the password field so it never appears in log output
    logger.info(
        f"Incoming create-user request | "
        f"{json.dumps(mask_sensitive(body.model_dump()))}"
    )

    # ── Step 1: Validate all input fields ─────────────────────────────────────
    # Raises HTTP 400 immediately if any field fails validation
    _validate_payload(body)

    # Extract and sanitize values after validation
    name = body.name.strip()
    email = body.email.strip()
    username = body.username.strip()
    password = body.password.strip()

    # ── Step 2: Check for duplicate username or email ──────────────────────────
    # Using OR filter catches both conflicts in a single DB round-trip
    logger.debug(
        f"Checking for duplicate username/email | "
        f'{json.dumps({"username": username, "email": email})}'
    )

    existing = (
        db.query(User)
        .filter((User.username == username) | (User.email == email))
        .first()
    )

    if existing:
        logger.warning(
            f"Conflict detected — username or email already in use | "
            f'{json.dumps({"username": username, "email": email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with the same username or email already exists",
        )

    logger.debug(
        f"No duplicate found — proceeding to create user | "
        f'{json.dumps({"username": username})}'
    )

    # ── Step 3: Hash the password ──────────────────────────────────────────────
    # hash_password() uses bcrypt with a fresh salt per call (see app/utils/security.py)
    # The plain-text password is NOT used after this point
    hashed = hash_password(password)

    # ── Step 4: Build and persist the new User record ──────────────────────────
    new_user = User(
        username=username,
        name=name,
        email=email,
        password=hashed,  # Only the bcrypt hash is stored, never plain text
    )

    logger.debug(
        f"Inserting new user into database | "
        f'{json.dumps({"username": username, "name": name, "email": email})}'
    )

    try:
        db.add(new_user)
        db.commit()        # Flush and commit the transaction to PostgreSQL
        db.refresh(new_user)  # Sync the ORM object with the committed DB state
    except IntegrityError:
        # IntegrityError fires if a UNIQUE constraint is violated at the DB level.
        # This can happen in rare race conditions where two requests create the
        # same user simultaneously and both pass the pre-check above.
        db.rollback()
        logger.error(
            f"IntegrityError on insert — duplicate username or email (race condition) | "
            f'{json.dumps({"username": username, "email": email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with the same username or email already exists",
        )

    # ── Step 5: Log success and return the response ────────────────────────────
    logger.info(
        f"User created successfully | "
        f'{json.dumps({"username": new_user.username, "name": new_user.name, "email": new_user.email})}'
    )

    return UserResponse(
        name=new_user.name,
        email=new_user.email,
        username=new_user.username,
        message="User created successfully",
    )
