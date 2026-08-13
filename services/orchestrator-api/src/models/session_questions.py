import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionQuestion(Base):
    __tablename__ = "session_questions"
    __table_args__ = (
        UniqueConstraint("question_set_id", "sequence_no", name="uq_session_questions_set_seq"),
        CheckConstraint(
            "difficulty IN ('easy','medium','hard','expert')",
            name="ck_session_questions_difficulty",
        ),
        CheckConstraint(
            "answer_format IN ('multiple_choice','short_text','long_text')",
            name="ck_session_questions_answer_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    question_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_sets.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[dict] = mapped_column(JSONB, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    target_competencies: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    answer_format: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    adaptive_answer_text: Mapped[str | None] = mapped_column(Text)
    adaptive_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ranking_order: Mapped[list | None] = mapped_column(JSONB)
    ranking_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reflection_text: Mapped[str | None] = mapped_column(Text)
    reflection_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluation: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
