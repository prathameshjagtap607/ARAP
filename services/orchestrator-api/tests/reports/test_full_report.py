"""
Integration tests for new M9 hiring-report endpoints:
  GET  /reports/{session_id}/full
  GET  /reports/{session_id}/pdf
  POST /reports/{session_id}/share
  GET  /reports/shared/{token}          (public — no JWT)
  PATCH /reports/{session_id}/feedback
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from src.models.clients import Client
from src.models.hiring_reports import HiringReport
from src.models.report_shares import ReportShare

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _make_report(db, seed: dict, full_report: dict | None = _SENTINEL) -> HiringReport:  # type: ignore[assignment]
    if full_report is _SENTINEL:
        full_report = {"summary": "detailed report content"}
    report = HiringReport(
        org_id=seed["org"].id,
        session_id=seed["session"].id,
        verdict="hire",
        ai_confidence_score=82.5,
        salary_band="$90k–$110k",
        executive_summary="Strong candidate with solid technical skills.",
        score_rollup={"composite_scores": {"Technical": 4.2, "Communication": 3.8}, "overall": 4.0},
        integrity_summary={
            "overall_risk": "low",
            "human_review_required": False,
            "flagged_signals": ["minor_hesitation"],
        },
        full_report=full_report,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _make_client(db, seed: dict) -> Client:
    uid = uuid.uuid4().hex[:6]
    client = Client(
        org_id=seed["org"].id,
        name=f"Test Client {uid}",
        email=f"client-{uid}@example.com",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


# ---------------------------------------------------------------------------
# GET /reports/{session_id}/full  — 200
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_full_report_200(async_client, report_seed, user_token, db):
    _make_report(db, report_seed)

    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}/full",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_ready"] is True
    assert data["verdict"] == "hire"
    assert data["ai_confidence_score"] == pytest.approx(82.5)
    assert data["salary_band"] == "$90k–$110k"
    assert "summary" in data["full_report"]
    assert data["requires_human_review"] is False


# ---------------------------------------------------------------------------
# GET /reports/{session_id}/full  — 404 when no report row
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_full_report_404_no_row(async_client, report_seed, user_token):
    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}/full",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /reports/{session_id}/full  — 404 when full_report is empty dict
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_full_report_404_empty_full_report(async_client, report_seed, user_token, db):
    _make_report(db, report_seed, full_report={})

    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}/full",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /reports/{session_id}/pdf  — 200 with mocked render_pdf
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_pdf_200(async_client, report_seed, user_token, db):
    _make_report(db, report_seed)

    fake_pdf = b"%PDF-fake-content"
    with patch("src.modules.reports.service.get_pdf_bytes", return_value=fake_pdf):
        resp = await async_client.get(
            f"/reports/{report_seed['session'].id}/pdf",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# POST /reports/{session_id}/share  — 200
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_share_link_200(async_client, report_seed, user_token, db):
    _make_report(db, report_seed)
    client = _make_client(db, report_seed)

    resp = await async_client.post(
        f"/reports/{report_seed['session'].id}/share",
        json={"client_id": str(client.id), "expires_in_days": 7},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert "expires_at" in data


# ---------------------------------------------------------------------------
# POST /reports/{session_id}/share  — 403 client from wrong org
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_share_link_403_wrong_org(async_client, report_seed, user_token, db):
    from src.models.orgs import Org

    _make_report(db, report_seed)
    other_org = Org(name="Other Org")
    db.add(other_org)
    db.flush()
    foreign_client = Client(
        org_id=other_org.id,
        name="Foreign Client",
        email="foreign@other.com",
    )
    db.add(foreign_client)
    db.commit()

    resp = await async_client.post(
        f"/reports/{report_seed['session'].id}/share",
        json={"client_id": str(foreign_client.id), "expires_in_days": 7},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /reports/shared/{token}  — expired share → 403
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_shared_report_expired_403(async_client, report_seed, db):
    report = _make_report(db, report_seed)
    client = _make_client(db, report_seed)

    share = ReportShare(
        org_id=report_seed["org"].id,
        hiring_report_id=report.id,
        client_id=client.id,
        shared_by=report_seed["admin"].id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    resp = await async_client.get(f"/reports/shared/{share.id}")
    assert resp.status_code == 403
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /reports/shared/{token}  — revoked share → 403
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_shared_report_revoked_403(async_client, report_seed, db):
    report = _make_report(db, report_seed)
    client = _make_client(db, report_seed)

    share = ReportShare(
        org_id=report_seed["org"].id,
        hiring_report_id=report.id,
        client_id=client.id,
        shared_by=report_seed["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    resp = await async_client.get(f"/reports/shared/{share.id}")
    assert resp.status_code == 403
    assert "revoked" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /reports/shared/{token}  — valid share → 200 with masked integrity
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_shared_report_200_integrity_masked(async_client, report_seed, db):
    report = _make_report(db, report_seed)
    client = _make_client(db, report_seed)

    share = ReportShare(
        org_id=report_seed["org"].id,
        hiring_report_id=report.id,
        client_id=client.id,
        shared_by=report_seed["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    resp = await async_client.get(f"/reports/shared/{share.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "hire"
    # integrity detail must be masked — only these two keys allowed
    integrity = data["full_report"].get("integrity_summary", {})
    assert set(integrity.keys()) <= {"overall_risk", "human_review_required"}
    assert "flagged_signals" not in integrity


# ---------------------------------------------------------------------------
# PATCH /reports/{session_id}/feedback  — discrepancy_flag set when AI=hire, decision=no_hire
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_feedback_discrepancy_flag(async_client, report_seed, user_token, db):
    _make_report(db, report_seed)  # verdict = "hire"

    resp = await async_client.patch(
        f"/reports/{report_seed['session'].id}/feedback",
        json={
            "final_decision": "no_hire",
            "comment": "Does not meet culture fit requirements.",
            "score_overrides": {"Communication": 2.5},
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    override = data["reviewer_override"]
    assert override["discrepancy_flag"] is True
    assert override["final_decision"] == "no_hire"
    assert override["score_overrides"]["Communication"] == pytest.approx(2.5)
    assert "submitted_at" in override
    assert "submitted_by" in override


# ---------------------------------------------------------------------------
# PATCH /reports/{session_id}/feedback  — no discrepancy when verdicts agree
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_feedback_no_discrepancy(async_client, report_seed, user_token, db):
    _make_report(db, report_seed)  # verdict = "hire"

    resp = await async_client.patch(
        f"/reports/{report_seed['session'].id}/feedback",
        json={
            "final_decision": "hire",
            "comment": "Agree with AI assessment.",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    override = resp.json()["reviewer_override"]
    assert override["discrepancy_flag"] is False
