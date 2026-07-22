import asyncio

import pytest


@pytest.mark.asyncio
async def test_refresh_returns_new_token_pair(async_client, seed):
    login = await async_client.post("/auth/login", json={
        "email": "user@test.com",
        "password": "userpass",
        "org_id": str(seed["org"].id),
    })
    old_refresh = login.json()["refresh_token"]
    old_access = login.json()["access_token"]

    # Sleep 1 s so the new access token gets a different exp (JWT is second-granular)
    await asyncio.sleep(1)
    resp = await async_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] != old_access
    assert body["refresh_token"] != old_refresh


@pytest.mark.asyncio
async def test_refresh_old_token_is_invalid_after_rotation(async_client, seed):
    login = await async_client.post("/auth/login", json={
        "email": "user@test.com",
        "password": "userpass",
        "org_id": str(seed["org"].id),
    })
    old_refresh = login.json()["refresh_token"]

    await async_client.post("/auth/refresh", json={"refresh_token": old_refresh})

    # use old token again — should fail
    resp = await async_client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(async_client, seed):
    resp = await async_client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_deletes_refresh_token(async_client, seed):
    login = await async_client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "adminpass",
        "org_id": str(seed["org"].id),
    })
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    resp = await async_client.post(
        "/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 204

    # refresh token now invalid
    resp2 = await async_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_bearer_still_returns_204(async_client, seed):
    # Logout is best-effort; no auth header = claims=None = no-op audit
    resp = await async_client.post("/auth/logout", json={})
    assert resp.status_code == 204
