import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompetencyCreate(BaseModel):
    name: str
    description: str | None = None
    rubric_notes: str | None = None


class CompetencyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rubric_notes: str | None = None


class CompetencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    rubric_notes: str | None
    created_by: uuid.UUID
    created_at: datetime
