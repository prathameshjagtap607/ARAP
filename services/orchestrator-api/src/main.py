from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.health import router as health_router
from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.error_handler import (
    http_exception_handler,
    unhandled_exception_handler,
)
from src.middleware.rate_limit import RateLimitMiddleware
from src.modules.auth.router import router as auth_router
from src.modules.candidate_profiles.router import router as candidate_profiles_router
from src.modules.competency_library.router import router as competency_library_router
from src.modules.job_assessments.router import router as job_assessments_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(competency_library_router)
app.include_router(job_assessments_router)
app.include_router(candidate_profiles_router)
