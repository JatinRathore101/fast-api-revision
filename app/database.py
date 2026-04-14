"""
Database engine, session factory, and ORM base configuration.

This module is imported by:
  - app/models/user.py  → inherits `Base` for ORM model declaration
  - All route handlers  → receive a `Session` via the `get_db()` dependency

How it works:
  1. Settings (from app/config.py) provide DB credentials.
  2. `DATABASE_URL` assembles the connection string for psycopg2.
  3. `engine` maintains a pool of reusable connections to PostgreSQL.
  4. `SessionLocal` is a factory that produces ORM sessions from the pool.
  5. `get_db()` is a FastAPI dependency — it opens a session, yields it to
     the route handler, and guarantees the session is closed afterward.

Connection pool settings:
  pool_size=10     → Keep up to 10 connections open permanently.
  max_overflow=20  → Allow up to 20 extra connections under burst traffic.
  pool_pre_ping    → Test each connection before use (catches stale connections).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings
from app.utils.logger import logger

# ─── Connection URL ──────────────────────────────────────────────────────────────
# Assembled from environment variables / .env defaults defined in app/config.py.
# The password is intentionally omitted from log output (masked as ***).
DATABASE_URL = (
    f"postgresql+psycopg2://{settings.db_user}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
)

logger.debug(
    f'Database configuration loaded | {{"host": "{settings.db_host}", '
    f'"port": {settings.db_port}, "name": "{settings.db_name}", '
    f'"user": "{settings.db_user}", "password": "***"}}'
)

# ─── SQLAlchemy Engine ───────────────────────────────────────────────────────────
# The engine manages the underlying connection pool.
#   pool_pre_ping=True  → run "SELECT 1" before handing out a connection;
#                          discards and replaces stale/broken connections silently.
#   pool_size=10        → steady-state max open connections.
#   max_overflow=20     → burst capacity on top of pool_size.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

logger.info(
    'Database engine initialized | '
    '{"pool_size": 10, "max_overflow": 20, "pool_pre_ping": true}'
)

# ─── Session Factory ─────────────────────────────────────────────────────────────
# autocommit=False → every change must be explicitly committed (data safety).
# autoflush=False  → SQL is not sent to the DB until we explicitly flush/commit.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    Declarative base class for all SQLAlchemy ORM models.

    All model classes (e.g., `User` in app/models/user.py) must inherit from
    this class so that SQLAlchemy can discover them for schema management,
    migrations, and query building.

    Example:
        class User(Base):
            __tablename__ = "user_table"
            ...
    """
    pass


def get_db():
    """
    FastAPI dependency — provides one database session per HTTP request.

    Opens a SQLAlchemy Session at the start of a request and closes it
    in the `finally` block, even if the handler raises an exception.
    This prevents connection leaks.

    How FastAPI uses it:
        The `Depends(get_db)` annotation on a route function causes FastAPI
        to call this generator, inject the yielded `db` session into the
        handler, then resume the generator (hitting `finally`) after the
        response is sent.

    Usage in a route handler:
        @router.get("/example")
        def my_endpoint(db: Session = Depends(get_db)):
            users = db.query(User).all()
            ...

    Yields:
        Session: An active SQLAlchemy ORM session bound to the engine.
    """
    db = SessionLocal()
    logger.debug("Database session opened for request")
    try:
        yield db  # ← Handler receives this session object
    finally:
        # Always close the session, returning the connection back to the pool.
        db.close()
        logger.debug("Database session closed — connection returned to pool")
