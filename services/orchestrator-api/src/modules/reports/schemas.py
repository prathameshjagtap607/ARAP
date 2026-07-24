import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportResponse(BaseModel):
    session_id: uuid.UUID
    report_ready: bool
    verdict: str | None
    executive_summary: str | None
    composite_scores: dict | None
    overall_score: float | None
    suggested_hr_questions: list[str]
    recommended_next_round: str | None
    training_needs: list[str]
    created_at: datetime | None

    model_config = {"from_attributes": True}
