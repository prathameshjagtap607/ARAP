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


@pytest.mark.asyncio
async def test_list_sessions_scopes_user_role_to_own_invites(async_client, seed, db):
    from src.models.users import User
    from src.modules.auth.token import create_access_token

    other_user = User(
        org_id=seed["org"].id,
        email="other-user@test.com",
        role="user",
        password_hash="x",
    )
    db.add(other_user)
    db.commit()

    # seed's session has no invited_by set — belongs to nobody
    other_user_token = create_access_token({
        "sub": str(other_user.id),
        "role": "user",
        "org_id": str(seed["org"].id),
    })

    resp = await async_client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
