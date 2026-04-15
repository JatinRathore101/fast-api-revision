"""
MongoDB client and database dependency.

This module is the single source of truth for MongoDB connectivity, following
the same pattern established in app/redis_client.py and app/database.py.

How it works:
  1. Settings (from app/config.py) provide the MongoDB host, port, and database name.
  2. A MongoClient is created once at import time — MongoClient manages its own
     internal connection pool and is thread-safe by design.
  3. A module-level database reference provides access to all collections.
  4. get_mongo_db() is a FastAPI dependency that injects the database into handlers.

Collections:
  companies_collection → company records keyed by unique domain
                         (created and indexed by setup.py)
"""

from pymongo import MongoClient
from pymongo.database import Database

from app.config import settings
from app.utils.logger import logger

# ─── MongoClient ─────────────────────────────────────────────────────────────────
# MongoClient is thread-safe and manages its own connection pool internally.
# A single instance is reused across all requests — no per-request teardown needed.
_mongo_client: MongoClient = MongoClient(
    host=settings.mongo_host,
    port=settings.mongo_port,
)

logger.debug(
    f'MongoDB configuration loaded | {{"host": "{settings.mongo_host}", '
    f'"port": {settings.mongo_port}, "db": "{settings.mongo_db_name}"}}'
)

# ─── Database Reference ───────────────────────────────────────────────────────────
# Accessing a database by name on MongoClient is lazy — no network call is made
# until an actual command (find, insert, etc.) is issued against it.
mongo_db: Database = _mongo_client[settings.mongo_db_name]

logger.info(
    f'MongoDB client initialized | {{"db": "{settings.mongo_db_name}"}}'
)


def get_mongo_db() -> Database:
    """
    FastAPI dependency — provides the shared MongoDB database to route handlers.

    MongoClient handles connection pooling internally, so the same Database
    reference is safely injectable into concurrent requests without any
    per-request setup or teardown (unlike the SQLAlchemy session generator).

    Usage in a route handler:
        @router.get("/example")
        def my_endpoint(db: Database = Depends(get_mongo_db)):
            doc = db["companies_collection"].find_one({"domain": "example.com"})
            ...

    Returns:
        Database: The module-level MongoDB database reference.
    """
    return mongo_db
