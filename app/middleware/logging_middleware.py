"""
HTTP Request / Response Logging Middleware.

This middleware intercepts EVERY HTTP request that enters the FastAPI application
before it reaches any route handler, and every response before it leaves.

What it logs:
    ► Incoming request  — HTTP method, full URL, client IP address
    ► Completed request — HTTP method, URL, status code, latency (ms)
    ► Errors            — unhandled exceptions with full stack trace

Why a middleware instead of per-handler logging?
    A middleware gives us a single, guaranteed choke-point for traffic logging.
    Route handlers only run for matched routes; middleware covers everything
    (including 404s, unmatched paths, and pre-route validation failures).

Log level rules:
    INFO    → status code < 400 (success / redirect)
    WARNING → status code 400–499 (client errors)
    ERROR   → status code 500+ (server errors)

Integration:
    Registered in app/main.py via:
        app.add_middleware(RequestLoggingMiddleware)
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.logger import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Starlette BaseHTTPMiddleware subclass that logs every HTTP request/response.

    Starlette's middleware model wraps request handling with a `dispatch` method.
    We record the start time, call the next handler in the chain, then compute
    the duration and log the outcome.

    Usage (in app/main.py):
        app.add_middleware(RequestLoggingMiddleware)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Intercept the request, log arrival, forward to the route handler,
        then log the response details.

        Args:
            request  (Request):  The incoming Starlette/FastAPI request object.
            call_next (callable): Async callable that passes the request to the
                                  next middleware or the route handler.

        Returns:
            Response: The HTTP response produced by the route handler.

        Raises:
            Re-raises any exception from the handler after logging it.
        """
        # ── Record start time (high-resolution) ─────────────────────────────────
        # perf_counter gives sub-millisecond precision; wall-clock time() does not.
        start_time = time.perf_counter()

        # ── Extract client IP ────────────────────────────────────────────────────
        # request.client is None when running in certain test environments.
        client_host = request.client.host if request.client else "unknown"

        # ── Log incoming request ─────────────────────────────────────────────────
        logger.info(
            f'Incoming request | {{"method": "{request.method}", '
            f'"url": "{request.url}", "client_ip": "{client_host}"}}'
        )

        # ── Forward to route handler ─────────────────────────────────────────────
        # If the handler raises an unhandled exception, we catch it, log a full
        # stack trace, then re-raise so FastAPI's exception handlers can respond.
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                f'Unhandled exception during request | {{"method": "{request.method}", '
                f'"url": "{request.url}", "duration_ms": {duration_ms}}}'
            )
            raise  # Re-raise so FastAPI returns a proper 500 response

        # ── Compute latency ──────────────────────────────────────────────────────
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Choose log level based on HTTP status code ───────────────────────────
        # 2xx/3xx → INFO, 4xx → WARNING (client mistake), 5xx → ERROR (our fault)
        if response.status_code < 400:
            log_fn = logger.info
        elif response.status_code < 500:
            log_fn = logger.warning
        else:
            log_fn = logger.error

        log_fn(
            f'Request completed | {{"method": "{request.method}", '
            f'"url": "{request.url}", "status_code": {response.status_code}, '
            f'"duration_ms": {duration_ms}}}'
        )

        return response
