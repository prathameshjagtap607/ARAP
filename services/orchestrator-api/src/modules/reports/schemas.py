import uuid
from datetime import datetime
from typing import Literal

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
    report_ready: bool
    requires_human_review: bool
    verdict: str | None
    ai_confidence_score: float | None
    salary_band: str | None
    full_report: dict
    reviewer_override: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class SharedReportResponse(BaseModel):
    session_id: uuid.UUID
    verdict: str | None
    executive_summary: str | None
    recommended_next_round: str | None
    full_report: dict
    requires_human_review: bool

    model_config = {"from_attributes": True}


class ReviewerFeedbackRequest(BaseModel):
    final_decision: Literal["hire", "no_hire", "hold"]
    comment: str
    score_overrides: dict[str, float] | None = None


class ReviewerFeedbackResponse(BaseModel):
    reviewer_override: dict


class ShareLinkRequest(BaseModel):
    client_id: uuid.UUID
    expires_in_days: int


class ShareLinkResponse(BaseModel):
    share_token: uuid.UUID
    expires_at: datetime


class ReportListItem(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    candidate_name: str
    job_title: str
    verdict: str | None
    overall_score: float | None
    disc_primary: str | None
    disc_confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    total_count: int
