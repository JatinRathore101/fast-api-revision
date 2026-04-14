from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/get-user/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_user(username: str, db: Session = Depends(get_db)):
    user = (
        db.query(User.name, User.email, User.username)
        .filter(User.username == username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    return UserResponse(
        name=user.name,
        email=user.email,
        username=user.username,
        message="User fetched successfully",
    )
