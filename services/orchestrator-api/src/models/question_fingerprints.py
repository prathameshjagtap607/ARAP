import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

EMBEDDING_DIM = 1536


class QuestionFingerprint(Base):
    __tablename__ = "question_fingerprints"
    __table_args__ = (
        Index(
            "idx_question_fingerprints_embedding",
            "question_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"question_embedding": "vector_cosine_ops"},
        ),
        Index("idx_question_fingerprints_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    question_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_sets.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
