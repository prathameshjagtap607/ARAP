import pytest

from tests.job_assessments.conftest import JA_BODY

TEMPLATE_BODY = {**JA_BODY, "is_template": True, "role_family": "engineering"}


@pytest.mark.asyncio
async def test_create_template(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_template"] is True
    assert body["role_family"] == "engineering"


@pytest.mark.asyncio
async def test_list_templates_filter(async_client, seed, user_token, mock_jd_agent):
    # Create one template and one regular
    await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    await async_client.post(
        "/job-assessments", json={**JA_BODY, "is_template": False},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        "/job-assessments?is_template=true",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(i["is_template"] is True for i in items)


@pytest.mark.asyncio
async def test_clone_copies_all_fields(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    source_id = create_resp.json()["id"]

    clone_resp = await async_client.post(
        f"/job-assessments/{source_id}/clone",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clone_resp.status_code == 201
    clone = clone_resp.json()
    assert clone["id"] != source_id
    assert clone["title"] == "Backend Engineer"
    assert clone["is_template"] is False


@pytest.mark.asyncio
async def test_clone_with_weightage_override(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    source_id = create_resp.json()["id"]

    new_weightage = {"problem_solving": 70.0, "communication": 20.0, "mentoring": 10.0}
    clone_resp = await async_client.post(
        f"/job-assessments/{source_id}/clone",
        json={"competency_weightage": new_weightage},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clone_resp.status_code == 201
    assert clone_resp.json()["competency_weightage"] == new_weightage


@pytest.mark.asyncio
async def test_clone_invalid_weightage_override_returns_422(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    source_id = create_resp.json()["id"]

    clone_resp = await async_client.post(
        f"/job-assessments/{source_id}/clone",
        json={"competency_weightage": {"a": 50.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clone_resp.status_code == 422


@pytest.mark.asyncio
async def test_clone_nonexistent_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.post(
        f"/job-assessments/{uuid.uuid4()}/clone",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404
