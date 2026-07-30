import pytest


@pytest.mark.asyncio
async def test_list_sessions_includes_candidate_and_job_ids(async_client, seed, user_token):
    resp = await async_client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    item = items[0]
    assert item["candidate_id"] == str(seed["candidate"].id)
    assert item["job_assessment_id"] == str(seed["job"].id)
