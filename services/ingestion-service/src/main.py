from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers.analyze import router as analyze_router
from src.routers.health import router as health_router
from src.routers.upload import router as upload_router

app = FastAPI(title="ARAP Ingestion Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(upload_router)
app.include_router(analyze_router)
