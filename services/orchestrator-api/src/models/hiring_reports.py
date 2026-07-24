import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class HiringReport(Base):
    __tablename__ = "hiring_reports"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_hiring_reports_session_id"),
        CheckConstraint(
            "verdict IS NULL OR verdict IN ('strong_hire','hire','consider','borderline','reject')",
            name="ck_hiring_reports_verdict",
        ),
        CheckConstraint(
            "ai_confidence_score IS NULL OR (ai_confidence_score >= 0 AND ai_confidence_score <= 100)",
            name="ck_hiring_reports_ai_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    executive_summary: Mapped[str | None] = mapped_column(Text)
    score_rollup: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    behavior_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("behavior_profiles.id"))
    integrity_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    salary_band: Mapped[str | None] = mapped_column(String)
    verdict: Mapped[str | None] = mapped_column(String)
    ai_confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    recommended_next_round: Mapped[str | None] = mapped_column(Text)
    training_needs: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    suggested_hr_questions: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    suggested_ceo_questions: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    reviewer_override: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
