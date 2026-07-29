import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SynthesizeRequest(BaseModel):
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID


class CandidateProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    summary: str | None
    skill_matrix: dict
    experience_matrix: dict
    leadership_level_estimate: str | None
    strengths: list[str]
    risk_flags: list[str]
    parsing_confidence: float | None
    match_score: float | None
    created_at: datetime
