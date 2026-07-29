import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ScoreTrendPoint(BaseModel):
    period: datetime
    avg_overall: float
    avg_by_competency: dict[str, float]
    session_count: int


class ScoreTrendsResponse(BaseModel):
    data: list[ScoreTrendPoint]
    filters_applied: dict


class FunnelRow(BaseModel):
    department: str
    role: str
    total_invited: int
    completed: int
    hired: int
    completion_rate: float
    hire_rate: float


class FunnelResponse(BaseModel):
    rows: list[FunnelRow]
    totals: FunnelRow


class QuestionCategoryRow(BaseModel):
    category: str
    difficulty: str
    question_count: int
    avg_difficulty_num: float
    avg_verdict_score: float | None


class QuestionAnalyticsResponse(BaseModel):
    rows: list[QuestionCategoryRow]


class BenchmarkResponse(BaseModel):
    session_id: uuid.UUID
    overall_score: float
    percentile: float
    p25: float
    p50: float
    p75: float
    peer_count: int


class SkillTrendPoint(BaseModel):
    week_start: date
    competency: str
    avg_score: float
    sample_count: int


class SkillTrendsResponse(BaseModel):
    data: list[SkillTrendPoint]
    has_data: bool
