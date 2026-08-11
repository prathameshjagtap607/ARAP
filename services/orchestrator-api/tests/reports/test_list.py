import pytest


@pytest.mark.anyio
async def test_list_reports_returns_only_reports_with_data(
    async_client, report_seed, user_token, db
):
    from src.models.hiring_reports import HiringReport

    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"composite_scores": {"Technical": 4.0}, "overall": 4.2},
        verdict="hire",
        executive_summary="Excellent candidate.",
    )
    db.add(report)
    db.commit()

    resp = await async_client.get(
        "/reports",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    item = body["items"][0]
    assert item["candidate_name"] == "Bob"
    assert item["job_title"] == "Product Manager"
    assert item["verdict"] == "hire"
    assert item["overall_score"] == pytest.approx(4.2)


@pytest.mark.anyio
async def test_list_reports_filters_by_verdict(async_client, report_seed, user_token, db):
    from src.models.hiring_reports import HiringReport

    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"overall": 2.0},
        verdict="reject",
    )
    db.add(report)
    db.commit()

    resp = await async_client.get(
        "/reports?verdict=hire",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 0


@pytest.mark.anyio
async def test_list_reports_awaiting_review_excludes_reviewed(
    async_client, report_seed, user_token, db
):
    from src.models.hiring_reports import HiringReport

    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"overall": 3.5},
        verdict="consider",
        reviewer_override={"final_decision": "hire"},
    )
    db.add(report)
    db.commit()

    resp = await async_client.get(
        "/reports?status=awaiting_review",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 0


@pytest.mark.anyio
async def test_list_reports_filters_by_multiple_disc_categories(
    async_client, report_seed, user_token, db
):
    from src.models.hiring_reports import HiringReport

    report_i = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        full_report={"disc_profile": {"primary": "I", "confidence": 0.7}},
    )
    db.add(report_i)
    db.commit()

    resp = await async_client.get(
        "/reports?disc_category=I&disc_category=S",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 1

    resp = await async_client.get(
        "/reports?disc_category=C&disc_category=S",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 0


@pytest.mark.anyio
async def test_list_reports_filters_by_disc_confidence_band(
    async_client, report_seed, user_token, db
):
    from src.models.hiring_reports import HiringReport

    high_confidence = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        full_report={"disc_profile": {"primary": "D", "confidence": 0.9}},
    )
    db.add(high_confidence)
    db.commit()

    resp = await async_client.get(
        "/reports?disc_confidence_band=60-79%25",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 0

    resp = await async_client.get(
        "/reports?disc_confidence_band=80-100%25",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 1


@pytest.mark.anyio
async def test_list_reports_requires_auth(async_client, report_seed):
    resp = await async_client.get("/reports")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_list_reports_filters_by_date_range(async_client, report_seed, user_token, db):
    from datetime import UTC, datetime, timedelta

    from src.models.hiring_reports import HiringReport

    old_report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"overall": 3.0},
        verdict="consider",
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add(old_report)
    db.commit()

    date_from = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    resp = await async_client.get(
        f"/reports?date_from={date_from}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_count"] == 0
