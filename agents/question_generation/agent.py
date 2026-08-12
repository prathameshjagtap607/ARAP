import json
import logging
import random

from agents.common.groq_client import call_tool
from agents.question_generation.prompts import (
    LEADERSHIP_COMPETENCIES,
    LEADERSHIP_CONTEXTS,
    QUESTION_GENERATION_TOOL,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192


def _assign_dimensions(target_question_count: int) -> tuple[list[str], list[str]]:
    """Explicitly assign one leadership competency and one leadership context
    per question, instead of leaving the choice to the model's free
    discretion — the model was observed drifting toward a handful of
    familiar leadership themes (inexperience, underperformance, conflict)
    even when instructed in prose to "use a different one every time"."""
    def _cycle(pool: list[str]) -> list[str]:
        result: list[str] = []
        while len(result) < target_question_count:
            shuffled = pool[:]
            random.shuffle(shuffled)
            result.extend(shuffled)
        return result[:target_question_count]

    return _cycle(LEADERSHIP_COMPETENCIES), _cycle(LEADERSHIP_CONTEXTS)


def _build_user_message(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> str:
    assigned_competencies, assigned_contexts = _assign_dimensions(target_question_count)
    assignments = [
        {"question_number": i + 1, "competency_area": c, "leadership_context": ctx}
        for i, (c, ctx) in enumerate(zip(assigned_competencies, assigned_contexts))
    ]
    return "\n".join([
        f"job_profile: {json.dumps(job_profile)}",
        f"candidate_profile: {json.dumps(candidate_profile)}",
        f"category_weightage: {json.dumps(category_weightage)}",
        f"difficulty_level: {difficulty_level}",
        f"risk_flags: {json.dumps(risk_flags)}",
        f"target_question_count: {target_question_count}",
        f"assigned_dimensions: {json.dumps(assignments)}",
        "",
        (
            "Generate exactly target_question_count questions, in the same "
            "order as assigned_dimensions. For question N, you MUST use "
            "exactly the competency_area and leadership_context given for "
            "question_number=N in assigned_dimensions — do not substitute a "
            "different one, even if another feels like a better fit. This "
            "guarantees variety across the set. "
            "Seed at least one question per risk flag."
        ),
    ])


def run_question_generation_agent(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> list[dict] | None:
    try:
        user_message = _build_user_message(
            job_profile, candidate_profile, category_weightage,
            difficulty_level, risk_flags, target_question_count,
        )
        result = call_tool(SYSTEM_PROMPT, QUESTION_GENERATION_TOOL, user_message, max_tokens=_MAX_TOKENS)
        return list(result["questions"])
    except Exception:
        logger.exception("Question generation agent failed — returning None")
        return None
