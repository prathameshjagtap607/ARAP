import hashlib
import json
import uuid

import redis as redis_lib


def make_cache_key(org_id: uuid.UUID, feature: str, params: dict) -> str:
    params_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]
    return f"analytics:{org_id}:{feature}:{params_hash}"


def get_cached(redis: redis_lib.Redis, key: str) -> str | None:
    return redis.get(key)


def set_cached(redis: redis_lib.Redis, key: str, value: str, ttl: int = 300) -> None:
    redis.setex(key, ttl, value)


def invalidate_org_analytics(redis: redis_lib.Redis, org_id: uuid.UUID) -> None:
    pattern = f"analytics:{org_id}:*"
    cursor = 0
    while True:
        cursor, keys = redis.scan(cursor, match=pattern, count=100)
        if keys:
            redis.delete(*keys)
        if cursor == 0:
            break
