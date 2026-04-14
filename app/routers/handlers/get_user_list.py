from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserListItem, UserListResponse

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
    errors = []
    if skip < 0:
        errors.append("skip must be a non-negative integer")
    if limit <= 0:
        errors.append("limit must be a positive integer")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    users = (
        db.query(User.name, User.email, User.username)
        .order_by(User.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total_count = db.query(func.count(User.username)).scalar()

    return UserListResponse(
        user_list=[
            UserListItem(name=u.name, email=u.email, username=u.username)
            for u in users
        ],
        total_count=total_count,
        message="User list fetched successfully",
    )
