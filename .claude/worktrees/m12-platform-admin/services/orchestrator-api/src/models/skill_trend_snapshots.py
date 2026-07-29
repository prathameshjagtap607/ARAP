import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SkillTrendSnapshot(Base):
    __tablename__ = "skill_trend_snapshots"
    __table_args__ = (
        Index(
            "ix_skill_trend_snapshots_org_week",
            "org_id",
            text("week_start DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    role_family: Mapped[str | None] = mapped_column(String)
    department: Mapped[str | None] = mapped_column(String)
    competency: Mapped[str] = mapped_column(String, nullable=False)
    avg_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
