"""
Pydantic request and response schemas for session operations (login / logout).

Schema overview:
  LoginRequest   → body for POST /session/login
  LoginResponse  → response for POST /session/login
  LogoutResponse → response for POST /session/logout

`from_attributes=True` enables building these models directly from SQLAlchemy
ORM objects (e.g., `LoginResponse.model_validate(user_orm, ...)`).

Note: session_token is only ever present in LoginResponse — it is never
returned in LogoutResponse and must never be logged.
"""

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """
    Request body schema for POST /session/login.

    At least one of `username` or `email` must be provided; `password` is
    always required.  Cross-field validation (at-least-one rule, format
    checks) is handled in the handler's `_validate_payload()` function.

    Fields:
        username (Optional[str]): Login handle — mutually usable with email.
        email    (Optional[str]): Email address — mutually usable with username.
        password (str):          Plain-text password — verified against stored hash.
    """

    username: Optional[str] = None
    email: Optional[str] = None
    password: str


class LoginResponse(BaseModel):
    """
    Response schema for a successful POST /session/login.

    Fields:
        name          (str): User's display name.
        email         (str): User's email address.
        username      (str): User's unique login handle.
        session_token (str): Secure random 64-character hex token for the session.
                             Store client-side and pass as the
                             `active-user-session-token` header on logout.
        message       (str): Human-readable status message.
    """

    name: str
    email: str
    username: str
    session_token: str  # 64-char hex; stored in Redis — never log this value
    message: str

    model_config = {"from_attributes": True}


class LogoutResponse(BaseModel):
    """
    Response schema for a successful POST /session/logout.

    Fields:
        name     (str): User's display name.
        email    (str): User's email address.
        username (str): User's unique login handle.
        message  (str): Human-readable status message.
    """

    name: str
    email: str
    username: str
    message: str

    model_config = {"from_attributes": True}
