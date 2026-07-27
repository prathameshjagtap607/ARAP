import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import jwt
import pytest

from src.modules.auth.token import (
    NIL_UUID,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    delete_refresh_token,
    generate_login_token,
    hash_login_token,
    rotate_refresh_token,
)


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


def test_create_and_decode_access_token():
    payload = {"sub": str(uuid.uuid4()), "role": "user", "org_id": str(uuid.uuid4())}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded["sub"] == payload["sub"]
    assert decoded["role"] == "user"
    assert decoded["type"] == "access"
    assert "exp" in decoded


def test_decode_expired_token_raises():
    payload = {"sub": "x", "role": "user", "org_id": "y"}
    with patch("src.modules.auth.token.settings") as m:
        m.JWT_SECRET_KEY = "test-secret"
        m.JWT_ALGORITHM = "HS256"
        m.ACCESS_TOKEN_EXPIRE_MINUTES = -1  # already expired
        token = create_access_token(payload)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)


def test_decode_wrong_key_raises():
    import jwt as _jwt
    payload = {"sub": "x", "role": "user", "org_id": "y", "type": "access",
               "exp": datetime.now(UTC) + timedelta(minutes=15)}
    token = _jwt.encode(payload, "wrong-key", algorithm="HS256")
    with pytest.raises(_jwt.InvalidSignatureError):
        decode_access_token(token)


def test_create_refresh_token_stores_in_redis(fake_redis):
    raw = create_refresh_token(fake_redis, "uid", "oid", "user")
    assert isinstance(raw, str)
    assert len(raw) > 20
    key = f"refresh:{hash_login_token(raw)}"
    stored = fake_redis.get(key)
    assert stored is not None
    data = json.loads(stored)
    assert data["user_id"] == "uid"
    assert data["role"] == "user"


def test_rotate_refresh_token(fake_redis):
    raw = create_refresh_token(fake_redis, "uid", "oid", "admin")
    data, new_raw = rotate_refresh_token(fake_redis, raw)
    assert data["user_id"] == "uid"
    assert new_raw != raw
    # old token gone
    assert fake_redis.get(f"refresh:{hash_login_token(raw)}") is None
    # new token present
    assert fake_redis.get(f"refresh:{hash_login_token(new_raw)}") is not None


def test_rotate_missing_refresh_token_raises(fake_redis):
    with pytest.raises(ValueError, match="not found"):
        rotate_refresh_token(fake_redis, "nonexistent-token")


def test_delete_refresh_token(fake_redis):
    raw = create_refresh_token(fake_redis, "uid", "oid", "user")
    delete_refresh_token(fake_redis, raw)
    assert fake_redis.get(f"refresh:{hash_login_token(raw)}") is None


def test_generate_login_token_is_unique():
    t1 = generate_login_token()
    t2 = generate_login_token()
    assert t1 != t2
    assert len(t1) > 20


def test_hash_login_token_is_deterministic():
    token = "abc123"
    assert hash_login_token(token) == hash_login_token(token)


def test_nil_uuid():
    assert str(NIL_UUID) == "00000000-0000-0000-0000-000000000000"
