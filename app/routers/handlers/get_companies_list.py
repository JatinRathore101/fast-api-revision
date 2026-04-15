"""
Handler for GET /companies/get-companies-list

Endpoint:   GET /companies/get-companies-list?skip=0&limit=5
Headers:    active-user-email          (required)
            active-user-session-token  (required)
Response:   200 OK           → CompanyListResponse (paginated)
            400 Bad Request  → missing headers or invalid pagination params
            401 Unauthorized → missing session, or session token mismatch

Request flow within this handler:
  1. Header validation      → both headers must be present (HTTP 400 if not)
  2. Session validation     → Redis key must exist and token must match (HTTP 401 if not)
  3. Param validation       → skip >= 0, limit > 0 (HTTP 400 if not)
  4. MongoDB fetch          → find() with skip/limit, projection excludes _id
  5. MongoDB count          → count_documents({}) for total_count metadata
  6. Return CompanyListResponse → companies_list, total_count, message
"""

import json

import redis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pymongo.database import Database

from app.mongo_client import get_mongo_db
from app.redis_client import get_redis
from app.schemas.company import CompanyItem, CompanyListResponse
from app.utils.logger import logger

router = APIRouter()

# ─── Constants ───────────────────────────────────────────────────────────────────
SESSION_KEY_PREFIX = "user-session-"
COMPANIES_COLLECTION = "companies_collection"


@router.get(
    "/get-companies-list",
    response_model=CompanyListResponse,
    status_code=status.HTTP_200_OK,
)
def get_companies_list(
    skip: int = Query(default=0),
    limit: int = Query(default=5),
    active_user_email: str = Header(None, alias="active-user-email"),
    active_user_session_token: str = Header(None, alias="active-user-session-token"),
    redis_client: redis.Redis = Depends(get_redis),
    mongo_db: Database = Depends(get_mongo_db),
):
    """
    Return a paginated list of companies from companies_collection.

    The caller must supply a valid active session via headers; the session
    is validated against Redis before any MongoDB query is executed.

    Flow:
      1. Log the incoming request (email only — never log the token)
      2. Ensure both required headers are present
      3. Validate the session token against Redis
      4. Validate pagination query parameters
      5. Fetch a paginated slice of documents from companies_collection
      6. Count total documents in the collection
      7. Return CompanyListResponse

    Headers:
        active-user-email         (str): Email of the authenticated user.
        active-user-session-token (str): Session token from POST /session/login.

    Args:
        skip                      (int):          Records to skip (default 0).
        limit                     (int):          Max records to return (default 5).
        active_user_email         (str):          From `active-user-email` header.
        active_user_session_token (str):          From `active-user-session-token` header.
        redis_client              (redis.Redis):  Redis client via Depends(get_redis).
        mongo_db                  (Database):     MongoDB database via Depends(get_mongo_db).

    Returns:
        CompanyListResponse (200): Paginated companies, total count, and message.

    Raises:
        HTTPException (400): Missing required headers or invalid pagination params.
        HTTPException (401): No active session for the email, or token mismatch.
    """
    # ── Log incoming request ─────────────────────────────────────────────────
    # Only log the email — never log the session token value
    logger.info(
        f"Incoming get-companies-list request | "
        f'{json.dumps({"email": active_user_email, "skip": skip, "limit": limit})}'
    )

    # ── Step 1: Validate required headers ─────────────────────────────────────
    errors = []
    if not active_user_email:
        errors.append("active-user-email header is required")
    if not active_user_session_token:
        errors.append("active-user-session-token header is required")

    if errors:
        logger.warning(
            f"get-companies-list failed — missing required headers | "
            f'{json.dumps({"errors": errors})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    # ── Step 2: Validate session against Redis ────────────────────────────────
    session_key = f"{SESSION_KEY_PREFIX}{active_user_email}"

    logger.debug(
        f"Validating session in Redis | "
        f'{json.dumps({"email": active_user_email})}'
    )

    stored_token = redis_client.get(session_key)

    if not stored_token:
        logger.warning(
            f"get-companies-list failed — no active session found | "
            f'{json.dumps({"email": active_user_email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session found for this user",
        )

    # Intentionally not logging either token value
    if stored_token != active_user_session_token:
        logger.warning(
            f"get-companies-list failed — session token mismatch | "
            f'{json.dumps({"email": active_user_email})}'
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
        )

    logger.debug(
        f"Session validated successfully | "
        f'{json.dumps({"email": active_user_email})}'
    )

    # ── Step 3: Validate pagination parameters ─────────────────────────────────
    # Collect all errors before raising (fail-all strategy, consistent with
    # the rest of this project — see get_user_list.py)
    param_errors = []

    if skip < 0:
        param_errors.append("skip must be a non-negative integer")

    if limit <= 0:
        param_errors.append("limit must be a positive integer")

    if param_errors:
        logger.warning(
            f"Pagination parameter validation failed | "
            f'{json.dumps({"errors": param_errors, "skip": skip, "limit": limit})}'
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": param_errors},
        )

    logger.debug(
        f"Pagination parameters valid | "
        f'{json.dumps({"skip": skip, "limit": limit})}'
    )

    # ── Step 4: Fetch paginated companies from MongoDB ─────────────────────────
    # Projection {"_id": 0} excludes the MongoDB ObjectId so Pydantic can
    # deserialize the documents directly without ObjectId serialization issues.
    collection = mongo_db[COMPANIES_COLLECTION]

    logger.debug(
        f"Executing MongoDB query — fetch paginated companies | "
        f'{json.dumps({"collection": COMPANIES_COLLECTION, "skip": skip, "limit": limit})}'
    )

    documents = list(
        collection.find({}, {"_id": 0}).skip(skip).limit(limit)
    )

    logger.debug(
        f"MongoDB query returned {len(documents)} document(s) | "
        f'{json.dumps({"returned_count": len(documents), "skip": skip, "limit": limit})}'
    )

    # ── Step 5: Count total documents in the collection ────────────────────────
    # count_documents({}) returns the total number of documents regardless of
    # the pagination applied above — clients use this to calculate total pages.
    total_count = collection.count_documents({})

    logger.debug(
        f"Total company count fetched | "
        f'{json.dumps({"total_count": total_count})}'
    )

    # ── Step 6: Build and return response ─────────────────────────────────────
    logger.info(
        f"Companies list fetched successfully | "
        f'{json.dumps({"returned_count": len(documents), "total_count": total_count, "skip": skip, "limit": limit})}'
    )

    return CompanyListResponse(
        companies_list=[CompanyItem(**doc) for doc in documents],
        total_count=total_count,
        message="Companies list fetched successfully",
    )
