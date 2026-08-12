import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_weightage(v: dict[str, float]) -> dict[str, float]:
    # Not used by question generation (pure DISC assessment — see
    # question_sets.service._derive_category_counts). Kept optional for
    # backward compatibility with any client still sending it; only
    # validated when non-empty.
    if v and abs(sum(v.values()) - 100) > 0.01:
        raise ValueError("competency_weightage must sum to 100")
    return v


class JobAssessmentCreate(BaseModel):
    title: str
    department: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: str | None = None
    education: str | None = None
    certifications: list[str] = []
    behavioral_competencies: list[str] = []
    leadership_competencies: list[str] = []
    culture_values: list[str] = []
    difficulty_level: Literal["junior", "mid", "senior", "executive"]
    duration_minutes: int = Field(gt=0)
    competency_weightage: dict[str, float] = {}
    is_template: bool = False
    role_family: str | None = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: dict[str, float]) -> dict[str, float]:
        return _validate_weightage(v)


class JobAssessmentUpdate(BaseModel):
    title: str | None = None
    department: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    responsibilities: str | None = None
    education: str | None = None
    certifications: list[str] | None = None
    behavioral_competencies: list[str] | None = None
    leadership_competencies: list[str] | None = None
    culture_values: list[str] | None = None
    difficulty_level: Literal["junior", "mid", "senior", "executive"] | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    competency_weightage: dict[str, float] | None = None
    is_template: bool | None = None
    role_family: str | None = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is not None:
            return _validate_weightage(v)
        return v


class InviteRequest(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    time_budget_seconds: int = Field(gt=0)


class InviteResponse(BaseModel):
    link: str
    email_sent: bool
    session_id: str
    candidate_id: str


class JobAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    department: str | None
    experience_min: int | None
    experience_max: int | None
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: str | None
    education: str | None
    certifications: list[str]
    behavioral_competencies: list[str]
    leadership_competencies: list[str]
    culture_values: list[str]
    difficulty_level: str
    duration_minutes: int
    competency_weightage: dict
    is_template: bool
    role_family: str | None
    job_profile: dict | None
    created_by: uuid.UUID
    created_at: datetime
