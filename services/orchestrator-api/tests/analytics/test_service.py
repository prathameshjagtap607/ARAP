from datetime import UTC, datetime, timedelta

import pytest

from src.modules.analytics.service import get_funnel, get_score_trends


class TestGetScoreTrends:
    def test_returns_data_for_completed_sessions(self, db, analytics_seed):
        org_id = analytics_seed["org"].id
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_score_trends(
            db, org_id,
            dept=None, role=None,
            from_date=from_date, to_date=to_date,
            granularity="week",
        )

        assert len(result.data) > 0
        point = result.data[0]
        assert point.avg_overall > 0
        assert point.session_count == 3
        assert "problem_solving" in point.avg_by_competency
        assert "communication" in point.avg_by_competency

    def test_dept_filter_returns_empty_for_unknown_dept(self, db, analytics_seed):
        org_id = analytics_seed["org"].id
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_score_trends(
            db, org_id,
            dept="NonExistentDept", role=None,
            from_date=from_date, to_date=to_date,
            granularity="week",
        )

        assert result.data == []

    def test_org_isolation(self, db, analytics_seed):
        import uuid
        other_org_id = uuid.uuid4()
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_score_trends(
            db, other_org_id,
            dept=None, role=None,
            from_date=from_date, to_date=to_date,
            granularity="week",
        )

        assert result.data == []


class TestGetFunnel:
    def test_returns_funnel_rows(self, db, analytics_seed):
        org_id = analytics_seed["org"].id
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_funnel(
            db, org_id,
            dept=None, role=None,
            from_date=from_date, to_date=to_date,
        )

        assert len(result.rows) > 0
        row = result.rows[0]
        assert row.total_invited == 3
        assert row.completed == 3
        assert row.hired >= 1
        assert 0.0 <= row.completion_rate <= 1.0
        assert 0.0 <= row.hire_rate <= 1.0

    def test_totals_match_row_sum(self, db, analytics_seed):
        org_id = analytics_seed["org"].id
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_funnel(
            db, org_id,
            dept=None, role=None,
            from_date=from_date, to_date=to_date,
        )

        total_invited = sum(r.total_invited for r in result.rows)
        assert result.totals.total_invited == total_invited

    def test_org_isolation(self, db, analytics_seed):
        import uuid
        other_org_id = uuid.uuid4()
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_funnel(
            db, other_org_id,
            dept=None, role=None,
            from_date=from_date, to_date=to_date,
        )

        assert result.rows == []
