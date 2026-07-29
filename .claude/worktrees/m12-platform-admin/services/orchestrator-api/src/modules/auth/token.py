import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import redis as redis_lib

from src.config import settings

NIL_UUID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    data["type"] = "access"
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def create_refresh_token(r: redis_lib.Redis, user_id: str, org_id: str, role: str) -> str:
    raw = secrets.token_urlsafe(32)
    key = f"refresh:{_sha256(raw)}"
    value = json.dumps({"user_id": user_id, "org_id": org_id, "role": role})
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    r.setex(key, ttl, value)
    return raw


def rotate_refresh_token(r: redis_lib.Redis, old_raw: str) -> tuple[dict, str]:
    old_key = f"refresh:{_sha256(old_raw)}"
    raw_value = r.get(old_key)
    if not raw_value:
        raise ValueError("refresh token not found or expired")
    r.delete(old_key)
    data = json.loads(raw_value)
    new_raw = create_refresh_token(r, data["user_id"], data["org_id"], data["role"])
    return data, new_raw


def delete_refresh_token(r: redis_lib.Redis, raw: str) -> None:
    r.delete(f"refresh:{_sha256(raw)}")


def generate_login_token() -> str:
    return secrets.token_urlsafe(32)


def hash_login_token(token: str) -> str:
    return _sha256(token)
