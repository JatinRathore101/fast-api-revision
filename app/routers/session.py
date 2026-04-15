"""
Session router aggregator.

This module collects the individual session handler routers and combines
them into a single `router` object that is mounted in app/main.py under
the `/session` prefix.  It follows the same pattern as app/routers/user.py.

Handler files and their endpoints:
  login.py  → POST /session/login
  logout.py → POST /session/logout

Mounting in app/main.py:
  app.include_router(session_router.router, prefix="/session", tags=["Session"])
"""

from fastapi import APIRouter

from app.routers.handlers.login import router as login_router
from app.routers.handlers.logout import router as logout_router

# ─── Aggregated Router ───────────────────────────────────────────────────────────
# This is the single router imported by app/main.py.
# All session endpoints are registered here and inherit the /session prefix.
router = APIRouter()

router.include_router(login_router)   # POST /session/login
router.include_router(logout_router)  # POST /session/logout
