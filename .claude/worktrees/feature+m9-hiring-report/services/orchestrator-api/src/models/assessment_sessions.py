import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('invited','in_progress','completed','expired')",
            name="ck_assessment_sessions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    job_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_assessments.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    candidate_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("candidate_profiles.id"))
    status: Mapped[str] = mapped_column(nullable=False, server_default=text("'invited'"))
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_budget_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
