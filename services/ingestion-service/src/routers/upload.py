import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status

from src.parsers import SUPPORTED_MIME_TYPES
from src.s3 import ensure_bucket, upload_file
from src.config import settings

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_resume(file: UploadFile) -> dict:
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {file.content_type}",
        )
    file_bytes = await file.read()
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    key = f"resumes/{uuid.uuid4()}.{ext}"
    try:
        ensure_bucket()
        returned_key = upload_file(file_bytes, key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"s3_key": returned_key, "presigned_url": ""}
