from fastapi import FastAPI

from src.routers.analyze import router as analyze_router
from src.routers.health import router as health_router
from src.routers.upload import router as upload_router

app = FastAPI(title="ARAP Ingestion Service", version="0.1.0")

app.include_router(health_router)
app.include_router(upload_router)
app.include_router(analyze_router)
