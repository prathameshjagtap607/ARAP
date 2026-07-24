import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def started_client(async_client, seed, candidate_token, db):
    """Client fixture with session already started."""
    from src.models.assessment_sessions import AssessmentSession
    from datetime import UTC, datetime
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    if s.status == "invited":
        s.status = "in_progress"
        s.started_at = datetime.now(UTC)
        db.commit()
    return async_client


@pytest.mark.asyncio
async def test_invite_endpoint_requires_user_token(async_client, seed, candidate_token):
    """POST /sessions/{id}/invite rejects candidate JWT."""
    resp = await async_client.post(
        f"/sessions/{seed['session'].id}/invite",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invite_endpoint_returns_link(async_client, seed, user_token):
    """POST /sessions/{id}/invite returns link and email_sent."""
    from unittest.mock import patch
    with patch("src.modules.sessions.service.send_invite_email", return_value=False):
        resp = await async_client.post(
            f"/sessions/{seed['session'].id}/invite",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "link" in data
    assert str(seed["session"].id) in data["link"]
    assert data["email_sent"] is False


@pytest.mark.asyncio
async def test_get_session_state(async_client, seed, candidate_token):
    """GET /sessions/{id} returns status and questions."""
    resp = await async_client.get(
        f"/sessions/{seed['session'].id}",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("invited", "in_progress", "completed", "expired")
    assert len(data["questions"]) == 2


@pytest.mark.asyncio
async def test_start_session_endpoint(async_client, seed, candidate_token, db):
    """POST /sessions/{id}/start transitions to in_progress."""
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    s.status = "invited"
    s.started_at = None
    db.commit()
    resp = await async_client.post(
        f"/sessions/{seed['session'].id}/start",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_patch_answer_endpoint(started_client, seed, candidate_token):
    """PATCH /sessions/{id}/questions/{qid}/answer saves answer."""
    resp = await started_client.patch(
        f"/sessions/{seed['session'].id}/questions/{seed['q1'].id}/answer",
        json={"answer_text": "I have 5 years of Python experience."},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer_text"] == "I have 5 years of Python experience."
    assert data["answered_at"] is not None


@pytest.mark.asyncio
async def test_patch_answer_wrong_session_rejected(async_client, seed, candidate_token):
    """PATCH with question not belonging to this session returns 404."""
    import uuid
    resp = await async_client.patch(
        f"/sessions/{seed['session'].id}/questions/{uuid.uuid4()}/answer",
        json={"answer_text": "Anything"},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_endpoint(started_client, seed, candidate_token):
    """POST /sessions/{id}/submit transitions to completed."""
    resp = await started_client.post(
        f"/sessions/{seed['session'].id}/submit",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("completed", "expired")


@pytest.mark.asyncio
async def test_patch_answer_question_from_different_session_rejected(async_client, seed, candidate_token, db):
    """PATCH with question belonging to a different session returns 404."""
    from datetime import UTC, datetime
    from src.models.assessment_sessions import AssessmentSession
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    # Create a second session with its own question
    other_session = AssessmentSession(
        org_id=seed["org"].id,
        job_assessment_id=seed["job"].id,
        candidate_id=seed["candidate"].id,
        time_budget_seconds=1800,
        status="in_progress",
        started_at=datetime.now(UTC),
    )
    db.add(other_session)
    db.flush()

    other_qset = QuestionSet(
        org_id=seed["org"].id,
        session_id=other_session.id,
        generation_prompt_version="v1",
        locked_at=datetime.now(UTC),
    )
    db.add(other_qset)
    db.flush()

    other_q = SessionQuestion(
        org_id=seed["org"].id,
        question_set_id=other_qset.id,
        sequence_no=1,
        question={"text": "Other session question"},
        category="Technical",
        target_competencies=["problem_solving"],
        difficulty="easy",
        answer_format="short_text",
    )
    db.add(other_q)
    db.commit()

    # candidate_token is scoped to seed["session"], not other_session
    # Using other_q.id (which belongs to other_session) should return 404
    resp = await async_client.patch(
        f"/sessions/{seed['session'].id}/questions/{other_q.id}/answer",
        json={"answer_text": "Cross-session attempt"},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_candidate_cannot_access_other_session(async_client, seed, db):
    """Candidate JWT for session A cannot access session B."""
    import uuid
    from src.modules.auth.token import create_access_token
    other_id = uuid.uuid4()
    token = create_access_token({
        "sub": str(seed["candidate"].id),
        "role": "candidate",
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(other_id),
    })
    resp = await async_client.get(
        f"/sessions/{seed['session'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
