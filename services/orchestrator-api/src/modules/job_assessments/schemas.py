import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_weightage(v: dict[str, float]) -> dict[str, float]:
    if v and abs(sum(v.values()) - 100) > 0.01:
        raise ValueError("competency_weightage must sum to 100")
    return v


class JobAssessmentCreate(BaseModel):
    title: str
    department: Optional[str] = None
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: Optional[str] = None
    education: Optional[str] = None
    certifications: list[str] = []
    behavioral_competencies: list[str] = []
    leadership_competencies: list[str] = []
    culture_values: list[str] = []
    difficulty_level: Literal["junior", "mid", "senior", "executive"]
    duration_minutes: int
    competency_weightage: dict[str, float]
    is_template: bool = False
    role_family: Optional[str] = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: dict[str, float]) -> dict[str, float]:
        return _validate_weightage(v)


class JobAssessmentUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    responsibilities: Optional[str] = None
    education: Optional[str] = None
    certifications: Optional[list[str]] = None
    behavioral_competencies: Optional[list[str]] = None
    leadership_competencies: Optional[list[str]] = None
    culture_values: Optional[list[str]] = None
    difficulty_level: Optional[Literal["junior", "mid", "senior", "executive"]] = None
    duration_minutes: Optional[int] = None
    competency_weightage: Optional[dict[str, float]] = None
    is_template: Optional[bool] = None
    role_family: Optional[str] = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if v is not None:
            return _validate_weightage(v)
        return v


class CloneRequest(BaseModel):
    competency_weightage: Optional[dict[str, float]] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    role_family: Optional[str] = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if v is not None:
            return _validate_weightage(v)
        return v


class InviteRequest(BaseModel):
    candidate_name: str
    candidate_email: str
    time_budget_seconds: int


class InviteResponse(BaseModel):
    assessment_session_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str


class JobAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    department: Optional[str]
    experience_min: Optional[int]
    experience_max: Optional[int]
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: Optional[str]
    education: Optional[str]
    certifications: list[str]
    behavioral_competencies: list[str]
    leadership_competencies: list[str]
    culture_values: list[str]
    difficulty_level: str
    duration_minutes: int
    competency_weightage: dict
    is_template: bool
    role_family: Optional[str]
    job_profile: Optional[dict]
    created_by: uuid.UUID
    created_at: datetime
