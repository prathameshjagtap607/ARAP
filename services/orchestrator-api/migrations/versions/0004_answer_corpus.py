"""add answer_corpus table for duplicate answer detection

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_corpus",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("session_question_id", sa.UUID(), nullable=False),
        sa.Column("answer_embedding", Vector(1536), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["session_question_id"], ["session_questions.id"]),
        sa.UniqueConstraint(
            "session_question_id", name="uq_answer_corpus_session_question_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_answer_corpus_embedding",
        "answer_corpus",
        ["answer_embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"answer_embedding": "vector_cosine_ops"},
    )
    op.create_index("idx_answer_corpus_org_id", "answer_corpus", ["org_id"])
    op.execute(
        """
        ALTER TABLE answer_corpus ENABLE ROW LEVEL SECURITY;
        CREATE POLICY answer_corpus_org_isolation ON answer_corpus
            USING (org_id = current_setting('app.current_org_id')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS answer_corpus_org_isolation ON answer_corpus;")
    op.drop_index("idx_answer_corpus_org_id", table_name="answer_corpus")
    op.drop_index("idx_answer_corpus_embedding", table_name="answer_corpus")
    op.drop_table("answer_corpus")
