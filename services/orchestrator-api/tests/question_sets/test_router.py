import uuid

import pytest

from tests.question_sets.conftest import FAKE_QUESTIONS


@pytest.mark.asyncio
async def test_generate_returns_201(async_client, seed, user_token, mock_agent, mock_embed):
    resp = await async_client.post(
        f"/question-sets/generate/{seed['session'].id}?target=2",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["session_id"] == str(seed["session"].id)
    assert body["locked_at"] is not None
    assert body["generation_prompt_version"] == "v2.5"
    assert len(body["questions"]) == 2
    assert body["questions"][0]["sequence_no"] == 1
    assert body["questions"][0]["question"] == FAKE_QUESTIONS[0]["question"]


@pytest.mark.asyncio
async def test_generate_returns_404_when_session_not_found(async_client, seed, user_token, mock_agent, mock_embed):
    resp = await async_client.post(
        f"/question-sets/generate/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_returns_409_when_called_twice(async_client, seed, user_token, mock_agent, mock_embed):
    await async_client.post(
        f"/question-sets/generate/{seed['session'].id}?target=2",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.post(
        f"/question-sets/generate/{seed['session'].id}?target=2",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_generate_returns_422_when_no_candidate_profile(async_client, seed, user_token, db, mock_agent, mock_embed):
    from src.models.assessment_sessions import AssessmentSession

    session = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    original = session.candidate_profile_id
    session.candidate_profile_id = None
    db.commit()

    try:
        resp = await async_client.post(
            f"/question-sets/generate/{seed['session'].id}?target=2",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 422
    finally:
        session.candidate_profile_id = original
        db.commit()


@pytest.mark.asyncio
async def test_generate_returns_502_when_agent_fails(async_client, seed, user_token, mock_embed):
    from unittest.mock import patch

    with patch(
        "src.modules.question_sets.service.run_question_generation_agent",
        return_value=None,
    ):
        resp = await async_client.post(
            f"/question-sets/generate/{seed['session'].id}?target=2",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_get_returns_404_before_generate(async_client, seed, user_token):
    resp = await async_client.get(
        f"/question-sets/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_returns_200_after_generate(async_client, seed, user_token, mock_agent, mock_embed):
    await async_client.post(
        f"/question-sets/generate/{seed['session'].id}?target=2",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        f"/question-sets/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == str(seed["session"].id)
    assert len(body["questions"]) == 2


@pytest.mark.asyncio
async def test_generate_requires_auth(async_client, seed):
    resp = await async_client.post(f"/question-sets/generate/{seed['session'].id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_requires_auth(async_client, seed):
    resp = await async_client.get(f"/question-sets/{seed['session'].id}")
    assert resp.status_code == 401
