from pydantic import BaseModel


class HealthOverview(BaseModel):
    queue_depth: int
    error_rate_24h: float
    p50_seconds: float | None
    p95_seconds: float | None
    p99_seconds: float | None
    total_sessions_24h: int


class IncidentEntry(BaseModel):
    status: str
    count: int
    last_seen: str | None


class FraudFlagStats(BaseModel):
    total_flags: int
    false_positive_count: int
    false_positive_rate: float
