import uuid

import pytest


@pytest.mark.asyncio
async def test_delete_session_removes_session_and_question_set(
    async_client, seed, user_token, db
):
    from src.models.assessment_sessions import AssessmentSession
    from src.models.question_sets import QuestionSet

    session_id = seed["session"].id

    resp = await async_client.delete(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 204

    assert db.query(AssessmentSession).filter_by(id=session_id).first() is None
    assert db.query(QuestionSet).filter_by(session_id=session_id).first() is None


@pytest.mark.asyncio
async def test_delete_session_removes_hiring_report_and_share(
    async_client, seed, user_token, db
):
    from src.models.clients import Client
    from src.models.hiring_reports import HiringReport
    from src.models.report_shares import ReportShare

    session_id = seed["session"].id
    org_id = seed["org"].id

    report = HiringReport(org_id=org_id, session_id=session_id)
    db.add(report)
    db.flush()

    client = Client(org_id=org_id, name="Bob Corp", email="bob@client.com", auth_method="magic_link")
    db.add(client)
    db.flush()

    share = ReportShare(
        org_id=org_id,
        hiring_report_id=report.id,
        client_id=client.id,
        shared_by=seed["admin"].id,
    )
    db.add(share)
    db.commit()
    share_id = share.id

    resp = await async_client.delete(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 204

    assert db.query(HiringReport).filter_by(session_id=session_id).first() is None
    assert db.query(ReportShare).filter_by(id=share_id).first() is None


@pytest.mark.asyncio
async def test_delete_session_removes_candidate_profile(
    async_client, seed, user_token, db
):
    from src.models.candidate_profiles import CandidateProfile

    session = seed["session"]

    profile = CandidateProfile(
        org_id=seed["org"].id,
        candidate_id=seed["candidate"].id,
        job_assessment_id=session.job_assessment_id,
    )
    db.add(profile)
    db.flush()
    session.candidate_profile_id = profile.id
    db.commit()
    profile_id = profile.id

    resp = await async_client.delete(
        f"/sessions/{session.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 204

    assert db.query(CandidateProfile).filter_by(id=profile_id).first() is None


@pytest.mark.asyncio
async def test_delete_session_keeps_candidate_profile_if_other_session_uses_it(
    async_client, seed, user_token, db
):
    from src.models.assessment_sessions import AssessmentSession
    from src.models.candidate_profiles import CandidateProfile

    session = seed["session"]

    profile = CandidateProfile(
        org_id=seed["org"].id,
        candidate_id=seed["candidate"].id,
        job_assessment_id=session.job_assessment_id,
    )
    db.add(profile)
    db.flush()
    session.candidate_profile_id = profile.id

    other_session = AssessmentSession(
        org_id=seed["org"].id,
        job_assessment_id=session.job_assessment_id,
        candidate_id=session.candidate_id,
        candidate_profile_id=profile.id,
        time_budget_seconds=3600,
    )
    db.add(other_session)
    db.commit()
    profile_id = profile.id

    resp = await async_client.delete(
        f"/sessions/{session.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 204

    assert db.query(CandidateProfile).filter_by(id=profile_id).first() is not None


@pytest.mark.asyncio
async def test_delete_session_requires_auth(async_client, seed):
    resp = await async_client.delete(f"/sessions/{seed['session'].id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_session_404_unknown(async_client, user_token):
    resp = await async_client.delete(
        f"/sessions/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404
