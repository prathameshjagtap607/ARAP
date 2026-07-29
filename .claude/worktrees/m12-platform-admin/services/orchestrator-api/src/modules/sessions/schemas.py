import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QuestionInSession(BaseModel):
    id: uuid.UUID
    sequence_no: int
    question: dict
    category: str
    target_competencies: list[str]
    difficulty: str
    answer_format: str
    options: dict | None
    answer_text: str | None
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class SessionStateResponse(BaseModel):
    id: uuid.UUID
    status: str
    seconds_remaining: int | None
    time_budget_seconds: int
    job_title: str
    duration_minutes: int
    questions: list[QuestionInSession]

    model_config = {"from_attributes": True}


class InviteResponse(BaseModel):
    link: str
    email_sent: bool


class StartResponse(BaseModel):
    status: str
    seconds_remaining: int | None


class AnswerRequest(BaseModel):
    answer_text: str


class AnswerResponse(BaseModel):
    id: uuid.UUID
    answer_text: str | None
    answered_at: datetime | None

    model_config = {"from_attributes": True}


class SubmitResponse(BaseModel):
    status: str
    completed_at: datetime | None


class SessionListItem(BaseModel):
    id: uuid.UUID
    candidate_email: str
    job_title: str
    status: str
    created_at: datetime
    started_at: datetime | None
    submitted_at: datetime | None

    model_config = {"from_attributes": True}


class CalibrationRequest(BaseModel):
    override_score: int = Field(..., ge=1, le=5)
    comment: str


class CalibrationResponse(BaseModel):
    override_score: int
    comment: str
    overridden_by: str
    overridden_at: str
