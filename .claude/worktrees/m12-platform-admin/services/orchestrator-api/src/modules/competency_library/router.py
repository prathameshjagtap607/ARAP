import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.competency_library import service
from src.modules.competency_library.schemas import (
    CompetencyCreate,
    CompetencyResponse,
    CompetencyUpdate,
)

router = APIRouter(prefix="/competency-library", tags=["competency-library"])


@router.get("", response_model=list[CompetencyResponse])
def list_competencies(
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_competencies(db, claims.org_id)


@router.post("", response_model=CompetencyResponse, status_code=status.HTTP_201_CREATED)
def create_competency(
    body: CompetencyCreate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_competency(db, claims.org_id, uuid.UUID(claims.sub), body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{comp_id}", response_model=CompetencyResponse)
def update_competency(
    comp_id: uuid.UUID,
    body: CompetencyUpdate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_competency(db, claims.org_id, comp_id, body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{comp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competency(
    comp_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        service.delete_competency(db, claims.org_id, comp_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
