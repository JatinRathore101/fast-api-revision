"""
Application entry point — User Management FastAPI service.

This module is responsible for:
  1. Creating the FastAPI application instance with metadata (title, version, etc.)
  2. Registering middleware — request/response logging runs before every handler
  3. Mounting routers — all user CRUD endpoints live under the /users prefix
  4. Defining the /health endpoint — used by load balancers and uptime monitors
  5. Logging application lifecycle events (startup and shutdown)

Request flow overview:
    HTTP Request
      ↓
    RequestLoggingMiddleware  (logs method, URL, client IP)
      ↓
    Router  (app/routers/user.py aggregates all handler routers)
      ↓
    Handler  (app/routers/handlers/*.py — validation, DB, response)
      ↓
    HTTP Response
      ↑
    RequestLoggingMiddleware  (logs status code and latency)

To run the server:
    uvicorn app.main:app --reload --port 52243
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

# Middleware that logs every HTTP request and response (method, URL, status, latency)
from app.middleware.logging_middleware import RequestLoggingMiddleware

# Aggregated router that includes all user CRUD endpoints
from app.routers import user as user_router

# Application-wide logger — import once here, Loguru handles everything globally
from app.utils.logger import logger


# ─── Application Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown lifecycle.

    FastAPI calls this context manager once when the server starts and once
    when it stops. Code before `yield` runs at startup; code after runs at
    shutdown. This is the recommended way to handle lifecycle events in
    modern FastAPI (replaces the deprecated @app.on_event decorators).

    Args:
        app (FastAPI): The FastAPI application instance (injected by the framework).

    Yields:
        Control to FastAPI while the application is running.
    """
    # ── Startup ─────────────────────────────────────────────────────────────────
    logger.info("Application starting up | User Management Service v1.0.0")
    logger.debug('Registered routers | {"prefix": "/users", "tags": ["Users"]}')
    logger.debug('Registered middleware | {"middleware": "RequestLoggingMiddleware"}')

    yield  # ← Application is live and serving requests between here and shutdown

    # ── Shutdown ─────────────────────────────────────────────────────────────────
    logger.info("Application shutting down | releasing resources and closing connections")


# ─── FastAPI App Instance ────────────────────────────────────────────────────────
app = FastAPI(
    title="User Management Service",
    description="Production-ready FastAPI microservice for user management",
    version="1.0.0",
    lifespan=lifespan,  # Wire up startup/shutdown logging
)

# ─── Middleware Registration ──────────────────────────────────────────────────────
# Middleware executes in reverse-registration order (last registered = first executed).
# RequestLoggingMiddleware wraps the entire request/response cycle.
app.add_middleware(RequestLoggingMiddleware)

# ─── Router Registration ──────────────────────────────────────────────────────────
# All user-related routes (create, get, update, delete, list) are grouped under /users.
# The `tags` parameter groups them together in the auto-generated Swagger UI.
app.include_router(user_router.router, prefix="/users", tags=["Users"])


# ─── Health Check Endpoint ───────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    """
    Lightweight health check endpoint.

    Returns a simple JSON response indicating the service is running.
    Typically polled by:
      - Kubernetes liveness / readiness probes
      - Load balancers (to determine whether to route traffic here)
      - Uptime monitoring tools (Pingdom, Grafana, etc.)

    Returns:
        dict: {"status": "ok"}
    """
    logger.debug("Health check requested")
    return {"status": "ok"}
