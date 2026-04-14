"""
Pydantic request and response schemas for the User resource.

Pydantic models serve two purposes in FastAPI:
  1. Request bodies  → FastAPI parses and validates incoming JSON against these.
                       If a field is missing or the wrong type, a 422 is returned
                       automatically before the handler even runs.
  2. Response bodies → FastAPI serializes ORM objects or dicts to these shapes,
                       ensuring the API contract is always enforced.

Schema overview:
  UserCreateRequest  → body for POST /users/create-user
  UserUpdateRequest  → body for POST /users/update-user/{username}
  UserResponse       → standard single-user response (create, get, update, delete)
  UserListItem       → one entry in the paginated user list
  UserListResponse   → response for GET /users/get-user-list

`from_attributes=True` (formerly `orm_mode`) enables building these models
directly from SQLAlchemy ORM objects (e.g., `UserResponse.model_validate(user_orm)`).
"""

from typing import List, Optional

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    """
    Request body schema for creating a new user.

    All fields are required. Additional validation (length, format) is
    performed in the handler's `_validate_payload()` function because
    Pydantic alone cannot express cross-field or custom business rules cleanly.

    Fields:
        name     (str): Full display name of the user.
        email    (str): Unique email address.
        username (str): Unique login handle.
        password (str): Plain-text password — will be hashed before storage.
    """

    name: str
    email: str
    username: str
    password: str  # Plain text; hashed by hash_password() before DB insert


class UserUpdateRequest(BaseModel):
    """
    Request body schema for partially updating an existing user.

    All fields are optional. The handler enforces that at least one field
    must be provided (returns 400 otherwise).

    Fields:
        name     (Optional[str]): New display name, or None to leave unchanged.
        email    (Optional[str]): New email address, or None to leave unchanged.
        password (Optional[str]): New plain-text password, or None to leave unchanged.
    """

    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None  # Plain text; hashed by hash_password() before DB update


class UserResponse(BaseModel):
    """
    Standard response schema for single-user operations.

    Returned by: create-user, get-user, update-user, delete-user.

    Note: `password` is intentionally excluded — we never return hashed
    passwords in API responses.

    Fields:
        name     (str): User's display name.
        email    (str): User's email address.
        username (str): User's unique login handle.
        message  (str): Human-readable status message (e.g., "User created successfully").
    """

    name: str
    email: str
    username: str
    message: str  # Contextual message explaining the outcome of the operation

    # Allows Pydantic to read values from SQLAlchemy ORM model attributes
    model_config = {"from_attributes": True}


class UserListItem(BaseModel):
    """
    Schema for a single user entry in the paginated user list.

    Similar to UserResponse but without the `message` field since the
    message is carried at the list level (UserListResponse.message).

    Fields:
        name     (str): User's display name.
        email    (str): User's email address.
        username (str): User's unique login handle.
    """

    name: str
    email: str
    username: str

    # Allows Pydantic to read values from SQLAlchemy ORM row objects
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """
    Response schema for the paginated user list endpoint.

    Returned by: GET /users/get-user-list

    Fields:
        user_list   (List[UserListItem]): The current page of users.
        total_count (int): Total number of users in the table (across all pages).
        message     (str): Human-readable status message.
    """

    user_list: List[UserListItem]  # Paginated slice of all users
    total_count: int               # Used by clients to calculate total pages
    message: str
