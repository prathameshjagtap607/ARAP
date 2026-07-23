import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


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

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
