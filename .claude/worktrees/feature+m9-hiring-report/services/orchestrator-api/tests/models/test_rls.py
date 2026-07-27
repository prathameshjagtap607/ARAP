"""
RLS integration tests — require a migration-applied DB, not Base.metadata.create_all().
Run in isolation with: pytest tests/models/test_rls.py -v

These tests create two orgs and verify cross-org data leakage is impossible
when app.current_org_id is set correctly.

NOTE: These tests connect as a non-superuser role (arap_app) because PostgreSQL
superusers bypass RLS even with FORCE ROW LEVEL SECURITY. The module fixture
creates this role and grants it minimal table permissions.
"""
import uuid
import os
import pytest
from sqlalchemy import create_engine, text

# NOTE: RLS tests require the test DB on port 5434 to be running.
# Start it with: docker compose up -d  (from services/orchestrator-api/)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)

APP_ROLE = "arap_app"

_RLS_TABLES = [
    "users", "job_assessments", "candidates", "clients",
    "candidate_profiles", "assessment_sessions", "question_sets",
    "session_questions", "question_fingerprints", "behavior_profiles",
    "integrity_flags", "hiring_reports", "report_shares",
    "competency_library", "prompt_templates", "audit_logs",
]


def _ensure_rls(conn) -> None:
    """
    Re-apply RLS policies if they were wiped by the other conftest's
    Base.metadata.create_all() call (which does not run alembic migrations).
    This is a no-op when the migration-applied DB is used in isolation.
    """
    # Check if RLS is already active on the users table
    result = conn.execute(
        text("SELECT relrowsecurity FROM pg_class WHERE relname = 'users' AND relnamespace = 'public'::regnamespace")
    )
    row = result.fetchone()
    if row and row[0]:
        return  # RLS already enabled, nothing to do

    # RLS was disabled — re-apply all policies (mirrors migration 0001)
    for table in _RLS_TABLES:
        conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        # Drop existing policy if any (idempotent)
        conn.execute(text(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}"))
        if table == "prompt_templates":
            conn.execute(text(
                f"CREATE POLICY {table}_org_isolation ON {table} "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid "
                f"OR org_id IS NULL)"
            ))
        else:
            conn.execute(text(
                f"CREATE POLICY {table}_org_isolation ON {table} "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid)"
            ))
    # Re-apply audit_logs append-only guard
    conn.execute(text("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC"))
    conn.commit()


@pytest.fixture(scope="module")
def rls_engine():
    """
    Module-scoped engine connected as the superuser (arap).
    Ensures RLS policies are in place (re-applies them if wiped by create_all).
    Also creates the non-superuser app role used inside each RLS test.
    """
    eng = create_engine(TEST_DATABASE_URL, echo=False)
    with eng.connect() as conn:
        # Ensure RLS is active (idempotent if already applied by alembic)
        _ensure_rls(conn)

        # Create app role if it doesn't exist
        conn.execute(text(
            "DO $$ BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role) THEN "
            "    EXECUTE 'CREATE ROLE ' || quote_ident(:role) || ' NOLOGIN'; "
            "  END IF; "
            "END $$"
        ), {"role": APP_ROLE})
        # Grant SELECT + INSERT on all tables (covers what tests need).
        # Do NOT grant UPDATE/DELETE on audit_logs — the REVOKE from PUBLIC
        # already blocks non-superusers; explicit grants would re-open it.
        conn.execute(text(
            f"GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
        ))
        # Grant usage on schema
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
        conn.commit()
    yield eng
    eng.dispose()


def _insert_org(conn, name: str) -> uuid.UUID:
    """Insert an org as superuser (bypasses RLS) and return its id."""
    result = conn.execute(
        text("INSERT INTO orgs (name) VALUES (:name) RETURNING id"),
        {"name": name},
    )
    return result.fetchone()[0]


def _set_app_context(conn, org_id: uuid.UUID) -> None:
    """Set the RLS tenant context and switch to the non-superuser role."""
    conn.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    conn.execute(text("SET LOCAL app.current_org_id = :oid"), {"oid": str(org_id)})


