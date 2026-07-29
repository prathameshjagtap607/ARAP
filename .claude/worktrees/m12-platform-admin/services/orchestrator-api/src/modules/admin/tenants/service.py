import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.tenants.schemas import TenantCreate, TenantDetail, TenantUpdate


def _row_to_detail(row) -> TenantDetail:
    return TenantDetail(
        id=row["id"],
        name=row["name"],
        plan_tier=row["plan_tier"],
        workspace_limit=row["workspace_limit"],
        is_active=row["is_active"],
        suspended_at=row["suspended_at"],
        created_at=row["created_at"],
        user_count=int(row["user_count"]),
        session_count=int(row["session_count"]),
    )


_TENANT_SQL = """
    SELECT
        o.id, o.name, o.plan_tier, o.workspace_limit, o.is_active,
        o.suspended_at, o.created_at,
        COUNT(DISTINCT u.id) AS user_count,
        COUNT(DISTINCT s.id) AS session_count
    FROM orgs o
    LEFT JOIN users u ON u.org_id = o.id
    LEFT JOIN assessment_sessions s ON s.org_id = o.id
"""


def list_tenants(db: Session) -> list[TenantDetail]:
    rows = db.execute(
        text(_TENANT_SQL + " GROUP BY o.id ORDER BY o.created_at DESC")
    ).mappings().all()
    return [_row_to_detail(r) for r in rows]


def get_tenant(db: Session, org_id: uuid.UUID) -> TenantDetail:
    row = db.execute(
        text(_TENANT_SQL + " WHERE o.id = :org_id GROUP BY o.id"),
        {"org_id": org_id},
    ).mappings().first()
    if not row:
        raise LookupError(f"Org {org_id} not found")
    return _row_to_detail(row)


def create_tenant(db: Session, payload: TenantCreate) -> TenantDetail:
    row = db.execute(
        text("""
            INSERT INTO orgs (name, plan_tier, workspace_limit)
            VALUES (:name, :plan_tier, :workspace_limit)
            RETURNING id
        """),
        {"name": payload.name, "plan_tier": payload.plan_tier, "workspace_limit": payload.workspace_limit},
    ).mappings().first()
    db.commit()
    return get_tenant(db, row["id"])


def update_tenant(db: Session, org_id: uuid.UUID, payload: TenantUpdate) -> TenantDetail:
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        return get_tenant(db, org_id)
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    db.execute(
        text(f"UPDATE orgs SET {set_clause} WHERE id = :org_id"),
        {**updates, "org_id": org_id},
    )
    db.commit()
    return get_tenant(db, org_id)


def suspend_tenant(db: Session, org_id: uuid.UUID) -> TenantDetail:
    # NOTE: sets is_active=false as a display flag only. Auth enforcement
    # (blocking login/API for suspended orgs) is deferred to M13.
    db.execute(
        text("UPDATE orgs SET is_active = false, suspended_at = :now WHERE id = :org_id"),
        {"now": datetime.now(timezone.utc), "org_id": org_id},
    )
    db.commit()
    return get_tenant(db, org_id)
