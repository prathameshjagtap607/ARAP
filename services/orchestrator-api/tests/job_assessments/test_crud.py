import pytest

from tests.job_assessments.conftest import JA_BODY


@pytest.mark.asyncio
async def test_create_assessment(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Backend Engineer"
    assert body["difficulty_level"] == "mid"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_assessments(async_client, seed, user_token, mock_jd_agent):
    await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        "/job-assessments",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_assessment(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    resp = await async_client.get(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == ja_id


@pytest.mark.asyncio
async def test_update_assessment(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    resp = await async_client.patch(
        f"/job-assessments/{ja_id}",
        json={"title": "Senior Backend Engineer"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Senior Backend Engineer"


@pytest.mark.asyncio
async def test_delete_assessment(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    del_resp = await async_client.delete(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_with_session_returns_409(async_client, seed, user_token, admin_token, mock_jd_agent, db):
    from src.models.assessment_sessions import AssessmentSession
    from src.models.candidates import Candidate

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    candidate = Candidate(
        org_id=seed["org"].id, name="Test C", email="tc@x.com", auth_method="magic_link"
    )
    db.add(candidate)
    db.flush()
    import uuid
    session = AssessmentSession(
        org_id=seed["org"].id,
        job_assessment_id=uuid.UUID(ja_id),
        candidate_id=candidate.id,
        time_budget_seconds=3600,
    )
    db.add(session)
    db.commit()

    resp = await async_client.delete(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_with_candidate_profile_returns_409(async_client, seed, user_token, mock_jd_agent, db):
    from src.models.candidate_profiles import CandidateProfile
    from src.models.candidates import Candidate

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    candidate = Candidate(
        org_id=seed["org"].id, name="Test C", email="tc2@x.com", auth_method="magic_link"
    )
    db.add(candidate)
    db.flush()
    import uuid
    profile = CandidateProfile(
        org_id=seed["org"].id,
        candidate_id=candidate.id,
        job_assessment_id=uuid.UUID(ja_id),
    )
    db.add(profile)
    db.commit()

    resp = await async_client.delete(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_wrong_org_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.get(
        f"/job-assessments/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_client):
    resp = await async_client.get("/job-assessments")
    assert resp.status_code == 401
