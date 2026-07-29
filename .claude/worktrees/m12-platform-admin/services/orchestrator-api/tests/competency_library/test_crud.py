import pytest


@pytest.mark.asyncio
async def test_create_competency(async_client, seed, user_token):
    resp = await async_client.post(
        "/competency-library",
        json={"name": "Problem Solving", "description": "Analytical thinking", "rubric_notes": "Use STAR method"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Problem Solving"
    assert body["description"] == "Analytical thinking"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_competencies(async_client, seed, user_token):
    await async_client.post(
        "/competency-library",
        json={"name": "Leadership"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        "/competency-library",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    names = [i["name"] for i in items]
    assert "Leadership" in names


@pytest.mark.asyncio
async def test_update_competency(async_client, seed, user_token):
    create_resp = await async_client.post(
        "/competency-library",
        json={"name": "Communication"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    comp_id = create_resp.json()["id"]
    resp = await async_client.patch(
        f"/competency-library/{comp_id}",
        json={"rubric_notes": "Updated rubric"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["rubric_notes"] == "Updated rubric"


@pytest.mark.asyncio
async def test_delete_competency(async_client, seed, user_token):
    create_resp = await async_client.post(
        "/competency-library",
        json={"name": "ToDelete"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    comp_id = create_resp.json()["id"]
    del_resp = await async_client.delete(
        f"/competency-library/{comp_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_resp.status_code == 204
    get_resp = await async_client.get(
        "/competency-library",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ids = [i["id"] for i in get_resp.json()]
    assert comp_id not in ids


@pytest.mark.asyncio
async def test_duplicate_name_returns_409(async_client, seed, user_token):
    await async_client.post(
        "/competency-library",
        json={"name": "Unique"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.post(
        "/competency-library",
        json={"name": "Unique"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_client):
    resp = await async_client.get("/competency-library")
    assert resp.status_code == 401
