from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.users import service
from src.modules.users.schemas import UserListResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
def list_users(
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_users(db, claims.org_id)
