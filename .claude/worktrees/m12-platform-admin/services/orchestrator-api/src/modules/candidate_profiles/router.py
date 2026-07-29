import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.candidate_profiles import service
from src.modules.candidate_profiles.schemas import (
    CandidateProfileResponse,
    SynthesizeRequest,
)

router = APIRouter(prefix="/candidate-profiles", tags=["candidate-profiles"])


@router.post("/synthesize", response_model=CandidateProfileResponse)
def synthesize(
    body: SynthesizeRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.synthesize_profile(
            db, claims.org_id, body.candidate_id, body.job_assessment_id
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/{candidate_id}/{job_assessment_id}", response_model=CandidateProfileResponse)
def get_profile(
    candidate_id: uuid.UUID,
    job_assessment_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_profile(db, claims.org_id, candidate_id, job_assessment_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
