import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    plan_tier: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'trial'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
