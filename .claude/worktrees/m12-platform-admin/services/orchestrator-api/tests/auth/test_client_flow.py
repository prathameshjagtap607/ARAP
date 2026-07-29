import pytest


@pytest.mark.asyncio
async def test_client_request_token(async_client, seed):
    resp = await async_client.post("/auth/client/request-token", json={
        "email": seed["client"].email,
        "org_id": str(seed["org"].id),
        "report_share_id": str(seed["share"].id),
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_client_verify_token_returns_access_jwt(async_client, seed):
    req = await async_client.post("/auth/client/request-token", json={
        "email": seed["client"].email,
        "org_id": str(seed["org"].id),
        "report_share_id": str(seed["share"].id),
    })
    raw = req.json()["token"]

    resp = await async_client.post("/auth/client/verify-token", json={
        "token": raw,
        "report_share_id": str(seed["share"].id),
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_client_token_is_single_use(async_client, seed):
    req = await async_client.post("/auth/client/request-token", json={
        "email": seed["client"].email,
        "org_id": str(seed["org"].id),
        "report_share_id": str(seed["share"].id),
    })
    raw = req.json()["token"]
    await async_client.post("/auth/client/verify-token", json={
        "token": raw, "report_share_id": str(seed["share"].id),
    })
    resp2 = await async_client.post("/auth/client/verify-token", json={
        "token": raw, "report_share_id": str(seed["share"].id),
    })
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_client_jwt_carries_report_share_id_claim(async_client, seed):
    import jwt as _jwt
    from src.config import settings

    req = await async_client.post("/auth/client/request-token", json={
        "email": seed["client"].email,
        "org_id": str(seed["org"].id),
        "report_share_id": str(seed["share"].id),
    })
    raw = req.json()["token"]
    verify = await async_client.post("/auth/client/verify-token", json={
        "token": raw, "report_share_id": str(seed["share"].id),
    })
    payload = _jwt.decode(
        verify.json()["access_token"],
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert payload["role"] == "client"
    assert payload["report_share_id"] == str(seed["share"].id)


@pytest.mark.asyncio
async def test_client_request_wrong_email_returns_401(async_client, seed):
    resp = await async_client.post("/auth/client/request-token", json={
        "email": "wrong@email.com",
        "org_id": str(seed["org"].id),
        "report_share_id": str(seed["share"].id),
    })
    assert resp.status_code == 401
