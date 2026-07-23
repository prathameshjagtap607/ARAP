import boto3
from botocore.config import Config

from src.config import settings

_REGION = "us-east-1"


def _client():
    kwargs = dict(
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=_REGION,
        config=Config(signature_version="s3v4"),
    )
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def ensure_bucket() -> None:
    s3 = _client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET_RESUMES)
    except Exception:
        s3.create_bucket(Bucket=settings.S3_BUCKET_RESUMES)


def upload_file(file_bytes: bytes, key: str) -> str:
    _client().put_object(Bucket=settings.S3_BUCKET_RESUMES, Key=key, Body=file_bytes)
    return key


def download_file(key: str) -> bytes:
    response = _client().get_object(Bucket=settings.S3_BUCKET_RESUMES, Key=key)
    return response["Body"].read()
