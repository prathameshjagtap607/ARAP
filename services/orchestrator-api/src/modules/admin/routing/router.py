import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db, get_redis
from src.modules.admin.routing import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/routing", tags=["admin-routing"])


@router.get("", response_model=list[schemas.RoutingConfigOut])
def list_routing_configs(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_routing_configs(db)


@router.patch("/{agent_name}", response_model=schemas.RoutingConfigOut)
def update_routing_config(
    agent_name: str,
    payload: schemas.RoutingUpdate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
    redis: redis_lib.Redis = Depends(get_redis),
):
    try:
        return service.update_routing_config(db, redis, agent_name, payload, claims.sub)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
