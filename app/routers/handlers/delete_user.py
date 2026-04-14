from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.delete(
    "/delete-user/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def delete_user(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    name, email, uname = user.name, user.email, user.username

    db.delete(user)
    db.commit()

    return UserResponse(
        name=name,
        email=email,
        username=uname,
        message="User deleted successfully",
    )
