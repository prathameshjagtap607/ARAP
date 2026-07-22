import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
    func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobAssessment(Base):
    __tablename__ = "job_assessments"
    __table_args__ = (
        CheckConstraint(
            "difficulty_level IN ('junior','mid','senior','executive')",
            name="ck_job_assessments_difficulty_level",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String)
    experience_min: Mapped[Optional[int]] = mapped_column(Integer)
    experience_max: Mapped[Optional[int]] = mapped_column(Integer)
    required_skills: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    preferred_skills: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    responsibilities: Mapped[Optional[str]] = mapped_column(Text)
    education: Mapped[Optional[str]] = mapped_column(Text)
    certifications: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    behavioral_competencies: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    leadership_competencies: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    culture_values: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    competency_weightage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
