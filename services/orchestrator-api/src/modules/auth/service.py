import uuid
from datetime import UTC, datetime, timedelta

from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config import settings
from src.models.assessment_sessions import AssessmentSession
from src.models.audit_logs import AuditLog
from src.models.candidates import Candidate
from src.models.clients import Client
from src.models.orgs import Org
from src.models.report_shares import ReportShare
from src.models.users import User
from src.modules.auth.token import NIL_UUID, generate_login_token, hash_login_token

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _set_rls(db: Session, org_id: uuid.UUID) -> None:
    db.execute(text(f"SET LOCAL app.current_org_id = '{org_id}'"))


def _write_audit(
    db: Session,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    log_metadata: dict | None = None,
) -> None:
    _set_rls(db, org_id)
    log = AuditLog(
        org_id=org_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        log_metadata=log_metadata or {},
    )
    db.add(log)
    db.flush()


def _try_write_audit(
    db: Session,
    org_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    log_metadata: dict | None = None,
) -> None:
    """Write audit using a savepoint so FK violations on unknown org_id are swallowed."""
    sp = db.begin_nested()
    try:
        _write_audit(db, org_id, actor_id, action, entity_type, entity_id, log_metadata)
        sp.commit()
    except Exception:
        sp.rollback()


def login_user(db: Session, email: str, password: str, org_id: uuid.UUID) -> User:
    org = db.query(Org).filter_by(id=org_id).first()
    if org and not org.is_active:
        raise PermissionError("organization is inactive")
    user = db.query(User).filter_by(org_id=org_id, email=email).first()
    if not user or not pwd_context.verify(password, user.password_hash):
        _try_write_audit(
            db, org_id, NIL_UUID, "login_failed", "user", NIL_UUID,
            {"email": email},
        )
        db.commit()
        raise ValueError("invalid credentials")
    _write_audit(db, org_id, user.id, "user_login", "user", user.id)
    db.commit()
    return user


def request_candidate_token(
    db: Session, email: str, org_id: uuid.UUID, session_id: uuid.UUID
) -> str:
    session = (
        db.query(AssessmentSession)
        .filter_by(id=session_id, org_id=org_id)
        .first()
    )
    if not session:
        raise ValueError("assessment session not found")
    if session.status in ("expired", "completed"):
        raise ValueError("session not available for login")
    candidate = (
        db.query(Candidate)
        .filter_by(id=session.candidate_id, email=email, org_id=org_id)
        .first()
    )
    if not candidate:
        raise ValueError("candidate not found")

    raw = generate_login_token()
    candidate.login_token_hash = hash_login_token(raw)
    candidate.login_token_expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.LOGIN_TOKEN_EXPIRE_MINUTES
    )
    _write_audit(
        db, org_id, candidate.id,
        "candidate_token_requested", "assessment_session", session_id,
    )
    db.commit()
    return raw


def verify_candidate_token(
    db: Session, token: str, session_id: uuid.UUID
) -> tuple[Candidate, AssessmentSession]:
    session = db.query(AssessmentSession).filter_by(id=session_id).first()
    if not session:
        raise ValueError("token invalid or expired")
    candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
    if not candidate:
        raise ValueError("token invalid or expired")

    now = datetime.now(UTC)
    expiry = candidate.login_token_expires_at
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)

    if (
        candidate.login_token_hash != hash_login_token(token)
        or expiry is None
        or expiry < now
    ):
        _write_audit(
            db, session.org_id, NIL_UUID, "login_failed", "candidate", NIL_UUID,
            {"session_id": str(session_id)},
        )
        db.commit()
        raise ValueError("token invalid or expired")

    candidate.login_token_hash = None
    candidate.login_token_expires_at = None
    _write_audit(
        db, session.org_id, candidate.id,
        "candidate_login", "assessment_session", session_id,
    )
    db.commit()
    return candidate, session


def request_client_token(
    db: Session, email: str, org_id: uuid.UUID, share_id: uuid.UUID
) -> str:
    share = db.query(ReportShare).filter_by(id=share_id, org_id=org_id).first()
    if not share:
        raise ValueError("report share not found")
    if share.revoked_at is not None:
        raise ValueError("report share has been revoked")
    now = datetime.now(UTC)
    if share.expires_at is not None:
        exp = share.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < now:
            raise ValueError("report share has expired")

    client = (
        db.query(Client)
        .filter_by(id=share.client_id, email=email, org_id=org_id)
        .first()
    )
    if not client:
        raise ValueError("client not found")

    raw = generate_login_token()
    client.login_token_hash = hash_login_token(raw)
    client.login_token_expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.LOGIN_TOKEN_EXPIRE_MINUTES
    )
    _write_audit(
        db, org_id, client.id,
        "client_token_requested", "report_share", share_id,
    )
    db.commit()
    return raw


def verify_client_token(
    db: Session, token: str, share_id: uuid.UUID
) -> tuple[Client, ReportShare]:
    share = db.query(ReportShare).filter_by(id=share_id).first()
    if not share:
        raise ValueError("token invalid or expired")
    client = db.query(Client).filter_by(id=share.client_id).first()
    if not client:
        raise ValueError("token invalid or expired")

    now = datetime.now(UTC)
    expiry = client.login_token_expires_at
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)

    if (
        client.login_token_hash != hash_login_token(token)
        or expiry is None
        or expiry < now
    ):
        _write_audit(
            db, share.org_id, NIL_UUID, "login_failed", "client", NIL_UUID,
            {"share_id": str(share_id)},
        )
        db.commit()
        raise ValueError("token invalid or expired")

    client.login_token_hash = None
    client.login_token_expires_at = None
    _write_audit(
        db, share.org_id, client.id,
        "client_login", "report_share", share_id,
    )
    db.commit()
    return client, share


def write_refresh_audit(db: Session, user_id: str, org_id: str) -> None:
    uid = uuid.UUID(user_id)
    oid = uuid.UUID(org_id)
    _write_audit(db, oid, uid, "token_refresh", "user", uid)
    db.commit()


def write_logout_audit(db: Session, claims: object) -> None:
    actor_id = uuid.UUID(claims.sub)
    org_id = claims.org_id
    _write_audit(db, org_id, actor_id, "logout", claims.role, actor_id)
    db.commit()
