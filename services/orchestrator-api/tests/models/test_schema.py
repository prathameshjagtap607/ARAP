import uuid
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.models.orgs import Org
from src.models.users import User


# ── Org ──────────────────────────────────────────────────────────────────────

def test_orgs_table_exists(engine):
    assert "orgs" in inspect(engine).get_table_names()


def test_orgs_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("orgs")}
    assert cols == {"id", "name", "plan_tier", "created_at"}


def test_org_insert_and_defaults(db):
    org = Org(name="Acme Corp")
    db.add(org)
    db.flush()
    assert org.id is not None
    assert org.plan_tier == "trial"
    assert org.created_at is not None


# ── User ─────────────────────────────────────────────────────────────────────

def test_users_table_exists(engine):
    assert "users" in inspect(engine).get_table_names()


def test_users_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    assert cols == {"id", "org_id", "email", "role", "password_hash", "created_at"}


def test_user_role_check_rejects_invalid(db):
    org = Org(name="TestOrg")
    db.add(org)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(User(org_id=org.id, email="x@x.com", role="superadmin", password_hash="h"))
        db.flush()
    db.rollback()


def test_user_unique_email_per_org(db):
    org = Org(name="UniqueOrg")
    db.add(org)
    db.flush()
    db.add(User(org_id=org.id, email="a@a.com", role="user", password_hash="h"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(User(org_id=org.id, email="a@a.com", role="admin", password_hash="h"))
        db.flush()
    db.rollback()
