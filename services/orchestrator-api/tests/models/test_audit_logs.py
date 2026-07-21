"""
audit_logs append-only test.

The REVOKE UPDATE, DELETE is applied by the Alembic migration — NOT by
Base.metadata.create_all(). Therefore, this test verifies only that:
  1. The table accepts INSERT.
  2. Rows inserted survive a flush.
The GRANT restriction is validated in test_rls.py after migration is run.
"""
import uuid
from src.models.orgs import Org
from src.models.audit_logs import AuditLog


def test_audit_log_insert(db):
    org = Org(name="AuditOrg")
    db.add(org)
    db.flush()

    log = AuditLog(
        org_id=org.id,
        actor_id=uuid.uuid4(),
        action="session.created",
        entity_type="assessment_session",
        entity_id=uuid.uuid4(),
        log_metadata={"ip": "127.0.0.1"},
    )
    db.add(log)
    db.flush()
    assert log.id is not None
    assert log.created_at is not None


def test_audit_log_metadata_defaults_empty(db):
    org = Org(name="AuditOrg2")
    db.add(org)
    db.flush()

    log = AuditLog(
        org_id=org.id,
        actor_id=uuid.uuid4(),
        action="report.viewed",
        entity_type="hiring_report",
        entity_id=uuid.uuid4(),
    )
    db.add(log)
    db.flush()
    # metadata defaults to {} at DB level; SQLAlchemy won't reflect the server default
    # until the row is expired and re-fetched
    db.expire(log)
    db.refresh(log)
    assert log.log_metadata == {}
