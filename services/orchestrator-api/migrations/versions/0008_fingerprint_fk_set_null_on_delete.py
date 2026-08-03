"""question_fingerprints.question_set_id: ON DELETE SET NULL

Fingerprints must survive session/question_set deletion — they exist
specifically for the org-wide no-repeat-question guarantee (M4-F05),
which needs question history to persist even after a candidate's
session is deleted. Previously the FK had no ON DELETE action, so
Postgres defaulted to RESTRICT and blocked session deletion whenever
a question set had fingerprints.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-03
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "question_fingerprints_question_set_id_fkey",
        "question_fingerprints",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "question_fingerprints_question_set_id_fkey",
        "question_fingerprints",
        "question_sets",
        ["question_set_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "question_fingerprints_question_set_id_fkey",
        "question_fingerprints",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "question_fingerprints_question_set_id_fkey",
        "question_fingerprints",
        "question_sets",
        ["question_set_id"],
        ["id"],
    )
