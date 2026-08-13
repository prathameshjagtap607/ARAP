"""session_questions: add ranking_order/reflection_text columns

DISC-Based Generative Leadership Question Framework — Question Formats
(spec section 7). Two of the 7 formats aren't answered by a single MCQ pick:
'ranking' (order all 4 options most-to-least-likely) and 'reflection' (a
free-text response). Purely additive, nullable columns: the existing
answer_text/answered_at columns keep capturing the candidate's single MCQ
pick exactly as before (still what drives DISC scoring for every question
regardless of format) — these new columns optionally capture the extra
ranking/reflection interaction for questions labeled with those formats,
without touching any existing data, column, or the scoring pipeline.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_questions",
        sa.Column("ranking_order", JSONB, nullable=True),
    )
    op.add_column(
        "session_questions",
        sa.Column("ranking_answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "session_questions",
        sa.Column("reflection_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "session_questions",
        sa.Column("reflection_answered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_questions", "reflection_answered_at")
    op.drop_column("session_questions", "reflection_text")
    op.drop_column("session_questions", "ranking_answered_at")
    op.drop_column("session_questions", "ranking_order")
