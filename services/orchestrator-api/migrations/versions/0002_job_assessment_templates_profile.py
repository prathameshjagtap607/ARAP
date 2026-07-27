"""add is_template role_family job_profile to job_assessments

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_assessments",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "job_assessments",
        sa.Column("role_family", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_assessments",
        sa.Column("job_profile", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_assessments", "job_profile")
    op.drop_column("job_assessments", "role_family")
    op.drop_column("job_assessments", "is_template")
