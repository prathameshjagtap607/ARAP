import pytest


@pytest.mark.asyncio
async def test_synthesize_returns_200(async_client, seed, user_token, mock_cp_agent):
    resp = await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(seed["candidate"].id),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == "Jane is a seasoned backend engineer with 8 years of Python expertise."
    assert body["leadership_level_estimate"] == "Manager"
    assert body["risk_flags"] == ["No direct people-management despite Manager title at Acme Corp"]
    aligned = body["skill_matrix"]["aligned"]
    assert aligned[0]["skill"] == "Python"
    assert aligned[0]["alignment"] == "yes"


@pytest.mark.asyncio
async def test_synthesize_returns_404_when_no_profile(async_client, seed, user_token, mock_cp_agent):
    import uuid
    resp = await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(uuid.uuid4()),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_synthesize_returns_422_when_parsing_confidence_null(
    async_client, seed, user_token, db
):
    from src.models.candidate_profiles import CandidateProfile

    profile = db.query(CandidateProfile).filter_by(
        candidate_id=seed["candidate"].id,
        job_assessment_id=seed["job"].id,
    ).first()
    original = profile.parsing_confidence
    profile.parsing_confidence = None
    db.commit()

    try:
        resp = await async_client.post(
            "/candidate-profiles/synthesize",
            json={
                "candidate_id": str(seed["candidate"].id),
                "job_assessment_id": str(seed["job"].id),
                "org_id": str(seed["org"].id),
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 422
    finally:
        profile.parsing_confidence = original
        db.commit()


@pytest.mark.asyncio
async def test_synthesize_returns_502_when_agent_fails(async_client, seed, user_token):
    from unittest.mock import patch

    with patch(
        "src.modules.candidate_profiles.service.run_candidate_profile_agent",
        return_value=None,
    ):
        resp = await async_client.post(
            "/candidate-profiles/synthesize",
            json={
                "candidate_id": str(seed["candidate"].id),
                "job_assessment_id": str(seed["job"].id),
                "org_id": str(seed["org"].id),
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_get_profile_returns_200_after_synthesize(async_client, seed, user_token, mock_cp_agent):
    await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(seed["candidate"].id),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        f"/candidate-profiles/{seed['candidate'].id}/{seed['job'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["candidate_id"] == str(seed["candidate"].id)


@pytest.mark.asyncio
async def test_get_profile_returns_404_when_missing(async_client, seed, user_token):
    import uuid
    resp = await async_client.get(
        f"/candidate-profiles/{uuid.uuid4()}/{seed['job'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_synthesize_requires_auth(async_client, seed):
    resp = await async_client.post(
        "/candidate-profiles/synthesize",
        json={
            "candidate_id": str(seed["candidate"].id),
            "job_assessment_id": str(seed["job"].id),
            "org_id": str(seed["org"].id),
        },
    )
    assert resp.status_code == 401
