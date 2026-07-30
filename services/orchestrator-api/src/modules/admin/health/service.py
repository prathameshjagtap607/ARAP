import redis as redis_lib
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.health.schemas import (
    FraudFlagStats,
    HealthOverview,
    IncidentEntry,
)


def get_health_overview(db: Session, redis: redis_lib.Redis) -> HealthOverview:
    queue_depth = 0
    try:
        queue_depth = redis.llen("generation_queue") or 0
    except Exception:
        pass

    stats = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'error') AS error_count,
            PERCENTILE_CONT(0.50) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
            ) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL) AS p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
            ) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
            ) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL) AS p99
        FROM assessment_sessions
        WHERE invited_at >= NOW() - INTERVAL '24 hours'
    """)).mappings().first()

    total = int(stats["total"]) if stats["total"] else 0
    error_count = int(stats["error_count"]) if stats["error_count"] else 0

    return HealthOverview(
        queue_depth=int(queue_depth),
        error_rate_24h=error_count / total if total > 0 else 0.0,
        p50_seconds=float(stats["p50"]) if stats["p50"] is not None else None,
        p95_seconds=float(stats["p95"]) if stats["p95"] is not None else None,
        p99_seconds=float(stats["p99"]) if stats["p99"] is not None else None,
        total_sessions_24h=total,
    )


def get_incidents(db: Session) -> list[IncidentEntry]:
    rows = db.execute(text("""
        SELECT
            status,
            COUNT(*) AS count,
            MAX(invited_at)::text AS last_seen
        FROM assessment_sessions
        WHERE status = 'error'
          AND invited_at >= NOW() - INTERVAL '7 days'
        GROUP BY status
        ORDER BY count DESC
    """)).mappings().all()
    return [
        IncidentEntry(
            status=r["status"],
            count=int(r["count"]),
            last_seen=r["last_seen"],
        )
        for r in rows
    ]


def get_fraud_flag_stats(db: Session) -> FraudFlagStats:
    row = db.execute(text("""
        SELECT
            COUNT(DISTINCT f.id) AS total_flags,
            COUNT(DISTINCT f.id) FILTER (
                WHERE hr.verdict IN ('hire', 'strong_hire')
            ) AS false_positives
        FROM integrity_flags f
        JOIN assessment_sessions s ON s.id = f.session_id
        LEFT JOIN hiring_reports hr ON hr.session_id = f.session_id
    """)).mappings().first()

    total = int(row["total_flags"]) if row["total_flags"] else 0
    fp = int(row["false_positives"]) if row["false_positives"] else 0
    return FraudFlagStats(
        total_flags=total,
        false_positive_count=fp,
        false_positive_rate=fp / total if total > 0 else 0.0,
    )
