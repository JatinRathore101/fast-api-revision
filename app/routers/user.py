from fastapi import APIRouter

from app.routers.handlers.create_user import router as create_user_router
from app.routers.handlers.delete_user import router as delete_user_router
from app.routers.handlers.get_user import router as get_user_router
from app.routers.handlers.get_user_list import router as get_user_list_router
from app.routers.handlers.update_user import router as update_user_router

router = APIRouter()

router.include_router(create_user_router)
router.include_router(get_user_router)
router.include_router(update_user_router)
router.include_router(delete_user_router)
router.include_router(get_user_list_router)
