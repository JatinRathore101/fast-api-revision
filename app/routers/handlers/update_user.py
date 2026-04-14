from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest
from app.utils.security import hash_password
from app.utils.validators import EMAIL_REGEX

router = APIRouter()


def _validate_payload(body: UserUpdateRequest) -> None:
    if body.name is None and body.email is None and body.password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": ["At least one of name, email, or password must be provided"]},
        )

    errors = []

    if body.name is not None:
        name = body.name.strip()
        if not name:
            errors.append("name must be a non-empty string")
        elif len(name) < 3:
            errors.append("name must be at least 3 characters")

    if body.email is not None:
        email = body.email.strip()
        if not email:
            errors.append("email must be a non-empty string")
        elif not EMAIL_REGEX.match(email):
            errors.append("email is not a valid email address")

    if body.password is not None:
        password = body.password.strip()
        if not password:
            errors.append("password must be a non-empty string")
        elif len(password) < 8:
            errors.append("password must be at least 8 characters")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )


@router.post(
    "/update-user/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def update_user(username: str, body: UserUpdateRequest, db: Session = Depends(get_db)):
    _validate_payload(body)

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    if body.email is not None:
        email = body.email.strip()
        conflict = (
            db.query(User)
            .filter(User.email == email, User.username != username)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use by another user",
            )
        user.email = email

    if body.name is not None:
        user.name = body.name.strip()

    if body.password is not None:
        user.password = hash_password(body.password.strip())

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already in use by another user",
        )

    return UserResponse(
        name=user.name,
        email=user.email,
        username=user.username,
        message="User updated successfully",
    )
