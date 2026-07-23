import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    plan_tier: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'trial'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_candidates_org_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    resume_file_url: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)
    github_url: Mapped[Optional[str]] = mapped_column(Text)
    portfolio_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobAssessment(Base):
    __tablename__ = "job_assessments"
    __table_args__ = (
        CheckConstraint(
            "difficulty_level IN ('junior','mid','senior','executive')",
            name="ck_job_assessments_difficulty_level",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    required_skills: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    preferred_skills: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    competency_weightage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    job_profile: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint("parsing_confidence BETWEEN 0 AND 1", name="ck_candidate_profiles_parsing_confidence"),
        CheckConstraint(
            "match_score IS NULL OR match_score BETWEEN 0 AND 1",
            name="ck_candidate_profiles_match_score",
        ),
        UniqueConstraint("candidate_id", "job_assessment_id", name="uq_candidate_profiles_candidate_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    job_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_assessments.id"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    skill_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    experience_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    leadership_level_estimate: Mapped[Optional[str]] = mapped_column(String)
    strengths: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    risk_flags: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    parsing_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    field_confidence: Mapped[Optional[dict]] = mapped_column(JSONB)
    match_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    github_enrichment: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
