import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CompetencyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rubric_notes: Optional[str] = None


class CompetencyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rubric_notes: Optional[str] = None


class CompetencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    rubric_notes: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
