import uuid
from datetime import datetime

from pydantic import BaseModel


class RoutingConfigOut(BaseModel):
    agent_name: str
    provider: str
    model_id: str
    fallback_provider: str | None
    fallback_model_id: str | None
    updated_by: uuid.UUID | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoutingUpdate(BaseModel):
    provider: str | None = None
    model_id: str | None = None
    fallback_provider: str | None = None
    fallback_model_id: str | None = None
