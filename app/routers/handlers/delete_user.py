"""
Handler for DELETE /users/delete-user/{username}

Endpoint:   DELETE /users/delete-user/{username}
Response:   200 OK       → UserResponse (deleted user's details + success message)
            404 Not Found → user with given username does not exist

Permanently deletes a user from the database.

Why return 200 (not 204)?
  We return 200 with the deleted user's details so that the caller can
  confirm exactly which record was removed. A 204 No Content would give
  no confirmation. This is a deliberate design choice in this service.

Implementation note:
  We capture name, email, and username BEFORE calling db.delete(), because
  once the session flushes the delete, those attributes may no longer be
  accessible on the detached ORM object.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.utils.logger import logger

router = APIRouter()


@router.delete(
    "/delete-user/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def delete_user(username: str, db: Session = Depends(get_db)):
    """
    Permanently delete a user by their username.

    Flow:
      1. Log the incoming request with the path parameter
      2. Fetch the user from DB — raise 404 if not found
      3. Capture the user's details before deletion
      4. Delete the record and commit the transaction
      5. Return the deleted user's details with a success message

    Args:
        username (str): Path parameter — the username of the user to delete.
        db (Session):   SQLAlchemy session injected via FastAPI Depends(get_db).

    Returns:
        UserResponse (200): Details of the deleted user and a success message.

    Raises:
        HTTPException (404): No user exists with the given username.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    logger.info(
        f"Incoming delete-user request | "
        f'{json.dumps({"username": username})}'
    )

    # ── Step 1: Fetch user to confirm existence ────────────────────────────────
    # We need the full ORM object (not a column projection) so that db.delete()
    # can mark the correct row for deletion.
    logger.debug(
        f"Fetching user from DB for deletion | "
        f'{json.dumps({"query": "SELECT * FROM user_table WHERE username = :username", "username": username})}'
    )

    user = db.query(User).filter(User.username == username).first()

    if not user:
        logger.warning(
            f"Delete failed — user not found | "
            f'{json.dumps({"username": username})}'
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    logger.debug(
        f"User found — proceeding with deletion | "
        f'{json.dumps({"username": user.username, "email": user.email, "name": user.name})}'
    )

    # ── Step 2: Capture user details BEFORE deletion ──────────────────────────
    # After db.delete() + db.commit(), the ORM object is in a detached/expired
    # state. Capturing the values now ensures we can still build the response.
    name, email, uname = user.name, user.email, user.username

    # ── Step 3: Delete and commit ─────────────────────────────────────────────
    logger.debug(
        f"Executing DELETE query | "
        f'{json.dumps({"query": "DELETE FROM user_table WHERE username = :username", "username": uname})}'
    )

    db.delete(user)
    db.commit()  # Commit the DELETE transaction to PostgreSQL

    # ── Step 4: Log and return response ───────────────────────────────────────
    logger.info(
        f"User deleted successfully | "
        f'{json.dumps({"username": uname, "name": name, "email": email})}'
    )

    return UserResponse(
        name=name,
        email=email,
        username=uname,
        message="User deleted successfully",
    )
