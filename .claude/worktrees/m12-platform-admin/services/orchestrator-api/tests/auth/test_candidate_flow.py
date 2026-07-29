import pytest


@pytest.mark.asyncio
async def test_candidate_request_token(async_client, seed):
    resp = await async_client.post("/auth/candidate/request-token", json={
        "email": seed["candidate"].email,
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session_a"].id),
    })
    assert resp.status_code == 200
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_candidate_verify_token_returns_access_jwt(async_client, seed):
    req = await async_client.post("/auth/candidate/request-token", json={
        "email": seed["candidate"].email,
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session_a"].id),
    })
    raw = req.json()["token"]

    resp = await async_client.post("/auth/candidate/verify-token", json={
        "token": raw,
        "assessment_session_id": str(seed["session_a"].id),
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_candidate_token_is_single_use(async_client, seed):
    req = await async_client.post("/auth/candidate/request-token", json={
        "email": seed["candidate"].email,
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session_a"].id),
    })
    raw = req.json()["token"]

    await async_client.post("/auth/candidate/verify-token", json={
        "token": raw,
        "assessment_session_id": str(seed["session_a"].id),
    })
    # second use must be rejected
    resp2 = await async_client.post("/auth/candidate/verify-token", json={
        "token": raw,
        "assessment_session_id": str(seed["session_a"].id),
    })
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_candidate_jwt_carries_session_id_claim(async_client, seed):
    import jwt as _jwt
    from src.config import settings

    req = await async_client.post("/auth/candidate/request-token", json={
        "email": seed["candidate"].email,
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session_a"].id),
    })
    raw = req.json()["token"]
    verify = await async_client.post("/auth/candidate/verify-token", json={
        "token": raw,
        "assessment_session_id": str(seed["session_a"].id),
    })
    access_token = verify.json()["access_token"]
    payload = _jwt.decode(access_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["role"] == "candidate"
    assert payload["assessment_session_id"] == str(seed["session_a"].id)


@pytest.mark.asyncio
async def test_candidate_request_wrong_email_returns_401(async_client, seed):
    resp = await async_client.post("/auth/candidate/request-token", json={
        "email": "wrong@email.com",
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session_a"].id),
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_candidate_audit_row_written(async_client, seed, db):
    from src.models.audit_logs import AuditLog

    req = await async_client.post("/auth/candidate/request-token", json={
        "email": seed["candidate"].email,
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session_a"].id),
    })
    raw = req.json()["token"]
    await async_client.post("/auth/candidate/verify-token", json={
        "token": raw,
        "assessment_session_id": str(seed["session_a"].id),
    })

    login_row = db.query(AuditLog).filter_by(
        action="candidate_login",
        org_id=seed["org"].id,
    ).first()
    assert login_row is not None
    assert login_row.actor_id == seed["candidate"].id
    assert login_row.entity_id == seed["session_a"].id
