import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BehaviorProfile(Base):
    __tablename__ = "behavior_profiles"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_behavior_profiles_session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    disc_style: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    big_five: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    leadership_style: Mapped[Optional[str]] = mapped_column(String)
    decision_style: Mapped[Optional[str]] = mapped_column(String)
    communication_style: Mapped[Optional[str]] = mapped_column(String)
    work_style: Mapped[Optional[str]] = mapped_column(String)
    stress_signal: Mapped[Optional[str]] = mapped_column(String)
    eq_signal: Mapped[Optional[str]] = mapped_column(String)
    team_compatibility_signal: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
