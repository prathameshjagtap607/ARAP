import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from src.modules.auth.dependencies import (
    TokenClaims,
    get_claims,
    require_admin,
    require_candidate_scope,
    require_client_scope,
    require_user,
)


def _make_request(claims):
    req = MagicMock()
    req.state.claims = claims
    return req


def _claims(**kwargs):
    defaults = dict(sub=str(uuid.uuid4()), role="user", org_id=uuid.uuid4(), type="access")
    defaults.update(kwargs)
    return TokenClaims(**defaults)


def test_get_claims_returns_claims():
    c = _claims()
    req = _make_request(c)
    assert get_claims(req) is c


def test_get_claims_raises_401_when_none():
    req = _make_request(None)
    with pytest.raises(HTTPException) as exc:
        get_claims(req)
    assert exc.value.status_code == 401


def test_require_user_passes_for_user():
    c = _claims(role="user")
    assert require_user(c) is c


def test_require_user_passes_for_admin():
    c = _claims(role="admin")
    assert require_user(c) is c


def test_require_user_raises_403_for_candidate():
    c = _claims(role="candidate")
    with pytest.raises(HTTPException) as exc:
        require_user(c)
    assert exc.value.status_code == 403


def test_require_admin_passes_for_admin():
    c = _claims(role="admin")
    assert require_admin(c) is c


def test_require_admin_raises_403_for_user():
    c = _claims(role="user")
    with pytest.raises(HTTPException) as exc:
        require_admin(c)
    assert exc.value.status_code == 403


def test_require_candidate_scope_passes():
    sid = uuid.uuid4()
    c = _claims(role="candidate", assessment_session_id=sid)
    result = require_candidate_scope(session_id=sid, claims=c)
    assert result is c


def test_require_candidate_scope_rejects_wrong_session():
    sid_a = uuid.uuid4()
    sid_b = uuid.uuid4()
    c = _claims(role="candidate", assessment_session_id=sid_a)
    with pytest.raises(HTTPException) as exc:
        require_candidate_scope(session_id=sid_b, claims=c)
    assert exc.value.status_code == 403


def test_require_candidate_scope_rejects_wrong_role():
    sid = uuid.uuid4()
    c = _claims(role="user", assessment_session_id=sid)
    with pytest.raises(HTTPException) as exc:
        require_candidate_scope(session_id=sid, claims=c)
    assert exc.value.status_code == 403


def test_require_client_scope_passes():
    share_id = uuid.uuid4()
    c = _claims(role="client", report_share_id=share_id)
    result = require_client_scope(share_id=share_id, claims=c)
    assert result is c


def test_require_client_scope_rejects_wrong_share():
    share_a = uuid.uuid4()
    share_b = uuid.uuid4()
    c = _claims(role="client", report_share_id=share_a)
    with pytest.raises(HTTPException) as exc:
        require_client_scope(share_id=share_b, claims=c)
    assert exc.value.status_code == 403
