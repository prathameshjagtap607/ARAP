"""add field_confidence match_score github_enrichment to candidate_profiles

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("field_confidence", JSONB(), nullable=True),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("match_score", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("github_enrichment", JSONB(), nullable=True),
    )
    op.create_check_constraint(
        "ck_candidate_profiles_match_score",
        "candidate_profiles",
        "match_score IS NULL OR match_score BETWEEN 0 AND 1",
    )
    op.create_unique_constraint(
        "uq_candidate_profiles_candidate_job",
        "candidate_profiles",
        ["candidate_id", "job_assessment_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_candidate_profiles_candidate_job", "candidate_profiles", type_="unique")
    op.drop_constraint("ck_candidate_profiles_match_score", "candidate_profiles")
    op.drop_column("candidate_profiles", "github_enrichment")
    op.drop_column("candidate_profiles", "match_score")
    op.drop_column("candidate_profiles", "field_confidence")
