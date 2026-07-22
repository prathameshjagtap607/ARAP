from fastapi import APIRouter
from src.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION}
