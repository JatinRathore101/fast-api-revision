"""
Handler for POST /session/logout

Endpoint:   POST /session/logout
Headers:    active-user-email          (required)
            active-user-session-token  (required)
Response:   200 OK           → LogoutResponse  (name, email, username, message)
            400 Bad Request  → missing required headers
            401 Unauthorized → no active session found, or token mismatch
            404 Not Found    → user does not exist

Request flow within this handler:
  1. Header validation     → both headers must be present
  2. DB lookup             → find user by email from header
  3. Redis GET             → retrieve stored session token for the user
  4. Token comparison      → header token must match stored token
  5. Redis DEL             → delete the session key to invalidate the session
  6. Return LogoutResponse → name, email, username, message
"""

import json

import redis
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.session import LogoutResponse
from app.utils.logger import logger

router = APIRouter()

# ─── Constants ───────────────────────────────────────────────────────────────────
SESSION_KEY_PREFIX = "user-session-"


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
)
def logout(
    active_user_email: str = Header(None, alias="active-user-email"),
    active_user_session_token: str = Header(None, alias="active-user-session-token"),
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Invalidate an active user session.

    Flow:
      1. Ensure both required headers are present
      2. Look up the user in the DB by email from the header
      3. Fetch the stored session token from Redis
      4. Verify the submitted token matches the stored token
      5. Delete the session key from Redis
      6. Return LogoutResponse with the user's details

    Headers:
        active-user-email         (str): Email address of the logged-in user.
        active-user-session-token (str): Token returned at login time.

    Args:
        active_user_email         (str):         From `active-user-email` header.
        active_user_session_token (str):         From `active-user-session-token` header.
        db                        (Session):     SQLAlchemy session via Depends(get_db).
        redis_client              (redis.Redis): Redis client via Depends(get_redis).

    Returns:
        LogoutResponse (200): User details + success message.

    Raises:
        HTTPException (400): One or both required headers are missing.
        HTTPException (401): No active session exists, or session token mismatch.
        HTTPException (404): No user found for the email in the header.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    # Only log the email — never log the session token value
    logger.info(
        f"Incoming logout request | "
        f'{json.dumps({"email": active_user_email})}'
    )

    # ── Step 1: Validate required headers ─────────────────────────────────────
    errors = []
    if not active_user_email:
        errors.append("active-user-email header is required")
    if not active_user_session_token:
        errors.append("active-user-session-token header is required")

    if errors:
        logger.warning(
            f"Logout failed — missing required headers | "
            f'{json.dumps({"errors": errors})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    # ── Step 2: Fetch user from DB by email ───────────────────────────────────
    logger.debug(
        f"Looking up user in database | "
        f'{json.dumps({"email": active_user_email})}'
    )

    user = db.query(User).filter(User.email == active_user_email).first()

    if not user:
        logger.warning(
            f"Logout failed — user not found | "
            f'{json.dumps({"email": active_user_email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.debug(
        f"User found — validating session in Redis | "
        f'{json.dumps({"username": user.username, "email": user.email})}'
    )

    # ── Step 3: Retrieve session token from Redis ─────────────────────────────
    session_key = f"{SESSION_KEY_PREFIX}{user.email}"
    stored_token = redis_client.get(session_key)

    if not stored_token:
        logger.warning(
            f"Logout failed — no active session found in Redis | "
            f'{json.dumps({"email": user.email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session found for this user",
        )

    # ── Step 4: Verify submitted token matches stored token ───────────────────
    # Intentionally not logging either token value
    if stored_token != active_user_session_token:
        logger.warning(
            f"Logout failed — session token mismatch | "
            f'{json.dumps({"email": user.email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )

    # ── Step 5: Delete session from Redis ─────────────────────────────────────
    logger.debug(
        f"Deleting session from Redis | "
        f'{json.dumps({"email": user.email})}'
    )

    redis_client.delete(session_key)

    # ── Step 6: Log success and return the response ────────────────────────────
    logger.info(
        f"User logged out successfully — session invalidated | "
        f'{json.dumps({"username": user.username, "email": user.email})}'
    )

    return LogoutResponse(
        name=user.name,
        email=user.email,
        username=user.username,
        message="Logged out successfully",
    )