def test_rls_isolates_users_by_org(rls_engine):
    """Org A's users must be invisible when the session belongs to Org B."""
    with rls_engine.connect() as conn:
        # Superuser setup: create orgs and a user in org_a
        with conn.begin():
            org_a = _insert_org(conn, f"RLS-OrgA-{uuid.uuid4()}")
            org_b = _insert_org(conn, f"RLS-OrgB-{uuid.uuid4()}")
            conn.execute(
                text(
                    "INSERT INTO users (org_id, email, role, password_hash) "
                    "VALUES (:o, :e, 'user', 'h')"
                ),
                {"o": str(org_a), "e": f"user-{uuid.uuid4()}@a.com"},
            )
            # commit so the non-superuser role can see the rows if RLS allows

        # RLS test: connect as app role for org_b — must NOT see org_a's user
        with conn.begin():
            _set_app_context(conn, org_b)
            rows = conn.execute(
                text("SELECT id FROM users WHERE org_id = :org_a"),
                {"org_a": str(org_a)},
            ).fetchall()
            assert rows == [], (
                f"RLS leak: org_b context can see {len(rows)} user(s) belonging to org_a"
            )
            # rollback so test data doesn't accumulate
            conn.rollback()

        # Clean up superuser data
        with conn.begin():
            conn.execute(text("DELETE FROM users WHERE org_id = :o"), {"o": str(org_a)})
            conn.execute(text("DELETE FROM orgs WHERE id IN (:a, :b)"), {"a": str(org_a), "b": str(org_b)})


def test_rls_prompt_templates_global_visible_to_all(rls_engine):
    """A prompt_template with org_id IS NULL must be visible to any org's context."""
    with rls_engine.connect() as conn:
        template_id = None
        with conn.begin():
            org_a = _insert_org(conn, f"PT-OrgA-{uuid.uuid4()}")
            result = conn.execute(
                text(
                    "INSERT INTO prompt_templates (org_id, agent_name, version, template_body) "
                    "VALUES (NULL, 'evaluation', :v, 'SYSTEM...') RETURNING id"
                ),
                {"v": f"v-{uuid.uuid4()}"},
            )
            template_id = result.fetchone()[0]

        # RLS test: as org_a, global template (org_id IS NULL) must be visible
        with conn.begin():
            _set_app_context(conn, org_a)
            rows = conn.execute(
                text("SELECT id FROM prompt_templates WHERE id = :tid"),
                {"tid": str(template_id)},
            ).fetchall()
            assert len(rows) == 1, (
                "Global prompt_template (org_id IS NULL) not visible through RLS policy"
            )
            conn.rollback()

        # Clean up
        with conn.begin():
            conn.execute(text("DELETE FROM prompt_templates WHERE id = :id"), {"id": str(template_id)})
            conn.execute(text("DELETE FROM orgs WHERE id = :id"), {"id": str(org_a)})


def test_audit_logs_update_denied(rls_engine):
    """INSERT to audit_logs must succeed; UPDATE must be denied for the app role."""
    from sqlalchemy.exc import ProgrammingError

    with rls_engine.connect() as conn:
        log_id = None
        with conn.begin():
            org = _insert_org(conn, f"AuditRLS-{uuid.uuid4()}")
            result = conn.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(org_id, actor_id, action, entity_type, entity_id) "
                    "VALUES (:o, gen_random_uuid(), 'test', 'orgs', gen_random_uuid()) "
                    "RETURNING id"
                ),
                {"o": str(org)},
            )
            log_id = result.fetchone()[0]

        # Verify app role can INSERT (reads back the row just inserted as superuser)
        with conn.begin():
            _set_app_context(conn, org)
            insert_result = conn.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(org_id, actor_id, action, entity_type, entity_id) "
                    "VALUES (:o, gen_random_uuid(), 'app_insert', 'orgs', gen_random_uuid()) "
                    "RETURNING id"
                ),
                {"o": str(org)},
            )
            assert insert_result.fetchone() is not None, "app role INSERT on audit_logs failed"
            conn.rollback()

        # Verify UPDATE is denied for the app role
        with pytest.raises(ProgrammingError, match="permission denied"):
            with conn.begin():
                _set_app_context(conn, org)
                conn.execute(
                    text("UPDATE audit_logs SET action = 'tampered' WHERE id = :id"),
                    {"id": str(log_id)},
                )

        # Clean up
        with conn.begin():
            conn.execute(text("DELETE FROM audit_logs WHERE org_id = :o"), {"o": str(org)})
            conn.execute(text("DELETE FROM orgs WHERE id = :id"), {"id": str(org)})
