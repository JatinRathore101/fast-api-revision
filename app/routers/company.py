"""
Company router aggregator.

This module collects the individual company handler routers and combines
them into a single `router` object that is mounted in app/main.py under
the `/companies` prefix. It follows the same pattern as app/routers/user.py
and app/routers/session.py.

Handler files and their endpoints:
  get_companies_list.py → GET /companies/get-companies-list

Mounting in app/main.py:
  app.include_router(company_router.router, prefix="/companies", tags=["Companies"])
"""

from fastapi import APIRouter

from app.routers.handlers.get_companies_list import router as get_companies_list_router

# ─── Aggregated Router ───────────────────────────────────────────────────────────
# This is the single router imported by app/main.py.
# All company endpoints are registered here and inherit the /companies prefix.
router = APIRouter()

router.include_router(get_companies_list_router)  # GET /companies/get-companies-list
