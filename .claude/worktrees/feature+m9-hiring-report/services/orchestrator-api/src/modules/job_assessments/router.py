import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.job_assessments import service
from src.modules.job_assessments.schemas import (
    CloneRequest,
    InviteRequest,
    InviteResponse,
    JobAssessmentCreate,
    JobAssessmentResponse,
    JobAssessmentUpdate,
)

router = APIRouter(prefix="/job-assessments", tags=["job-assessments"])


@router.get("", response_model=list[JobAssessmentResponse])
def list_assessments(
    is_template: bool | None = Query(default=None),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_assessments(db, claims.org_id, is_template)


@router.post("", response_model=JobAssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: JobAssessmentCreate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.create_assessment(db, claims.org_id, uuid.UUID(claims.sub), body)


@router.get("/{assessment_id}", response_model=JobAssessmentResponse)
def get_assessment(
    assessment_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_assessment(db, claims.org_id, assessment_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{assessment_id}", response_model=JobAssessmentResponse)
def update_assessment(
    assessment_id: uuid.UUID,
    body: JobAssessmentUpdate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_assessment(db, claims.org_id, assessment_id, body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        service.delete_assessment(db, claims.org_id, assessment_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{assessment_id}/clone", response_model=JobAssessmentResponse, status_code=status.HTTP_201_CREATED)
def clone_assessment(
    assessment_id: uuid.UUID,
    body: CloneRequest = CloneRequest(),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.clone_assessment(db, claims.org_id, uuid.UUID(claims.sub), assessment_id, body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{assessment_id}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite_candidate(
    assessment_id: uuid.UUID,
    body: InviteRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.invite_candidate(db, claims.org_id, assessment_id, uuid.UUID(claims.sub), body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
