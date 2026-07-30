import pytest

from tests.job_assessments.conftest import JA_BODY

INVITE_BODY = {
    "candidate_name": "Alice Smith",
    "candidate_email": "alice@candidate.com",
    "time_budget_seconds": 3600,
}


@pytest.mark.asyncio
async def test_invite_creates_assessment_session(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    assert "link" in body
    assert "email_sent" in body
    assert "candidate_id" in body


@pytest.mark.asyncio
async def test_invite_does_not_email_until_questions_are_locked(
    async_client, seed, user_token, mock_jd_agent
):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email_sent"] is False


@pytest.mark.asyncio
async def test_sessions_invite_blocked_until_questions_locked(
    async_client, seed, user_token, mock_jd_agent
):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    session_id = resp.json()["session_id"]

    send_resp = await async_client.post(
        f"/sessions/{session_id}/invite",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert send_resp.status_code == 409


@pytest.mark.asyncio
async def test_sessions_invite_emails_once_questions_are_locked(
    async_client, seed, user_token, mock_jd_agent, db
):
    from datetime import UTC, datetime

    from src.models.question_sets import QuestionSet

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    session_id = resp.json()["session_id"]

    qset = QuestionSet(
        session_id=session_id,
        org_id=str(seed["org"].id),
        generation_prompt_version="v1",
        locked_at=datetime.now(UTC),
    )
    db.add(qset)
    db.commit()

    send_resp = await async_client.post(
        f"/sessions/{session_id}/invite",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert send_resp.status_code == 200
    assert send_resp.json()["email_sent"] is True


@pytest.mark.asyncio
async def test_invite_sets_prompt_template_id_from_active_template(
    async_client, seed, user_token, mock_jd_agent, db
):
    from sqlalchemy import text
    from src.models.assessment_sessions import AssessmentSession

    template_id = db.execute(
        text("""
            INSERT INTO prompt_templates (org_id, agent_name, version, template_body, is_active)
            VALUES (:org_id, 'question_generator', 'v1', 'body', true)
            RETURNING id
        """),
        {"org_id": str(seed["org"].id)},
    ).scalar()
    db.commit()

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    session_id = resp.json()["session_id"]
    session = db.query(AssessmentSession).filter_by(id=session_id).first()
    assert str(session.prompt_template_id) == str(template_id)


@pytest.mark.asyncio
async def test_invite_upserts_candidate_by_email(async_client, seed, user_token, mock_jd_agent, db):
    from src.models.candidates import Candidate

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    # First invite — creates candidate
    resp1 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "bob@candidate.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp1.status_code == 201

    # Second invite same email — reuses candidate
    resp2 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "bob@candidate.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp2.status_code == 201

    # Only one candidate row should exist for this email
    count = db.query(Candidate).filter_by(
        org_id=seed["org"].id, email="bob@candidate.com"
    ).count()
    assert count == 1


@pytest.mark.asyncio
async def test_invite_creates_distinct_sessions(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp1 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "c1@x.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp2 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "c2@x.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert resp1.json()["session_id"] != resp2.json()["session_id"]


@pytest.mark.asyncio
async def test_invite_bad_assessment_id_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.post(
        f"/job-assessments/{uuid.uuid4()}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404
