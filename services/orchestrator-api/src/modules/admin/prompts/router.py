import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.admin.prompts import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/prompts", tags=["admin-prompts"])


@router.get("", response_model=list[schemas.PromptTemplateOut])
def list_prompts(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_prompt_templates(db)


@router.get("/{agent_name}", response_model=list[schemas.PromptTemplateOut])
def list_versions(
    agent_name: str,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_versions_for_agent(db, agent_name)


@router.post("", response_model=schemas.PromptTemplateOut, status_code=status.HTTP_201_CREATED)
def create_prompt(
    payload: schemas.PromptCreate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.create_prompt_template(db, payload)


@router.post("/{template_id}/activate", response_model=schemas.PromptTemplateOut)
def activate_prompt(
    template_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.activate_prompt(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{template_id}/rollback", response_model=schemas.PromptTemplateOut)
def rollback_prompt(
    template_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.rollback_prompt(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{template_id}/audit", response_model=list[schemas.PromptAuditEntry])
def get_audit(
    template_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.get_prompt_audit(db, template_id)
