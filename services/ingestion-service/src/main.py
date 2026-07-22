from fastapi import FastAPI

app = FastAPI(title="ARAP Ingestion Service", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ingestion-service"}
