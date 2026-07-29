import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.integrity import service
from src.modules.integrity.schemas import IntegritySummaryResponse

router = APIRouter(prefix="/integrity", tags=["integrity"])


@router.get("/{session_id}", response_model=IntegritySummaryResponse)
def get_integrity_summary(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_integrity_summary(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
