import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.users import User
from src.modules.auth.service import pwd_context
from src.modules.users.schemas import (
    UserCreateRequest,
    UserListItem,
    UserListResponse,
    UserUpdateRequest,
)


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


def update_user(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID, data: UserUpdateRequest, acting_user_id: uuid.UUID
) -> UserListItem:
    user = db.query(User).filter_by(id=user_id, org_id=org_id).first()
    if not user:
        raise LookupError("User not found")
    if user.role == "super_admin":
        raise ValueError("Cannot change a super_admin's role")
    if user.id == acting_user_id and data.role != user.role:
        raise ValueError("Cannot change your own role")

    user.role = data.role
    db.commit()
    db.refresh(user)
    return UserListItem.model_validate(user)


def delete_user(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, acting_user_id: uuid.UUID) -> None:
    user = db.query(User).filter_by(id=user_id, org_id=org_id).first()
    if not user:
        raise LookupError("User not found")
    if user.role == "super_admin":
        raise ValueError("Cannot delete a super_admin")
    if user.id == acting_user_id:
        raise ValueError("Cannot delete your own account")
    if user.role == "admin":
        other_admins = (
            db.query(User)
            .filter(User.org_id == org_id, User.role == "admin", User.id != user_id)
            .count()
        )
        if other_admins == 0:
            raise ValueError("Cannot delete the last remaining admin in this org")

    db.delete(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(
            "Cannot delete this user — they have created job assessments or "
            "competencies that are still in use"
        )
