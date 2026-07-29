import redis as redis_lib
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db, get_redis
from src.modules.admin.health import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/health", tags=["admin-health"])


@router.get("/overview", response_model=schemas.HealthOverview)
def health_overview(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
):
    return service.get_health_overview(db, redis)


@router.get("/incidents", response_model=list[schemas.IncidentEntry])
def incidents(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.get_incidents(db)


@router.get("/fraud-flags", response_model=schemas.FraudFlagStats)
def fraud_flags(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.get_fraud_flag_stats(db)
