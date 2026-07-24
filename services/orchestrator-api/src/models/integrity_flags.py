import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IntegrityFlag(Base):
    __tablename__ = "integrity_flags"
    __table_args__ = (
        CheckConstraint(
            "flag_type IN ('ai_generated','duplicate_answer','resume_inconsistency','behavioral_anomaly')",
            name="ck_integrity_flags_flag_type",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high')",
            name="ck_integrity_flags_severity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    session_question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("session_questions.id"))
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
