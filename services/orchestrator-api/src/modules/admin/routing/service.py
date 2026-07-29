import redis as redis_lib
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.routing.schemas import RoutingConfigOut, RoutingUpdate

_CACHE_TTL = 30  # seconds

_ALLOWED_PATCH_FIELDS = {"provider", "model_id", "fallback_provider", "fallback_model_id"}


def _cache_key(agent_name: str) -> str:
    return f"routing:{agent_name}"


def _row_to_out(row) -> RoutingConfigOut:
    return RoutingConfigOut(
        agent_name=row["agent_name"],
        provider=row["provider"],
        model_id=row["model_id"],
        fallback_provider=row["fallback_provider"],
        fallback_model_id=row["fallback_model_id"],
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    )


def list_routing_configs(db: Session) -> list[RoutingConfigOut]:
    rows = db.execute(
        text("SELECT * FROM model_routing_configs WHERE is_active = true ORDER BY agent_name")
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


def get_routing_config(
    db: Session, redis: redis_lib.Redis, agent_name: str
) -> RoutingConfigOut:
    key = _cache_key(agent_name)
    cached = redis.get(key)
    if cached:
        return RoutingConfigOut.model_validate_json(cached)

    row = db.execute(
        text(
            "SELECT * FROM model_routing_configs WHERE agent_name = :agent_name AND is_active = true"
        ),
        {"agent_name": agent_name},
    ).mappings().first()
    if not row:
        raise LookupError(f"No routing config for agent '{agent_name}'")

    result = _row_to_out(row)
    redis.setex(key, _CACHE_TTL, result.model_dump_json())
    return result


def update_routing_config(
    db: Session,
    redis: redis_lib.Redis,
    agent_name: str,
    payload: RoutingUpdate,
    updated_by: str,
) -> RoutingConfigOut:
    existing = db.execute(
        text(
            "SELECT id FROM model_routing_configs WHERE agent_name = :agent_name AND is_active = true"
        ),
        {"agent_name": agent_name},
    ).mappings().first()
    if not existing:
        raise LookupError(f"No routing config for agent '{agent_name}'")

    # Build SET clause from whitelist only — never interpolate user-supplied field names
    updates = {
        k: v
        for k, v in payload.model_dump().items()
        if k in _ALLOWED_PATCH_FIELDS and v is not None
    }

    set_parts = [f"{k} = :{k}" for k in updates]
    set_parts.append("updated_at = NOW()")
    set_parts.append("updated_by = :updated_by")
    set_clause = ", ".join(set_parts)

    params = dict(updates)
    params["updated_by"] = str(updated_by)
    params["agent_name"] = agent_name

    row = db.execute(
        text(
            f"""
            UPDATE model_routing_configs
            SET {set_clause}
            WHERE agent_name = :agent_name AND is_active = true
            RETURNING *
            """
        ),
        params,
    ).mappings().first()
    db.commit()

    # Invalidate cache immediately after commit
    redis.delete(_cache_key(agent_name))

    return _row_to_out(row)
