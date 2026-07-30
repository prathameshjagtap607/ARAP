import pytest


@pytest.mark.anyio
async def test_list_users_returns_org_users(async_client, user_seed, user_token):
    resp = await async_client.get(
        "/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 2
    emails = {item["email"] for item in body["items"]}
    assert emails == {user_seed["admin"].email, user_seed["member"].email}


@pytest.mark.anyio
async def test_list_users_scoped_to_org(async_client, user_seed, user_token, db):
    from src.models.orgs import Org
    from src.models.users import User

    other_org = Org(name="Other Org")
    db.add(other_org)
    db.flush()
    other_user = User(
        org_id=other_org.id, email="outsider@test.com", role="user", password_hash="x"
    )
    db.add(other_user)
    db.commit()

    resp = await async_client.get(
        "/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    emails = {item["email"] for item in resp.json()["items"]}
    assert "outsider@test.com" not in emails


@pytest.mark.anyio
async def test_list_users_requires_auth(async_client, user_seed):
    resp = await async_client.get("/users")
    assert resp.status_code == 401
