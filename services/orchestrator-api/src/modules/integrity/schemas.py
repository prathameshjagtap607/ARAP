import uuid
from datetime import datetime

from pydantic import BaseModel


class IntegrityFlagItem(BaseModel):
    id: uuid.UUID
    flag_type: str
    severity: str
    evidence: str
    session_question_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntegritySummaryResponse(BaseModel):
    session_id: uuid.UUID
    flagged_count: int
    overall_risk: str
    human_review_required: bool
    open_question: str | None
    flags: list[IntegrityFlagItem]
