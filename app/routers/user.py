import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreateRequest, UserResponse
from app.utils.security import hash_password

router = APIRouter()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _validate_create_payload(body: UserCreateRequest) -> None:
    name = body.name.strip()
    email = body.email.strip()
    username = body.username.strip()
    password = body.password.strip()

    errors = []

    if not name:
        errors.append("name must be a non-empty string")
    elif len(name) < 3:
        errors.append("name must be at least 3 characters")

    if not email:
        errors.append("email must be a non-empty string")
    elif not EMAIL_REGEX.match(email):
        errors.append("email is not a valid email address")

    if not username:
        errors.append("username must be a non-empty string")

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
    "/create-user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(body: UserCreateRequest, db: Session = Depends(get_db)):
    _validate_create_payload(body)

    name = body.name.strip()
    email = body.email.strip()
    username = body.username.strip()
    password = body.password.strip()

    existing = (
        db.query(User)
        .filter((User.username == username) | (User.email == email))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with the same username or email already exists",
        )

    hashed = hash_password(password)
    new_user = User(
        username=username,
        name=name,
        email=email,
        password=hashed,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with the same username or email already exists",
        )

    return UserResponse(
        name=new_user.name,
        email=new_user.email,
        username=new_user.username,
        message="User created successfully",
    )


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
