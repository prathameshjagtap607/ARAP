import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.prompts.schemas import (
    PromptAuditEntry,
    PromptCreate,
    PromptTemplateOut,
)


def _row_to_out(row) -> PromptTemplateOut:
    return PromptTemplateOut(
        id=row["id"],
        org_id=row["org_id"],
        agent_name=row["agent_name"],
        version=row["version"],
        template_body=row["template_body"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )


def list_prompt_templates(db: Session) -> list[PromptTemplateOut]:
    rows = db.execute(
        text("SELECT * FROM prompt_templates ORDER BY created_at DESC")
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


def list_versions_for_agent(db: Session, agent_name: str) -> list[PromptTemplateOut]:
    rows = db.execute(
        text("""
            SELECT * FROM prompt_templates
            WHERE agent_name = :agent_name
            ORDER BY created_at DESC
        """),
        {"agent_name": agent_name},
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


def create_prompt_template(db: Session, payload: PromptCreate) -> PromptTemplateOut:
    row = db.execute(
        text("""
            INSERT INTO prompt_templates (org_id, agent_name, version, template_body)
            VALUES (:org_id, :agent_name, :version, :template_body)
            RETURNING *
        """),
        {
            "org_id": payload.org_id,
            "agent_name": payload.agent_name,
            "version": payload.version,
            "template_body": payload.template_body,
        },
    ).mappings().first()
    db.commit()
    return _row_to_out(row)


def activate_prompt(db: Session, template_id: uuid.UUID) -> PromptTemplateOut:
    target = db.execute(
        text("SELECT * FROM prompt_templates WHERE id = :id"),
        {"id": template_id},
    ).mappings().first()
    if not target:
        raise LookupError(f"Template {template_id} not found")

    # Atomic swap: deactivate current active for same (org_id, agent_name), activate target
    db.execute(
        text("""
            UPDATE prompt_templates
            SET is_active = false
            WHERE agent_name = :agent_name
              AND (org_id = :org_id OR (org_id IS NULL AND :org_id IS NULL))
              AND is_active = true
              AND id != :id
        """),
        {"agent_name": target["agent_name"], "org_id": target["org_id"], "id": template_id},
    )
    updated = db.execute(
        text("UPDATE prompt_templates SET is_active = true WHERE id = :id RETURNING *"),
        {"id": template_id},
    ).mappings().first()
    db.commit()
    return _row_to_out(updated)


def rollback_prompt(db: Session, template_id: uuid.UUID) -> PromptTemplateOut:
    target = db.execute(
        text("SELECT * FROM prompt_templates WHERE id = :id"),
        {"id": template_id},
    ).mappings().first()
    if not target:
        raise LookupError(f"Template {template_id} not found")

    # Find the most-recent version that is NOT the target and NOT currently active
    prev = db.execute(
        text("""
            SELECT id FROM prompt_templates
            WHERE agent_name = :agent_name
              AND (org_id = :org_id OR (org_id IS NULL AND :org_id IS NULL))
              AND id != :id
              AND is_active = false
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"agent_name": target["agent_name"], "org_id": target["org_id"], "id": template_id},
    ).mappings().first()
    if not prev:
        raise LookupError("No previous version available for rollback")

    return activate_prompt(db, prev["id"])


def get_prompt_audit(db: Session, template_id: uuid.UUID) -> list[PromptAuditEntry]:
    rows = db.execute(
        text("""
            SELECT s.id AS session_id, s.org_id, s.started_at, s.completed_at
            FROM assessment_sessions s
            WHERE s.prompt_template_id = :template_id
            ORDER BY s.started_at DESC
        """),
        {"template_id": template_id},
    ).mappings().all()
    return [
        PromptAuditEntry(
            session_id=r["session_id"],
            org_id=r["org_id"],
            started_at=r["started_at"],
            completed_at=r["completed_at"],
        )
        for r in rows
    ]
