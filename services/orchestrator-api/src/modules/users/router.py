from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_admin, require_user
from src.modules.users import service
from src.modules.users.schemas import UserCreateRequest, UserListItem, UserListResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
def list_users(
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_users(db, claims.org_id)


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateRequest,
    claims: TokenClaims = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.create_user(db, claims.org_id, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
