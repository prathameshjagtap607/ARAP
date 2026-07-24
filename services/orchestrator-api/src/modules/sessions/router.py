import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import (
    TokenClaims,
    require_candidate_scope,
    require_user,
)
from src.modules.sessions import service
from src.modules.sessions.schemas import (
    AnswerRequest,
    AnswerResponse,
    InviteResponse,
    SessionStateResponse,
    SubmitResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/invite", response_model=InviteResponse)
def invite(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.invite_candidate(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{session_id}", response_model=SessionStateResponse)
def get_state(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.get_session_state(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/start", response_model=SessionStateResponse)
def start(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.start_session(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/{session_id}/questions/{question_id}/answer",
    response_model=AnswerResponse,
)
def answer(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    body: AnswerRequest,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.save_answer(db, session_id, question_id, claims.org_id, body.answer_text)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{session_id}/submit", response_model=SubmitResponse)
def submit(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        return service.submit_session(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
