from fastapi import APIRouter

from src.modules.admin.health.router import router as health_router
from src.modules.admin.prompts.router import router as prompts_router
from src.modules.admin.routing.router import router as routing_router
from src.modules.admin.tenants.router import router as tenants_router

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(tenants_router)
router.include_router(prompts_router)
router.include_router(routing_router)
router.include_router(health_router)
