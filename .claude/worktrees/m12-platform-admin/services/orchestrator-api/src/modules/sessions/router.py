import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import SessionLocal, get_db
from src.modules.auth.dependencies import (
    TokenClaims,
    require_candidate_scope,
    require_user,
)
from src.modules.sessions import service
from src.modules.sessions.schemas import (
    AnswerRequest,
    AnswerResponse,
    CalibrationRequest,
    CalibrationResponse,
    InviteResponse,
    SessionListItem,
    SessionStateResponse,
    SubmitResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionListItem])
def list_sessions(
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_sessions(db, claims.org_id)


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
    background_tasks: BackgroundTasks,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        from agents.evaluation.pipeline import evaluation_pipeline
        def _run_pipeline():
            background_tasks.add_task(evaluation_pipeline, session_id, SessionLocal)

        return service.submit_session(db, session_id, claims.org_id, on_complete=_run_pipeline)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/{session_id}/questions/{question_id}/calibration",
    response_model=CalibrationResponse,
)
def calibrate(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    body: CalibrationRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        result = service.calibrate_answer(
            db, session_id, question_id, claims.org_id,
            body.override_score, body.comment, claims.sub,
        )
        return CalibrationResponse(**result)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
