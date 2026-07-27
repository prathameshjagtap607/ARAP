"""add full_report column to hiring_reports

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hiring_reports",
        sa.Column(
            "full_report",
            postgresql.JSONB(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("hiring_reports", "full_report")
