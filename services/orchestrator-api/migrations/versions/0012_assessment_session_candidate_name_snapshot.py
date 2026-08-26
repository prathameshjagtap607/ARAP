"""assessment_sessions.candidate_name: snapshot the name typed at invite time

candidates.name is shared per (org, email) and gets overwritten whenever the
same email is re-invited under a different name — so an older session's
displayed candidate name silently changes to whatever was typed on a later,
unrelated invite to the same email. Snapshotting the name onto the session
itself at invite time keeps each session's displayed name locked to what was
actually typed for that invite. Existing rows predate this snapshot, so they
are backfilled from the current candidates.name (the best available value —
there's no way to recover what was typed for a specific past invite).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assessment_sessions",
        sa.Column("candidate_name", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE assessment_sessions
        SET candidate_name = candidates.name
        FROM candidates
        WHERE assessment_sessions.candidate_id = candidates.id
          AND assessment_sessions.candidate_name IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("assessment_sessions", "candidate_name")
