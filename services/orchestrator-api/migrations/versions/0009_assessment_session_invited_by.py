"""assessment_sessions.invited_by: track which user invited the candidate

Needed for per-user data scoping — a "user" role account should only see
sessions/candidates/reports they personally invited, while "admin" keeps
seeing everything org-wide. Existing rows predate this tracking, so they
are backfilled from job_assessments.created_by (the one reliable ownership
signal that already existed) — each legacy session is attributed to
whoever created its job assessment.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_sessions",
        sa.Column("invited_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "assessment_sessions_invited_by_fkey",
        "assessment_sessions",
        "users",
        ["invited_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE assessment_sessions
        SET invited_by = job_assessments.created_by
        FROM job_assessments
        WHERE assessment_sessions.job_assessment_id = job_assessments.id
          AND assessment_sessions.invited_by IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "assessment_sessions_invited_by_fkey",
        "assessment_sessions",
        type_="foreignkey",
    )
    op.drop_column("assessment_sessions", "invited_by")
