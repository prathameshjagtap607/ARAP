import pytest


@pytest.mark.asyncio
async def test_admin_login_success(async_client, seed):
    resp = await async_client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "adminpass",
        "org_id": str(seed["org"].id),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_user_login_success(async_client, seed):
    resp = await async_client.post("/auth/login", json={
        "email": "user@test.com",
        "password": "userpass",
        "org_id": str(seed["org"].id),
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(async_client, seed):
    resp = await async_client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "wrong",
        "org_id": str(seed["org"].id),
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(async_client, seed):
    resp = await async_client.post("/auth/login", json={
        "email": "nobody@test.com",
        "password": "anything",
        "org_id": str(seed["org"].id),
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_audit_row_written(async_client, seed, db):
    from src.models.audit_logs import AuditLog
    await async_client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "adminpass",
        "org_id": str(seed["org"].id),
    })
    row = db.query(AuditLog).filter_by(action="user_login", org_id=seed["org"].id).first()
    assert row is not None
    assert row.actor_id == seed["admin"].id


@pytest.mark.asyncio
async def test_failed_login_audit_row_written(async_client, seed, db):
    from src.models.audit_logs import AuditLog
    await async_client.post("/auth/login", json={
        "email": "nobody@test.com",
        "password": "x",
        "org_id": str(seed["org"].id),
    })
    row = db.query(AuditLog).filter_by(action="login_failed", org_id=seed["org"].id).first()
    assert row is not None
    assert row.log_metadata["email"] == "nobody@test.com"
