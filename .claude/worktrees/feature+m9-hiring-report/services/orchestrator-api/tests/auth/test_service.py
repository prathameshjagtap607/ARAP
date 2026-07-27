import uuid
from datetime import UTC, datetime, timedelta

import pytest
from passlib.context import CryptContext

from src.modules.auth import service as svc

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def test_login_user_success(db, seed):
    user = svc.login_user(db, "admin@test.com", "adminpass", seed["org"].id)
    assert user.email == "admin@test.com"
    assert user.role == "admin"


def test_login_user_wrong_password(db, seed):
    with pytest.raises(ValueError, match="invalid credentials"):
        svc.login_user(db, "admin@test.com", "wrongpass", seed["org"].id)


def test_login_user_not_found(db, seed):
    with pytest.raises(ValueError, match="invalid credentials"):
        svc.login_user(db, "nobody@test.com", "anything", seed["org"].id)


def test_login_user_wrong_org(db, seed):
    with pytest.raises(ValueError, match="invalid credentials"):
        svc.login_user(db, "admin@test.com", "adminpass", uuid.uuid4())


def test_login_failed_writes_audit(db, seed):
    from src.models.audit_logs import AuditLog
    with pytest.raises(ValueError):
        svc.login_user(db, "nobody@test.com", "x", seed["org"].id)
    row = db.query(AuditLog).filter_by(action="login_failed", org_id=seed["org"].id).first()
    assert row is not None
    assert row.log_metadata.get("email") == "nobody@test.com"


def test_request_candidate_token(db, seed):
    raw = svc.request_candidate_token(
        db, seed["candidate"].email, seed["org"].id, seed["session_a"].id
    )
    assert isinstance(raw, str) and len(raw) > 10
    db.refresh(seed["candidate"])
    assert seed["candidate"].login_token_hash is not None
    assert seed["candidate"].login_token_expires_at is not None


def test_request_candidate_token_wrong_email(db, seed):
    with pytest.raises(ValueError):
        svc.request_candidate_token(
            db, "wrong@email.com", seed["org"].id, seed["session_a"].id
        )


def test_verify_candidate_token_single_use(db, seed):
    raw = svc.request_candidate_token(
        db, seed["candidate"].email, seed["org"].id, seed["session_a"].id
    )
    candidate, session = svc.verify_candidate_token(db, raw, seed["session_a"].id)
    assert candidate.id == seed["candidate"].id
    # second use must fail
    with pytest.raises(ValueError, match="invalid or expired"):
        svc.verify_candidate_token(db, raw, seed["session_a"].id)


def test_verify_candidate_token_expired(db, seed):
    from src.models.candidates import Candidate
    from src.modules.auth.token import hash_login_token
    raw = "sometoken"
    seed["candidate"].login_token_hash = hash_login_token(raw)
    seed["candidate"].login_token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()
    with pytest.raises(ValueError, match="invalid or expired"):
        svc.verify_candidate_token(db, raw, seed["session_a"].id)


def test_request_client_token(db, seed):
    raw = svc.request_client_token(
        db, seed["client"].email, seed["org"].id, seed["share"].id
    )
    assert isinstance(raw, str)
    db.refresh(seed["client"])
    assert seed["client"].login_token_hash is not None


def test_verify_client_token_single_use(db, seed):
    raw = svc.request_client_token(
        db, seed["client"].email, seed["org"].id, seed["share"].id
    )
    client, share = svc.verify_client_token(db, raw, seed["share"].id)
    assert client.id == seed["client"].id
    with pytest.raises(ValueError, match="invalid or expired"):
        svc.verify_client_token(db, raw, seed["share"].id)
