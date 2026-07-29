from datetime import UTC, datetime, timedelta

import pytest

from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
from src.modules.analytics.service import (
    get_benchmark,
    get_funnel,
    get_question_analytics,
    get_score_trends,
    get_skill_trends,
)


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


class TestGetQuestionAnalytics:
    def test_returns_category_rows(self, db, analytics_seed):
        org_id = analytics_seed["org"].id
        sess = analytics_seed["sessions"][0]

        qs = QuestionSet(
            org_id=org_id,
            session_id=sess.id,
            generation_prompt_version="v1",
        )
        db.add(qs)
        db.flush()

        sq = SessionQuestion(
            org_id=org_id,
            question_set_id=qs.id,
            sequence_no=1,
            question={"text": "Describe a time..."},
            category="behavioral",
            target_competencies=["communication"],
            difficulty="medium",
            answer_format="long_text",
        )
        db.add(sq)
        db.commit()

        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_question_analytics(
            db, org_id,
            job_assessment_id=None,
            from_date=from_date,
            to_date=to_date,
        )

        assert len(result.rows) > 0
        assert result.rows[0].category == "behavioral"
        assert result.rows[0].question_count >= 1

    def test_org_isolation(self, db, analytics_seed):
        import uuid
        from_date = datetime.now(UTC) - timedelta(days=7)
        to_date = datetime.now(UTC) + timedelta(days=1)
        other_org_id = uuid.uuid4()

        result = get_question_analytics(
            db, other_org_id,
            job_assessment_id=None,
            from_date=from_date,
            to_date=to_date,
        )
        assert result.rows == []


class TestGetBenchmark:
    def test_returns_percentile_for_completed_session(self, db, analytics_seed):
        org_id = analytics_seed["org"].id
        session_id = analytics_seed["sessions"][0].id

        result = get_benchmark(db, org_id, session_id)

        assert result.session_id == session_id
        assert 0.0 <= result.percentile <= 1.0
        assert result.peer_count == 3
        assert result.overall_score > 0
        assert result.p25 <= result.p50 <= result.p75

    def test_raises_for_unknown_session(self, db, analytics_seed):
        import uuid
        with pytest.raises(LookupError):
            get_benchmark(db, analytics_seed["org"].id, uuid.uuid4())


class TestGetSkillTrends:
    def test_returns_empty_when_no_snapshots(self, db, analytics_seed):
        from_date = datetime.now(UTC) - timedelta(days=30)
        to_date = datetime.now(UTC) + timedelta(days=1)

        result = get_skill_trends(
            db, analytics_seed["org"].id,
            dept=None, role=None,
            from_date=from_date, to_date=to_date,
        )

        assert result.has_data is False
        assert result.data == []
