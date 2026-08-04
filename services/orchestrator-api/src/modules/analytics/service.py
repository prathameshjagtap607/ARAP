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


def get_question_analytics(
    db: Session,
    org_id: uuid.UUID,
    job_assessment_id: uuid.UUID | None,
    from_date: datetime,
    to_date: datetime,
) -> QuestionAnalyticsResponse:
    sql = text("""
        SELECT
            sq.category,
            sq.difficulty,
            COUNT(*) AS question_count,
            AVG(CASE sq.difficulty
                WHEN 'easy'   THEN 1
                WHEN 'medium' THEN 2
                WHEN 'hard'   THEN 3
                WHEN 'expert' THEN 4
            END) AS avg_difficulty_num,
            AVG((r.score_rollup->>'overall')::numeric) AS avg_verdict_score
        FROM session_questions sq
        JOIN question_sets qs ON qs.id = sq.question_set_id
        JOIN assessment_sessions s ON s.id = qs.session_id
        LEFT JOIN hiring_reports r ON r.session_id = s.id
        WHERE sq.org_id = :org_id
          AND (:job_assessment_id IS NULL OR s.job_assessment_id = :job_assessment_id)
          AND s.completed_at BETWEEN :from_date AND :to_date
        GROUP BY sq.category, sq.difficulty
        ORDER BY sq.category, sq.difficulty
    """)

    rows = db.execute(sql, {
        "org_id": org_id,
        "job_assessment_id": job_assessment_id,
        "from_date": from_date,
        "to_date": to_date,
    }).mappings().all()

    return QuestionAnalyticsResponse(
        rows=[
            QuestionCategoryRow(
                category=r["category"],
                difficulty=r["difficulty"],
                question_count=int(r["question_count"]),
                avg_difficulty_num=float(r["avg_difficulty_num"]),
                avg_verdict_score=float(r["avg_verdict_score"]) if r["avg_verdict_score"] is not None else None,
            )
            for r in rows
        ]
    )


def get_benchmark(
    db: Session,
    org_id: uuid.UUID,
    session_id: uuid.UUID,
) -> BenchmarkResponse:
    check = text("""
        SELECT job_assessment_id FROM assessment_sessions
        WHERE id = :session_id AND org_id = :org_id AND status = 'completed'
    """)
    row = db.execute(check, {"session_id": session_id, "org_id": org_id}).mappings().first()
    if not row:
        raise LookupError("session not found or not completed")

    sql = text("""
        WITH scores AS (
            SELECT
                s.id AS session_id,
                (r.score_rollup->>'overall')::numeric AS overall_score
            FROM assessment_sessions s
            JOIN hiring_reports r ON r.session_id = s.id
            WHERE s.org_id = :org_id
              AND s.job_assessment_id = :job_assessment_id
              AND s.status = 'completed'
        ),
        agg AS (
            SELECT
                COUNT(*) AS peer_count,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY overall_score) AS p25,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY overall_score) AS p50,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY overall_score) AS p75
            FROM scores
        ),
        ranked AS (
            SELECT
                sc.session_id,
                sc.overall_score,
                PERCENT_RANK() OVER (ORDER BY sc.overall_score) AS percentile,
                agg.peer_count,
                agg.p25,
                agg.p50,
                agg.p75
            FROM scores sc, agg
        )
        SELECT * FROM ranked WHERE session_id = :session_id
    """)

    result = db.execute(sql, {
        "org_id": org_id,
        "job_assessment_id": row["job_assessment_id"],
        "session_id": session_id,
    }).mappings().first()

    if not result:
        raise LookupError("benchmark data not available for this session")

    return BenchmarkResponse(
        session_id=session_id,
        overall_score=float(result["overall_score"]),
        percentile=float(result["percentile"]),
        p25=float(result["p25"]),
        p50=float(result["p50"]),
        p75=float(result["p75"]),
        peer_count=int(result["peer_count"]),
    )


def get_skill_trends(
    db: Session,
    org_id: uuid.UUID,
    dept: str | None,
    role: str | None,
    from_date: datetime,
    to_date: datetime,
) -> SkillTrendsResponse:
    # Computed live from completed sessions' competency_scores (no separate
    # materialization job exists yet — snapshot table stays unused for now).
    sql = text("""
        SELECT
            DATE_TRUNC('week', s.completed_at)::date AS week_start,
            comp.key AS competency,
            AVG(comp.value::numeric) AS avg_score,
            COUNT(*) AS sample_count
        FROM assessment_sessions s
        JOIN hiring_reports r ON r.session_id = s.id
        JOIN job_assessments j ON j.id = s.job_assessment_id,
        LATERAL jsonb_each_text(COALESCE(r.score_rollup->'competency_scores', '{}'::jsonb)) AS comp(key, value)
        WHERE s.org_id = :org_id
          AND s.status = 'completed'
          AND (:dept IS NULL OR j.department = :dept)
          AND (:role IS NULL OR j.title = :role)
          AND s.completed_at BETWEEN :from_date AND :to_date
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)

    rows = db.execute(sql, {
        "org_id": org_id,
        "dept": dept,
        "role": role,
        "from_date": from_date,
        "to_date": to_date,
    }).mappings().all()

    data = [
        SkillTrendPoint(
            week_start=r["week_start"],
            competency=r["competency"],
            avg_score=float(r["avg_score"]),
            sample_count=int(r["sample_count"]),
        )
        for r in rows
    ]

    return SkillTrendsResponse(data=data, has_data=len(data) > 0)
