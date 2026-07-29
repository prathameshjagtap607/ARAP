"""add skill_trend_snapshots

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_text = sa.text


def upgrade() -> None:
    op.create_table(
        "skill_trend_snapshots",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("role_family", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("competency", sa.String(), nullable=False),
        sa.Column("avg_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_skill_trend_snapshots_org_week",
        "skill_trend_snapshots",
        ["org_id", sa.desc("week_start")],
    )


def downgrade() -> None:
    op.drop_index("ix_skill_trend_snapshots_org_week", table_name="skill_trend_snapshots")
    op.drop_table("skill_trend_snapshots")
