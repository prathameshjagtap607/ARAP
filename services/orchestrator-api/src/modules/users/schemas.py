import uuid
from datetime import datetime

from pydantic import BaseModel


class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total_count: int
