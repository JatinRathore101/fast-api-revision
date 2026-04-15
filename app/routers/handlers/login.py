"""
Handler for POST /session/login

Endpoint:   POST /session/login
Response:   200 OK           → LoginResponse  (name, email, username, session_token, message)
            400 Bad Request  → validation errors
            401 Unauthorized → wrong password
            404 Not Found    → user does not exist
            409 Conflict     → an active session already exists for this user

Request flow within this handler:
  1. _validate_payload()  → field rules (at-least-one, format, length)
  2. DB lookup            → find user by email or username
  3. verify_password()    → bcrypt comparison against stored hash
  4. Redis GET            → check for existing session key
  5. secrets.token_hex()  → generate a 64-char cryptographically secure token
  6. Redis SETEX          → store token with 1-hour TTL
  7. Return LoginResponse → name, email, username, session_token, message
"""

import json
import secrets

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.redis_client import get_redis
from app.schemas.session import LoginRequest, LoginResponse
from app.utils.logger import logger, mask_sensitive
from app.utils.security import verify_password
from app.utils.validators import EMAIL_REGEX

router = APIRouter()

# ─── Constants ───────────────────────────────────────────────────────────────────
SESSION_KEY_PREFIX = "user-session-"
SESSION_TTL_SECONDS = 3600  # 1 hour


def _validate_payload(body: LoginRequest) -> None:
    """
    Validate all fields of the login request body.

    Rules:
      - At least one of `username` or `email` must be present
      - email (if present)    : non-empty after strip, must match EMAIL_REGEX
      - username (if present) : non-empty after strip
      - password              : non-empty after strip, minimum 8 characters

    Collects ALL validation errors before raising so the client receives a
    complete list in a single 400 response (fail-all strategy, consistent
    with the rest of this project).

    Args:
        body (LoginRequest): The parsed request payload from FastAPI.

    Raises:
        HTTPException (400): If one or more validation rules fail.
                             `detail.errors` contains a list of error messages.
    """
    # Strip whitespace upfront — treat blank strings the same as absent
    username = body.username.strip() if body.username is not None else None
    email = body.email.strip() if body.email is not None else None
    password = body.password.strip()

    errors = []

    # ── Validate: at least one identifier must be present ────────────────────
    if not username and not email:
        errors.append("at least one of username or email must be provided")

    # ── Validate: email (only when caller supplied it) ────────────────────────
    if email is not None:
        if not email:
            errors.append("email must be a non-empty string")
        elif not EMAIL_REGEX.match(email):
            errors.append("email is not a valid email address")

    # ── Validate: username (only when caller supplied it) ─────────────────────
    if username is not None and not username:
        errors.append("username must be a non-empty string")

    # ── Validate: password ────────────────────────────────────────────────────
    if not password:
        errors.append("password must be a non-empty string")
    elif len(password) < 8:
        # Minimum 8 chars matches the rule enforced at user creation
        errors.append("password must be at least 8 characters")

    if errors:
        logger.warning(
            f"Login payload validation failed | "
            f'{json.dumps({"errors": errors, "username": username, "email": email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    logger.debug(
        f"Login payload validation passed | "
        f'{json.dumps({"username": username, "email": email})}'
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    """
    Authenticate a user and create a Redis-backed session.

    Flow:
      1. Log the incoming request (password masked)
      2. Validate input fields via _validate_payload()
      3. Look up the user in the DB by email or username
      4. Verify the submitted password against the stored bcrypt hash
      5. Check Redis for an already-active session — reject if found
      6. Generate a 64-char cryptographically secure session token
      7. Persist the token in Redis with a 1-hour TTL
      8. Return LoginResponse with the token

    Args:
        body         (LoginRequest): Parsed request body.
        db           (Session):      SQLAlchemy session via Depends(get_db).
        redis_client (redis.Redis):  Redis client via Depends(get_redis).

    Returns:
        LoginResponse (200): User details + session token + success message.

    Raises:
        HTTPException (400): Validation failure — see _validate_payload().
        HTTPException (401): Password does not match the stored hash.
        HTTPException (404): No user found for the given email / username.
        HTTPException (409): An active session already exists for this user.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    # mask_sensitive() replaces the password value with *** before logging
    logger.info(
        f"Incoming login request | "
        f"{json.dumps(mask_sensitive(body.model_dump()))}"
    )

    # ── Step 1: Validate all input fields ─────────────────────────────────────
    _validate_payload(body)

    # Normalise values after validation (strip is safe to repeat)
    username = body.username.strip() if body.username is not None else None
    email = body.email.strip() if body.email is not None else None
    password = body.password.strip()

    # ── Step 2: Fetch user from DB ────────────────────────────────────────────
    # Prefer email lookup when both identifiers are supplied (email is unique
    # at the DB level via a UNIQUE constraint, same as username)
    logger.debug(
        f"Looking up user in database | "
        f'{json.dumps({"username": username, "email": email})}'
    )

    if email:
        user = db.query(User).filter(User.email == email).first()
    else:
        user = db.query(User).filter(User.username == username).first()

    if not user:
        identifier = email or username
        logger.warning(
            f"Login failed — user not found | "
            f'{json.dumps({"identifier": identifier})}'
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.debug(
        f"User found — proceeding to password verification | "
        f'{json.dumps({"username": user.username, "email": user.email})}'
    )

    # ── Step 3: Verify password ───────────────────────────────────────────────
    # verify_password() is a constant-time bcrypt comparison (see app/utils/security.py)
    if not verify_password(password, user.password):
        logger.warning(
            f"Login failed — invalid password | "
            f'{json.dumps({"username": user.username, "email": user.email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # ── Step 4: Check for existing session in Redis ────────────────────────────
    session_key = f"{SESSION_KEY_PREFIX}{user.email}"

    logger.debug(
        f"Checking Redis for existing session | "
        f'{json.dumps({"email": user.email})}'
    )

    existing_session = redis_client.get(session_key)

    if existing_session:
        logger.warning(
            f"Login failed — active session already exists | "
            f'{json.dumps({"email": user.email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active session already exists",
        )

    # ── Step 5: Generate a secure session token ────────────────────────────────
    # secrets.token_hex(32) → 32 random bytes encoded as a 64-character hex string.
    # The `secrets` module is the standard-library CSPRNG for security tokens.
    session_token = secrets.token_hex(32)

    # ── Step 6: Store session in Redis with TTL ────────────────────────────────
    logger.debug(
        f"Storing session in Redis | "
        f'{json.dumps({"email": user.email, "ttl_seconds": SESSION_TTL_SECONDS})}'
    )

    redis_client.setex(session_key, SESSION_TTL_SECONDS, session_token)

    # ── Step 7: Log success and return the response ────────────────────────────
    # Do NOT log the session_token value — it is a security credential
    logger.info(
        f"User logged in successfully — session created | "
        f'{json.dumps({"username": user.username, "email": user.email, "ttl_seconds": SESSION_TTL_SECONDS})}'
    )

    return LoginResponse(
        name=user.name,
        email=user.email,
        username=user.username,
        session_token=session_token,
        message="Logged in successfully",
    )
