"""
Redis client and connection dependency.

This module is the single source of truth for Redis connectivity, mirroring
the pattern established in app/database.py for the PostgreSQL session layer.

How it works:
  1. Settings (from app/config.py) provide the Redis host and port.
  2. A ConnectionPool is created once at import time — all requests share it.
  3. A single module-level Redis client wraps the pool; it is thread-safe.
  4. get_redis() is a FastAPI dependency that injects the client into handlers.

Key format used by the session layer:
  user-session-{email}  →  <session token string>  (TTL: 3600 seconds / 1 hour)

Connection pool settings:
  max_connections=20   → Cap on concurrent pooled connections.
  decode_responses=True → Automatically decode bytes to str (no manual .decode()).
"""

import redis

from app.config import settings
from app.utils.logger import logger

# ─── Connection Pool ─────────────────────────────────────────────────────────────
# A single pool is shared across all requests.  Pooling prevents a new TCP
# handshake on every command and mirrors the connection-pool approach in
# the SQLAlchemy engine (database.py).
_pool = redis.ConnectionPool(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,
    decode_responses=True,  # Return str instead of bytes for all GET/HGET/etc.
    max_connections=20,
)

logger.debug(
    f'Redis configuration loaded | {{"host": "{settings.redis_host}", '
    f'"port": {settings.redis_port}, "db": 0, "max_connections": 20}}'
)

# ─── Module-level Client ─────────────────────────────────────────────────────────
# redis.Redis is thread-safe when backed by a ConnectionPool.
# A single instance is reused for every request — connections are borrowed
# from the pool per command and returned automatically.
_redis_client = redis.Redis(connection_pool=_pool)

logger.info(
    'Redis client initialized | '
    '{"max_connections": 20, "decode_responses": true}'
)


def get_redis() -> redis.Redis:
    """
    FastAPI dependency — provides the shared Redis client to route handlers.

    The client is backed by a connection pool, so each Redis command borrows
    a connection from the pool and releases it immediately after use.
    No teardown is needed per request (unlike the DB session generator).

    Usage in a route handler:
        @router.post("/example")
        def my_endpoint(redis_client: redis.Redis = Depends(get_redis)):
            redis_client.set("key", "value", ex=3600)
            ...

    Returns:
        redis.Redis: The module-level Redis client backed by the shared pool.
    """
    return _redis_client
