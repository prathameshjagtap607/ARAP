"""session_questions: add adaptive_answer_text/adaptive_answered_at columns

DISC-Based Generative Leadership Question Framework — Natural vs Adaptive
Behaviour mechanic (spec section 8). Purely additive, nullable columns: the
existing answer_text/answered_at columns keep capturing the candidate's
NATURAL response exactly as before; these new columns optionally capture a
second ADAPTIVE response ("what would be most effective, even if not your
natural choice?") to the same question, without touching any existing data
or column.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_questions",
        sa.Column("adaptive_answer_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "session_questions",
        sa.Column("adaptive_answered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_questions", "adaptive_answered_at")
    op.drop_column("session_questions", "adaptive_answer_text")
