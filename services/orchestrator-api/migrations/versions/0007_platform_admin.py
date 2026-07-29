"""platform admin: role constraint, orgs extensions, model_routing_configs, session traceability

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Expand role check constraint to include super_admin
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('user', 'admin', 'super_admin')",
    )

    # 2. Extend orgs
    op.add_column("orgs", sa.Column("workspace_limit", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("orgs", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("orgs", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))

    # 3. Add prompt traceability to assessment_sessions
    op.add_column(
        "assessment_sessions",
        sa.Column("prompt_template_id", UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_assessment_sessions_prompt_template_id",
        "assessment_sessions",
        "prompt_templates",
        ["prompt_template_id"],
        ["id"],
    )

    # 4. Create model_routing_configs
    op.create_table(
        "model_routing_configs",
        sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("fallback_provider", sa.String(), nullable=True),
        sa.Column("fallback_model_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("agent_name", name="uq_routing_agent"),
    )

    # 5. Seed default routing config for the three known agents
    op.execute(sa.text("""
        INSERT INTO model_routing_configs (agent_name, provider, model_id)
        VALUES
          ('question_generator', 'anthropic', 'claude-sonnet-5'),
          ('report_writer',      'anthropic', 'claude-sonnet-5'),
          ('scorer',             'anthropic', 'claude-haiku-4-5-20251001')
    """))


def downgrade() -> None:
    op.drop_table("model_routing_configs")
    op.drop_constraint("fk_assessment_sessions_prompt_template_id", "assessment_sessions", type_="foreignkey")
    op.drop_column("assessment_sessions", "prompt_template_id")
    op.drop_column("orgs", "suspended_at")
    op.drop_column("orgs", "is_active")
    op.drop_column("orgs", "workspace_limit")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('user', 'admin')"
    )
