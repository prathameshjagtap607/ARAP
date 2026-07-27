import pytest

from tests.job_assessments.conftest import JA_BODY

INVITE_BODY = {
    "candidate_name": "Alice Smith",
    "candidate_email": "alice@candidate.com",
    "time_budget_seconds": 3600,
}


@pytest.mark.asyncio
async def test_invite_creates_assessment_session(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "assessment_session_id" in body
    assert "candidate_id" in body
    assert body["status"] == "invited"


@pytest.mark.asyncio
async def test_invite_upserts_candidate_by_email(async_client, seed, user_token, mock_jd_agent, db):
    from src.models.candidates import Candidate

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    # First invite — creates candidate
    resp1 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "bob@candidate.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    cand_id_1 = resp1.json()["candidate_id"]

    # Second invite same email — reuses candidate
    resp2 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "bob@candidate.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    cand_id_2 = resp2.json()["candidate_id"]

    assert cand_id_1 == cand_id_2

    count = db.query(Candidate).filter_by(
        org_id=seed["org"].id, email="bob@candidate.com"
    ).count()
    assert count == 1


@pytest.mark.asyncio
async def test_invite_creates_distinct_sessions(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp1 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "c1@x.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp2 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "c2@x.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert resp1.json()["assessment_session_id"] != resp2.json()["assessment_session_id"]


@pytest.mark.asyncio
async def test_invite_bad_assessment_id_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.post(
        f"/job-assessments/{uuid.uuid4()}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404
