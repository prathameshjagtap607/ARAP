import uuid

from sqlalchemy.orm import Session

from src.models.users import User
from src.modules.users.schemas import UserListItem, UserListResponse


def list_users(db: Session, org_id: uuid.UUID) -> UserListResponse:
    rows = db.query(User).filter_by(org_id=org_id).order_by(User.created_at.desc()).all()
    return UserListResponse(
        items=[UserListItem.model_validate(u) for u in rows],
        total_count=len(rows),
    )
