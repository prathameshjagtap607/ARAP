import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.competency_library import CompetencyLibrary
from src.modules.competency_library.schemas import CompetencyCreate, CompetencyUpdate


def list_competencies(db: Session, org_id: uuid.UUID) -> list[CompetencyLibrary]:
    return db.query(CompetencyLibrary).filter_by(org_id=org_id).all()


def create_competency(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID, data: CompetencyCreate
) -> CompetencyLibrary:
    comp = CompetencyLibrary(
        org_id=org_id,
        name=data.name,
        description=data.description,
        rubric_notes=data.rubric_notes,
        created_by=user_id,
    )
    db.add(comp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Competency '{data.name}' already exists in this org")
    db.commit()
    db.refresh(comp)
    return comp


def update_competency(
    db: Session, org_id: uuid.UUID, comp_id: uuid.UUID, data: CompetencyUpdate
) -> CompetencyLibrary:
    comp = db.query(CompetencyLibrary).filter_by(id=comp_id, org_id=org_id).first()
    if comp is None:
        raise LookupError("Competency not found")
    if data.name is not None:
        comp.name = data.name
    if data.description is not None:
        comp.description = data.description
    if data.rubric_notes is not None:
        comp.rubric_notes = data.rubric_notes
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Competency name '{data.name}' already exists in this org")
    db.refresh(comp)
    return comp


def delete_competency(db: Session, org_id: uuid.UUID, comp_id: uuid.UUID) -> None:
    comp = db.query(CompetencyLibrary).filter_by(id=comp_id, org_id=org_id).first()
    if comp is None:
        raise LookupError("Competency not found")
    db.delete(comp)
    db.commit()
