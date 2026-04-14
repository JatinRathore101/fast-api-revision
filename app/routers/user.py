"""
User router aggregator.

This module collects all individual user-related handler routers and
combines them into a single `router` object that is mounted in app/main.py
under the `/users` prefix.

Why split handlers into separate files?
  Each CRUD operation lives in its own file under app/routers/handlers/.
  This keeps each file focused and small, makes code review easier, and
  avoids one massive "user router" file. This module is the glue that
  brings them together.

Handler files and their endpoints:
  create_user.py   → POST   /users/create-user
  get_user.py      → GET    /users/get-user/{username}
  update_user.py   → POST   /users/update-user/{username}
  delete_user.py   → DELETE /users/delete-user/{username}
  get_user_list.py → GET    /users/get-user-list

Mounting in app/main.py:
  app.include_router(user_router.router, prefix="/users", tags=["Users"])
"""

from fastapi import APIRouter

# Individual handler routers — each file owns exactly one endpoint
from app.routers.handlers.create_user import router as create_user_router
from app.routers.handlers.delete_user import router as delete_user_router
from app.routers.handlers.get_user import router as get_user_router
from app.routers.handlers.get_user_list import router as get_user_list_router
from app.routers.handlers.update_user import router as update_user_router

# ─── Aggregated Router ───────────────────────────────────────────────────────────
# This is the single router imported by app/main.py.
# All user endpoints are registered here and inherit the /users prefix.
router = APIRouter()

router.include_router(create_user_router)    # POST   /users/create-user
router.include_router(get_user_router)       # GET    /users/get-user/{username}
router.include_router(update_user_router)    # POST   /users/update-user/{username}
router.include_router(delete_user_router)    # DELETE /users/delete-user/{username}
router.include_router(get_user_list_router)  # GET    /users/get-user-list
