import pytest

from tests.job_assessments.conftest import JA_BODY


@pytest.mark.asyncio
async def test_weightage_summing_to_100_passes(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json={**JA_BODY, "competency_weightage": {"a": 60.0, "b": 40.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_weightage_not_summing_to_100_returns_422(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json={**JA_BODY, "competency_weightage": {"a": 60.0, "b": 30.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 422
    assert "100" in str(resp.json()["detail"])


@pytest.mark.asyncio
async def test_weightage_float_precision_passes(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json={**JA_BODY, "competency_weightage": {"a": 33.33, "b": 33.33, "c": 33.34}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_patch_weightage_validated(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    resp = await async_client.patch(
        f"/job-assessments/{ja_id}",
        json={"competency_weightage": {"a": 50.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 422
