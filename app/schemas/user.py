from typing import List, Optional

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    name: str
    email: str
    username: str
    message: str

    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    name: str
    email: str
    username: str

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    user_list: List[UserListItem]
    total_count: int
    message: str
