from fastapi import APIRouter, Depends

from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/tenants", tags=["admin-tenants"])


@router.get("")
def list_tenants(claims: TokenClaims = Depends(require_super_admin)):
    return []
