import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .question_fingerprints import EMBEDDING_DIM


class AnswerCorpus(Base):
    __tablename__ = "answer_corpus"
    __table_args__ = (
        UniqueConstraint("session_question_id", name="uq_answer_corpus_session_question_id"),
        Index(
            "idx_answer_corpus_embedding",
            "answer_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"answer_embedding": "vector_cosine_ops"},
        ),
        Index("idx_answer_corpus_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id"), nullable=False
    )
    session_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_questions.id"), nullable=False
    )
    answer_embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
