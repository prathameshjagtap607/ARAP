"""
Exit criterion per TASK-000:
  A candidate JWT for session A cannot access any resource scoped to session B.
"""
import uuid

import pytest
from fastapi import HTTPException

from src.modules.auth.dependencies import (
    TokenClaims,
    require_candidate_scope,
    require_client_scope,
)


def _candidate_claims(session_id: uuid.UUID) -> TokenClaims:
    return TokenClaims(
        sub=str(uuid.uuid4()),
        role="candidate",
        org_id=uuid.uuid4(),
        type="access",
        assessment_session_id=session_id,
    )


def _client_claims(share_id: uuid.UUID) -> TokenClaims:
    return TokenClaims(
        sub=str(uuid.uuid4()),
        role="client",
        org_id=uuid.uuid4(),
        type="access",
        report_share_id=share_id,
    )


def test_candidate_jwt_for_session_a_cannot_access_session_b():
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    claims = _candidate_claims(session_a)
    with pytest.raises(HTTPException) as exc:
        require_candidate_scope(session_id=session_b, claims=claims)
    assert exc.value.status_code == 403
    assert "scope" in exc.value.detail.lower()


def test_candidate_jwt_for_session_a_can_access_session_a():
    session_a = uuid.uuid4()
    claims = _candidate_claims(session_a)
    result = require_candidate_scope(session_id=session_a, claims=claims)
    assert result is claims


def test_user_jwt_cannot_access_candidate_scope():
    session_id = uuid.uuid4()
    claims = TokenClaims(
        sub=str(uuid.uuid4()), role="user", org_id=uuid.uuid4(), type="access"
    )
    with pytest.raises(HTTPException) as exc:
        require_candidate_scope(session_id=session_id, claims=claims)
    assert exc.value.status_code == 403


def test_client_jwt_for_share_a_cannot_access_share_b():
    share_a = uuid.uuid4()
    share_b = uuid.uuid4()
    claims = _client_claims(share_a)
    with pytest.raises(HTTPException) as exc:
        require_client_scope(share_id=share_b, claims=claims)
    assert exc.value.status_code == 403
    assert "scope" in exc.value.detail.lower()


def test_client_jwt_for_share_a_can_access_share_a():
    share_a = uuid.uuid4()
    claims = _client_claims(share_a)
    result = require_client_scope(share_id=share_a, claims=claims)
    assert result is claims


def test_candidate_jwt_cannot_use_client_scope():
    session_id = uuid.uuid4()
    share_id = uuid.uuid4()
    claims = _candidate_claims(session_id)
    with pytest.raises(HTTPException) as exc:
        require_client_scope(share_id=share_id, claims=claims)
    assert exc.value.status_code == 403
