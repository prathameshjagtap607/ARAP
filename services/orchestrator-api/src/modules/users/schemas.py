import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total_count: int


class UserCreateRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(user|admin)$")
    password: str = Field(min_length=8)


class UserUpdateRequest(BaseModel):
    role: str = Field(pattern="^(user|admin)$")
