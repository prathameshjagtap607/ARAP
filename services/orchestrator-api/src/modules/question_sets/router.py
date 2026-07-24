import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.question_sets import QuestionSet
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.question_sets import service
from src.modules.question_sets.schemas import QuestionSetResponse

router = APIRouter(prefix="/question-sets", tags=["question-sets"])

_DEFAULT_TARGET = 10


@router.post(
    "/generate/{session_id}",
    response_model=QuestionSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
    target: int = Query(default=_DEFAULT_TARGET, ge=1, le=50),
):
    existing = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question set already generated and locked for this session",
        )
    try:
        return service.generate_question_set(db, session_id, claims.org_id, target=target)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/{session_id}", response_model=QuestionSetResponse)
def get_set(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_question_set(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
