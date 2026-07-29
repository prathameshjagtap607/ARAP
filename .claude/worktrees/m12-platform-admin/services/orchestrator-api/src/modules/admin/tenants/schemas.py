import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    plan_tier: str = "trial"
    workspace_limit: int = 5


class TenantUpdate(BaseModel):
    plan_tier: str | None = None
    workspace_limit: int | None = None
    is_active: bool | None = None


class TenantDetail(BaseModel):
    id: uuid.UUID
    name: str
    plan_tier: str
    workspace_limit: int
    is_active: bool
    suspended_at: datetime | None
    created_at: datetime
    user_count: int
    session_count: int

    model_config = {"from_attributes": True}
