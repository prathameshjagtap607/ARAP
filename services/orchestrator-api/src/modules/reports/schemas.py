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


class FullReportResponse(BaseModel):
    session_id: uuid.UUID
    verdict: str | None
    ai_confidence_score: float | None
    salary_band: str | None
    requires_human_review: bool
    full_report: dict

    model_config = {"from_attributes": True}


class ReviewerFeedbackRequest(BaseModel):
    final_decision: str
    comment: str | None = None
    score_overrides: dict[str, float] = {}


class ShareLinkRequest(BaseModel):
    client_id: uuid.UUID
    expires_in_days: int = 7


class ShareLinkResponse(BaseModel):
    share_token: uuid.UUID
    expires_at: datetime
