from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str


class UserResponse(BaseModel):
    name: str
    email: str
    username: str
    message: str

    model_config = {"from_attributes": True}
