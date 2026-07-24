import uuid
from datetime import datetime
from typing import Optional

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
    summary: Optional[str]
    skill_matrix: dict
    experience_matrix: dict
    leadership_level_estimate: Optional[str]
    strengths: list[str]
    risk_flags: list[str]
    parsing_confidence: Optional[float]
    match_score: Optional[float]
    created_at: datetime
