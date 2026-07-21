"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_RLS_TABLES = [
    "users", "job_assessments", "candidates", "clients",
    "candidate_profiles", "assessment_sessions", "question_sets",
    "session_questions", "question_fingerprints", "behavior_profiles",
    "integrity_flags", "hiring_reports", "report_shares",
    "competency_library", "prompt_templates", "audit_logs",
]

_text = sa.text


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── orgs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "orgs",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("plan_tier", sa.Text(), nullable=False, server_default=_text("'trial'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    # ── job_assessments ───────────────────────────────────────────────────────
    op.create_table(
        "job_assessments",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("department", sa.Text()),
        sa.Column("experience_min", sa.Integer()),
        sa.Column("experience_max", sa.Integer()),
        sa.Column("required_skills", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("preferred_skills", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("responsibilities", sa.Text()),
        sa.Column("education", sa.Text()),
        sa.Column("certifications", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("behavioral_competencies", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("leadership_competencies", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("culture_values", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("difficulty_level", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("competency_weightage", JSONB(), nullable=False),
        sa.Column("created_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "difficulty_level IN ('junior','mid','senior','executive')",
            name="ck_job_assessments_difficulty_level",
        ),
    )

    # ── competency_library ────────────────────────────────────────────────────
    op.create_table(
        "competency_library",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("rubric_notes", sa.Text()),
        sa.Column("created_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "name", name="uq_competency_library_org_name"),
    )

    # ── candidates ────────────────────────────────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("resume_file_url", sa.Text()),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("github_url", sa.Text()),
        sa.Column("portfolio_url", sa.Text()),
        sa.Column("auth_method", sa.Text()),
        sa.Column("password_hash", sa.Text()),
        sa.Column("login_token_hash", sa.Text()),
        sa.Column("login_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "email", name="uq_candidates_org_email"),
        sa.CheckConstraint(
            "auth_method IS NULL OR auth_method IN ('magic_link','otp','password')",
            name="ck_candidates_auth_method",
        ),
    )

    # ── clients ───────────────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("auth_method", sa.Text()),
        sa.Column("password_hash", sa.Text()),
        sa.Column("login_token_hash", sa.Text()),
        sa.Column("login_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "email", name="uq_clients_org_email"),
        sa.CheckConstraint(
            "auth_method IS NULL OR auth_method IN ('magic_link','otp','password')",
            name="ck_clients_auth_method",
        ),
    )

    # ── candidate_profiles ────────────────────────────────────────────────────
    op.create_table(
        "candidate_profiles",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("candidate_id", UUID(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("job_assessment_id", UUID(), sa.ForeignKey("job_assessments.id"), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("skill_matrix", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("experience_matrix", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("leadership_level_estimate", sa.Text()),
        sa.Column("strengths", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("risk_flags", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("parsing_confidence", sa.Numeric(4, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("parsing_confidence BETWEEN 0 AND 1", name="ck_candidate_profiles_parsing_confidence"),
    )

    # ── assessment_sessions ───────────────────────────────────────────────────
    op.create_table(
        "assessment_sessions",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("job_assessment_id", UUID(), sa.ForeignKey("job_assessments.id"), nullable=False),
        sa.Column("candidate_id", UUID(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("candidate_profile_id", UUID(), sa.ForeignKey("candidate_profiles.id")),
        sa.Column("status", sa.Text(), nullable=False, server_default=_text("'invited'")),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("time_budget_seconds", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('invited','in_progress','completed','expired')",
            name="ck_assessment_sessions_status",
        ),
    )

    # ── question_sets ─────────────────────────────────────────────────────────
    op.create_table(
        "question_sets",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("generation_prompt_version", sa.Text(), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_question_sets_session_id"),
    )

    # ── session_questions ─────────────────────────────────────────────────────
    op.create_table(
        "session_questions",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("question_set_id", UUID(), sa.ForeignKey("question_sets.id"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("question", JSONB(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("target_competencies", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("difficulty", sa.Text(), nullable=False),
        sa.Column("answer_format", sa.Text(), nullable=False),
        sa.Column("options", JSONB()),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("evaluation", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("question_set_id", "sequence_no", name="uq_session_questions_set_seq"),
        sa.CheckConstraint(
            "difficulty IN ('easy','medium','hard','expert')",
            name="ck_session_questions_difficulty",
        ),
        sa.CheckConstraint(
            "answer_format IN ('multiple_choice','short_text','long_text')",
            name="ck_session_questions_answer_format",
        ),
    )

    # ── question_fingerprints ─────────────────────────────────────────────────
    op.create_table(
        "question_fingerprints",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_embedding", sa.Text(), nullable=False),  # DDL overridden below
        sa.Column("question_set_id", UUID(), sa.ForeignKey("question_sets.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Alter the column to the actual vector type (Alembic can't express vector natively)
    op.execute("ALTER TABLE question_fingerprints ALTER COLUMN question_embedding TYPE vector(1536) USING question_embedding::vector")
    op.execute(
        "CREATE INDEX idx_question_fingerprints_embedding "
        "ON question_fingerprints "
        "USING hnsw (question_embedding vector_cosine_ops) "
        "WITH (m=16, ef_construction=64)"
    )
    op.execute("CREATE INDEX idx_question_fingerprints_org_id ON question_fingerprints (org_id)")

    # ── behavior_profiles ─────────────────────────────────────────────────────
    op.create_table(
        "behavior_profiles",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("disc_style", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("big_five", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("leadership_style", sa.Text()),
        sa.Column("decision_style", sa.Text()),
        sa.Column("communication_style", sa.Text()),
        sa.Column("work_style", sa.Text()),
        sa.Column("stress_signal", sa.Text()),
        sa.Column("eq_signal", sa.Text()),
        sa.Column("team_compatibility_signal", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", name="uq_behavior_profiles_session_id"),
    )

    # ── integrity_flags ───────────────────────────────────────────────────────
    op.create_table(
        "integrity_flags",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("session_question_id", UUID(), sa.ForeignKey("session_questions.id")),
        sa.Column("flag_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "flag_type IN ('ai_generated','duplicate_answer','resume_inconsistency','behavioral_anomaly')",
            name="ck_integrity_flags_flag_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high')",
            name="ck_integrity_flags_severity",
        ),
    )

    # ── hiring_reports ────────────────────────────────────────────────────────
    op.create_table(
        "hiring_reports",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("executive_summary", sa.Text()),
        sa.Column("score_rollup", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("behavior_profile_id", UUID(), sa.ForeignKey("behavior_profiles.id")),
        sa.Column("integrity_summary", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("salary_band", sa.Text()),
        sa.Column("verdict", sa.Text()),
        sa.Column("ai_confidence_score", sa.Numeric(5, 2)),
        sa.Column("recommended_next_round", sa.Text()),
        sa.Column("training_needs", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("suggested_hr_questions", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("suggested_ceo_questions", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("reviewer_override", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", name="uq_hiring_reports_session_id"),
        sa.CheckConstraint(
            "verdict IS NULL OR verdict IN ('strong_hire','hire','consider','borderline','reject')",
            name="ck_hiring_reports_verdict",
        ),
        sa.CheckConstraint(
            "ai_confidence_score IS NULL OR (ai_confidence_score >= 0 AND ai_confidence_score <= 100)",
            name="ck_hiring_reports_ai_confidence",
        ),
    )

    # ── report_shares ─────────────────────────────────────────────────────────
    op.create_table(
        "report_shares",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("hiring_report_id", UUID(), sa.ForeignKey("hiring_reports.id"), nullable=False),
        sa.Column("client_id", UUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("shared_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── prompt_templates ──────────────────────────────────────────────────────
    op.create_table(
        "prompt_templates",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id")),  # nullable — NULL = global
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=_text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "agent_name", "version", name="uq_prompt_templates_org_agent_version"),
    )

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("actor_id", UUID(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── RLS ───────────────────────────────────────────────────────────────────
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        if table == "prompt_templates":
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid "
                f"OR org_id IS NULL)"
            )
        else:
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid)"
            )

    # ── audit_logs append-only ────────────────────────────────────────────────
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON audit_logs TO PUBLIC")  # undo REVOKE guard

    for table in reversed(_RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS idx_question_fingerprints_org_id")
    op.execute("DROP INDEX IF EXISTS idx_question_fingerprints_embedding")

    for table in [
        "audit_logs", "prompt_templates", "report_shares", "hiring_reports",
        "integrity_flags", "behavior_profiles", "question_fingerprints",
        "session_questions", "question_sets", "assessment_sessions",
        "candidate_profiles", "clients", "candidates",
        "competency_library", "job_assessments", "users", "orgs",
    ]:
        op.drop_table(table)

    op.execute("DROP EXTENSION IF EXISTS vector")
