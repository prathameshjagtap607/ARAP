import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.analytics.schemas import (
    BenchmarkResponse,
    FunnelResponse,
    FunnelRow,
    QuestionAnalyticsResponse,
    QuestionCategoryRow,
    ScoreTrendPoint,
    ScoreTrendsResponse,
    SkillTrendPoint,
    SkillTrendsResponse,
)


def get_score_trends(
    db: Session,
    org_id: uuid.UUID,
    dept: str | None,
    role: str | None,
    from_date: datetime,
    to_date: datetime,
    granularity: str = "week",
) -> ScoreTrendsResponse:
    overall_sql = text("""
        SELECT
            DATE_TRUNC(:granularity, s.completed_at) AS period,
            AVG((r.score_rollup->>'overall')::numeric) AS avg_overall,
            COUNT(*) AS session_count
        FROM assessment_sessions s
        JOIN hiring_reports r ON r.session_id = s.id
        JOIN job_assessments j ON j.id = s.job_assessment_id
        WHERE s.org_id = :org_id
          AND s.status = 'completed'
          AND (:dept IS NULL OR j.department = :dept)
          AND (:role IS NULL OR j.title = :role)
          AND s.completed_at BETWEEN :from_date AND :to_date
        GROUP BY 1
        ORDER BY 1
    """)

    comp_sql = text("""
        SELECT
            DATE_TRUNC(:granularity, s.completed_at) AS period,
            comp.key AS competency,
            AVG(comp.value::numeric) AS avg_score
        FROM assessment_sessions s
        JOIN hiring_reports r ON r.session_id = s.id
        JOIN job_assessments j ON j.id = s.job_assessment_id,
        LATERAL jsonb_each_text(r.score_rollup->'composite_scores') AS comp(key, value)
        WHERE s.org_id = :org_id
          AND s.status = 'completed'
          AND (:dept IS NULL OR j.department = :dept)
          AND (:role IS NULL OR j.title = :role)
          AND s.completed_at BETWEEN :from_date AND :to_date
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)

    params = {
        "org_id": org_id,
        "granularity": granularity,
        "dept": dept,
        "role": role,
        "from_date": from_date,
        "to_date": to_date,
    }

    overall_rows = db.execute(overall_sql, params).mappings().all()
    comp_rows = db.execute(comp_sql, params).mappings().all()

    # Build competency lookup: period -> {competency: avg_score}
    comp_by_period: dict[datetime, dict[str, float]] = {}
    for row in comp_rows:
        p = row["period"]
        comp_by_period.setdefault(p, {})[row["competency"]] = float(row["avg_score"])

    data = [
        ScoreTrendPoint(
            period=row["period"],
            avg_overall=float(row["avg_overall"]),
            avg_by_competency=comp_by_period.get(row["period"], {}),
            session_count=int(row["session_count"]),
        )
        for row in overall_rows
    ]

    return ScoreTrendsResponse(
        data=data,
        filters_applied={"dept": dept, "role": role, "granularity": granularity},
    )


def get_funnel(
    db: Session,
    org_id: uuid.UUID,
    dept: str | None,
    role: str | None,
    from_date: datetime,
    to_date: datetime,
) -> FunnelResponse:
    sql = text("""
        SELECT
            COALESCE(j.department, 'Unknown') AS department,
            j.title AS role,
            COUNT(*) AS total_invited,
            COUNT(*) FILTER (WHERE s.status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE r.verdict IN ('hire', 'strong_hire')) AS hired
        FROM assessment_sessions s
        JOIN job_assessments j ON j.id = s.job_assessment_id
        LEFT JOIN hiring_reports r ON r.session_id = s.id
        WHERE s.org_id = :org_id
          AND (:dept IS NULL OR j.department = :dept)
          AND (:role IS NULL OR j.title = :role)
          AND s.invited_at BETWEEN :from_date AND :to_date
        GROUP BY j.department, j.title
        ORDER BY total_invited DESC
    """)

    rows_raw = db.execute(sql, {
        "org_id": org_id,
        "dept": dept,
        "role": role,
        "from_date": from_date,
        "to_date": to_date,
    }).mappings().all()

    def make_row(department, role, total_invited, completed, hired) -> FunnelRow:
        return FunnelRow(
            department=department,
            role=role,
            total_invited=total_invited,
            completed=completed,
            hired=hired,
            completion_rate=completed / total_invited if total_invited else 0.0,
            hire_rate=hired / completed if completed else 0.0,
        )

    rows = [
        make_row(
            r["department"], r["role"],
            int(r["total_invited"]), int(r["completed"]), int(r["hired"])
        )
        for r in rows_raw
    ]

    if not rows:
        totals = FunnelRow(
            department="All", role="All",
            total_invited=0, completed=0, hired=0,
            completion_rate=0.0, hire_rate=0.0,
        )
    else:
        ti = sum(r.total_invited for r in rows)
        co = sum(r.completed for r in rows)
        hi = sum(r.hired for r in rows)
        totals = make_row("All", "All", ti, co, hi)

    return FunnelResponse(rows=rows, totals=totals)
