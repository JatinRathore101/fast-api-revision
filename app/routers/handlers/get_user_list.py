"""
Handler for GET /users/get-user-list

Endpoint:   GET /users/get-user-list?skip=0&limit=5
Response:   200 OK         → UserListResponse (paginated)
            400 Bad Request → invalid pagination parameters

Returns a paginated, alphabetically sorted list of all users.

Pagination:
  skip  — number of records to skip (offset); must be >= 0
  limit — maximum records to return per page; must be > 0

The endpoint also returns `total_count` — the total number of users
in the table regardless of pagination — so clients can calculate the
total number of pages without a separate request.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserListItem, UserListResponse
from app.utils.logger import logger

router = APIRouter()


@router.get(
    "/get-user-list",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_list(
    skip: int = Query(default=0),
    limit: int = Query(default=5),
    db: Session = Depends(get_db),
):
    """
    Retrieve a paginated list of all users, ordered by name ascending.

    Flow:
      1. Log the incoming request with pagination params
      2. Validate skip >= 0 and limit > 0
      3. Query users with ORDER BY name ASC, OFFSET skip, LIMIT limit
      4. Count total users in the table (for pagination metadata)
      5. Return UserListResponse with the page of users and total count

    Args:
        skip  (int):     Number of records to skip (default 0, must be >= 0).
        limit (int):     Max records per page (default 5, must be > 0).
        db (Session):    SQLAlchemy session injected via FastAPI Depends(get_db).

    Returns:
        UserListResponse (200): Paginated user list, total count, and message.

    Raises:
        HTTPException (400): If skip < 0 or limit <= 0.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    logger.info(
        f"Incoming get-user-list request | "
        f'{json.dumps({"skip": skip, "limit": limit})}'
    )

    # ── Step 1: Validate pagination parameters ─────────────────────────────────
    # Collect all errors before raising so the client gets a full picture
    errors = []

    if skip < 0:
        # Negative offset is meaningless and could expose unintended rows
        errors.append("skip must be a non-negative integer")

    if limit <= 0:
        # Zero or negative limit would return no records or cause a DB error
        errors.append("limit must be a positive integer")

    if errors:
        logger.warning(
            f"Pagination parameter validation failed | "
            f'{json.dumps({"errors": errors, "skip": skip, "limit": limit})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    logger.debug(
        f"Pagination parameters valid | "
        f'{json.dumps({"skip": skip, "limit": limit})}'
    )

    # ── Step 2: Fetch paginated users ──────────────────────────────────────────
    # Select only non-sensitive columns (name, email, username — not password)
    # ORDER BY name ASC gives consistent alphabetical ordering across pages
    logger.debug(
        f"Executing DB query — fetch paginated user list | "
        f'{json.dumps({"query": "SELECT name, email, username FROM user_table ORDER BY name ASC OFFSET :skip LIMIT :limit", "skip": skip, "limit": limit})}'
    )

    users = (
        db.query(User.name, User.email, User.username)
        .order_by(User.name.asc())  # Deterministic ordering for consistent pagination
        .offset(skip)               # Skip the first `skip` records
        .limit(limit)               # Return at most `limit` records
        .all()
    )

    logger.debug(
        f"Query returned {len(users)} user(s) | "
        f'{json.dumps({"returned_count": len(users), "skip": skip, "limit": limit})}'
    )

    # ── Step 3: Count total users ──────────────────────────────────────────────
    # A separate COUNT(*) query is needed because the paginated query above
    # only returns a slice — `total_count` gives clients the full picture.
    total_count = db.query(func.count(User.username)).scalar()

    logger.debug(
        f"Total user count fetched | "
        f'{json.dumps({"total_count": total_count})}'
    )

    # ── Step 4: Build and return response ─────────────────────────────────────
    logger.info(
        f"User list fetched successfully | "
        f'{json.dumps({"returned_count": len(users), "total_count": total_count, "skip": skip, "limit": limit})}'
    )

    return UserListResponse(
        user_list=[
            UserListItem(name=u.name, email=u.email, username=u.username)
            for u in users
        ],
        total_count=total_count,
        message="User list fetched successfully",
    )
