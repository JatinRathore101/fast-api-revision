"""
SQLAlchemy ORM model for the `user_table` database table.

This model maps directly to the PostgreSQL `user_table` table.
SQLAlchemy uses it to:
  - Generate and validate queries (SELECT, INSERT, UPDATE, DELETE)
  - Map result rows back to Python objects

Column notes:
  username → Primary key (natural key). Usernames are immutable once set.
  email    → Unique constraint ensures no two accounts share an email.
  password → Stores the bcrypt hash. Never the plain-text password.

The `Base` imported here is the DeclarativeBase from app/database.py.
Inheriting from it registers this model with SQLAlchemy's metadata
so it can be included in schema creation / Alembic migrations.
"""

from sqlalchemy import Column, String

# Base is defined in app/database.py and shared across all models.
# All models MUST inherit from it for SQLAlchemy to recognize them.
from app.database import Base


class User(Base):
    """
    ORM representation of the `user_table` PostgreSQL table.

    Each instance of this class corresponds to one row in the table.
    SQLAlchemy sessions use this class to build type-safe queries.

    Columns:
        username (str, PK): Unique login handle. Max 100 chars.
        name     (str):     Display name. Max 100 chars. Cannot be null.
        email    (str):     Email address. Must be unique across all rows.
        password (str):     bcrypt hash of the user's password. Never plain text.

    Usage:
        # Create
        user = User(username="jatin", name="Jatin Rathore",
                    email="jatin@example.com", password=hashed)
        db.add(user)
        db.commit()

        # Query
        user = db.query(User).filter(User.username == "jatin").first()
    """

    __tablename__ = "user_table"  # Must match the table name in PostgreSQL

    # Primary key — uniquely identifies each user; cannot be null or duplicated
    username = Column(String(100), primary_key=True, nullable=False)

    # Display name — shown in UI; not used for authentication
    name = Column(String(100), nullable=False)

    # Email — used for communication; unique constraint enforced at DB level
    email = Column(String(100), unique=True, nullable=False)

    # Password — stores the bcrypt hash (starts with "$2b$12$...")
    # Never log or return this field in API responses
    password = Column(String(100), nullable=False)
