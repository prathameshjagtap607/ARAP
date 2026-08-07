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
