from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rbac import RBACMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.error_handler import http_exception_handler, unhandled_exception_handler
from src.api.health import router as health_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RBACMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
