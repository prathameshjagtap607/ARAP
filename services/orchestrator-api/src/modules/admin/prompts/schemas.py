import uuid
from datetime import datetime

from pydantic import BaseModel


class PromptCreate(BaseModel):
    org_id: uuid.UUID | None = None
    agent_name: str
    version: str
    template_body: str


class PromptTemplateOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    agent_name: str
    version: str
    template_body: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptAuditEntry(BaseModel):
    session_id: uuid.UUID
    org_id: uuid.UUID
    started_at: datetime | None
    completed_at: datetime | None
