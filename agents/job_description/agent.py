import logging
from datetime import UTC, datetime

import anthropic
from sqlalchemy.orm import Session
from src.config import settings

from agents.job_description.prompts import JOB_PROFILE_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _build_user_message(assessment) -> str:
    return (
        f"Title: {assessment.title}\n"
        f"Department: {assessment.department or 'N/A'}\n"
        f"Difficulty: {assessment.difficulty_level}\n"
        f"Experience: {assessment.experience_min or 0}–{assessment.experience_max or 0} years\n"
        f"Required skills: {', '.join(assessment.required_skills or [])}\n"
        f"Preferred skills: {', '.join(assessment.preferred_skills or [])}\n"
        f"Responsibilities: {assessment.responsibilities or 'N/A'}\n"
        f"Education: {assessment.education or 'N/A'}\n"
        f"Certifications: {', '.join(assessment.certifications or [])}\n"
        f"Behavioral competencies: {', '.join(assessment.behavioral_competencies or [])}\n"
        f"Leadership competencies: {', '.join(assessment.leadership_competencies or [])}\n"
        f"Culture values: {', '.join(assessment.culture_values or [])}\n"
        f"Competency weightage: {assessment.competency_weightage}\n"
    )


def run_job_description_agent(db: Session, assessment) -> None:
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[JOB_PROFILE_TOOL],
            tool_choice={"type": "tool", "name": "produce_job_profile"},
            messages=[{"role": "user", "content": _build_user_message(assessment)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        profile = dict(tool_block.input)
        profile["generated_at"] = datetime.now(UTC).isoformat()
        assessment.job_profile = profile
        db.commit()
    except Exception:
        logger.exception("JD agent failed for assessment %s — job_profile left NULL", assessment.id)
        db.rollback()
