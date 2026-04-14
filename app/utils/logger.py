"""
Centralized Loguru logger for the entire application.

This is the SINGLE source of truth for all logging configuration.
Every other module should import `logger` (and `mask_sensitive`) from here
instead of creating its own logger instances.

Log format (mandatory across all layers):
    [file_name.py][function_name] LEVEL → message | optional_json_data

Examples:
    [create_user.py][create_user]    INFO  → User created successfully | {"username": "jatin"}
    [user_repo.py][get_user]         DEBUG → Executing query | {"username": "jatin"}
    [security.py][hash_password]     INFO  → Password hashed successfully

Sinks:
    1. Console (stdout) — colorized output, captures DEBUG and above
    2. File  (logs/app.log) — plain-text, DEBUG and above,
       rotated at 10 MB, retained for 10 days, thread-safe

Import usage:
    from app.utils.logger import logger, mask_sensitive
"""

import json
import os
import sys

from loguru import logger

# ─── Ensure logs/ directory exists ──────────────────────────────────────────────
# Loguru can create the file but not intermediate directories.
# This guard prevents a FileNotFoundError on first startup.
os.makedirs("logs", exist_ok=True)

# ─── Remove Loguru's default handler ────────────────────────────────────────────
# By default, Loguru adds a stderr sink with its own format.
# We remove it so we have full control over every log destination.
logger.remove()

# ─── Format Strings ─────────────────────────────────────────────────────────────
# Loguru automatically resolves:
#   {file}     → the filename where logger.xxx() was called (e.g., create_user.py)
#   {function} → the function name at the call site (e.g., create_user)
#   {level}    → the log level string (e.g., INFO, DEBUG, WARNING)
#   {message}  → the message passed to the log call

# Console: includes ANSI color codes for human-friendly terminal output
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "[<cyan>{file}</cyan>][<yellow>{function}</yellow>] "
    "<level>{level: <8}</level> → {message}"
)

# File: plain text without ANSI escape sequences (safe for log parsers / grep)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "[{file}][{function}] "
    "{level: <8} → {message}"
)

# ─── Sink 1: Console (stdout) ───────────────────────────────────────────────────
# colorize=True  → emit ANSI color codes (terminal only)
# level="DEBUG"  → capture every log level
logger.add(
    sys.stdout,
    format=CONSOLE_FORMAT,
    level="DEBUG",
    colorize=True,
)

# ─── Sink 2: File (logs/app.log) ────────────────────────────────────────────────
# rotation="10 MB"  → start a new file once the current one hits 10 MB
# retention="10 days" → automatically delete files older than 10 days
# enqueue=True      → write logs in a background thread (non-blocking, thread-safe)
# colorize=False    → no ANSI codes in log files
logger.add(
    "logs/app.log",
    format=FILE_FORMAT,
    level="DEBUG",
    rotation="10 MB",
    retention="10 days",
    colorize=False,
    enqueue=True,
)

# ─── Sensitive Data Masking ──────────────────────────────────────────────────────

# Fields whose values must NEVER appear in plain text in logs.
# Add new keys here whenever a new sensitive field is introduced.
_SENSITIVE_KEYS = {"password", "auth", "consumer-key", "token", "secret", "authorization"}


def mask_sensitive(data: dict) -> dict:
    """
    Return a shallow copy of `data` with sensitive field values replaced by '***'.

    This prevents raw credentials (passwords, tokens, API keys) from leaking
    into log files or the console.

    Sensitive fields (case-insensitive check):
        password, auth, consumer-key, token, secret, authorization

    Args:
        data (dict): The dictionary to sanitize (e.g., a request body dict).

    Returns:
        dict: A new dictionary with the same keys but sensitive values masked.

    Example:
        >>> mask_sensitive({"username": "jatin", "password": "secret123"})
        {"username": "jatin", "password": "***"}
    """
    return {
        key: "***" if key.lower() in _SENSITIVE_KEYS else value
        for key, value in data.items()
    }
