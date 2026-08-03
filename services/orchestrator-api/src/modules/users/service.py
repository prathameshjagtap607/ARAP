import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.users import User
from src.modules.auth.service import pwd_context
from src.modules.users.schemas import UserCreateRequest, UserListItem, UserListResponse


def list_users(db: Session, org_id: uuid.UUID) -> UserListResponse:
    rows = db.query(User).filter_by(org_id=org_id).order_by(User.created_at.desc()).all()
    return UserListResponse(
        items=[UserListItem.model_validate(u) for u in rows],
        total_count=len(rows),
    )


def create_user(db: Session, org_id: uuid.UUID, data: UserCreateRequest) -> UserListItem:
    user = User(
        org_id=org_id,
        email=data.email,
        role=data.role,
        password_hash=pwd_context.hash(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"User with email '{data.email}' already exists in this org")
    db.refresh(user)
    return UserListItem.model_validate(user)
