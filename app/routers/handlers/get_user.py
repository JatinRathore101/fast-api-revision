"""
Handler for GET /users/get-user/{username}

Endpoint:   GET /users/get-user/{username}
Response:   200 OK       → UserResponse
            404 Not Found → user with given username does not exist

Fetches a single user by their username (primary key).

Security note:
  Only `name`, `email`, and `username` are selected — the `password` column
  is never included in the query result and is never exposed via the API.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.utils.logger import logger

router = APIRouter()


@router.get(
    "/get-user/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_user(username: str, db: Session = Depends(get_db)):
    """
    Retrieve a single user by their username.

    Flow:
      1. Log the incoming request with the path parameter
      2. Query the database — select only non-sensitive columns
      3. Return 404 if no matching record is found
      4. Return 200 with user details on success

    Args:
        username (str):   Path parameter — the username to look up.
        db (Session):     SQLAlchemy session injected via FastAPI Depends(get_db).

    Returns:
        UserResponse (200): User's name, email, username, and a success message.

    Raises:
        HTTPException (404): No user exists with the given username.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    logger.info(
        f"Incoming get-user request | "
        f'{json.dumps({"username": username})}'
    )

    # ── Query database ────────────────────────────────────────────────────────
    # Only select name, email, username — deliberately exclude `password`
    # to ensure the hash never leaves the database layer, even accidentally.
    logger.debug(
        f"Executing DB query — fetch user by username | "
        f'{json.dumps({"query": "SELECT name, email, username FROM user_table WHERE username = :username", "username": username})}'
    )

    user = (
        db.query(User.name, User.email, User.username)
        .filter(User.username == username)
        .first()
    )

    # ── Handle not found ──────────────────────────────────────────────────────
    if not user:
        logger.warning(
            f"User not found | "
            f'{json.dumps({"username": username})}'
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    # ── Log and return success response ───────────────────────────────────────
    logger.info(
        f"User fetched successfully | "
        f'{json.dumps({"username": user.username, "email": user.email, "name": user.name})}'
    )

    return UserResponse(
        name=user.name,
        email=user.email,
        username=user.username,
        message="User fetched successfully",
    )
