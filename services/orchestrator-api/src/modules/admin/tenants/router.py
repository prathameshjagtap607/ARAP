import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.admin.tenants import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/tenants", tags=["admin-tenants"])


@router.get("", response_model=list[schemas.TenantDetail])
def list_tenants(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_tenants(db)


@router.post("", response_model=schemas.TenantDetail, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: schemas.TenantCreate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.create_tenant(db, payload)


@router.get("/{org_id}", response_model=schemas.TenantDetail)
def get_tenant(
    org_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.get_tenant(db, org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{org_id}", response_model=schemas.TenantDetail)
def update_tenant(
    org_id: uuid.UUID,
    payload: schemas.TenantUpdate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.update_tenant(db, org_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{org_id}/suspend", response_model=schemas.TenantDetail)
def suspend_tenant(
    org_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.suspend_tenant(db, org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
