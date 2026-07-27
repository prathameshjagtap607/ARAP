import pytest


@pytest.mark.anyio
async def test_get_report_not_ready(async_client, report_seed, user_token):
    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_ready"] is False
    assert data["verdict"] is None


@pytest.mark.anyio
async def test_get_report_returns_data(async_client, report_seed, user_token, db):
    from src.models.hiring_reports import HiringReport
    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"composite_scores": {"Technical": 4.0}, "overall": 4.0},
        verdict="hire",
        executive_summary="Excellent candidate.",
    )
    db.add(report)
    db.commit()

    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_ready"] is True
    assert data["verdict"] == "hire"
    assert data["overall_score"] == pytest.approx(4.0)


@pytest.mark.anyio
async def test_get_report_requires_auth(async_client, report_seed):
    resp = await async_client.get(f"/reports/{report_seed['session'].id}")
    assert resp.status_code == 401
