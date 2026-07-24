import json
import logging

import anthropic

from agents.question_generation.prompts import (
    QUESTION_GENERATION_TOOL,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192


def _build_user_message(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> str:
    return "\n".join([
        f"job_profile: {json.dumps(job_profile)}",
        f"candidate_profile: {json.dumps(candidate_profile)}",
        f"category_weightage: {json.dumps(category_weightage)}",
        f"difficulty_level: {difficulty_level}",
        f"risk_flags: {json.dumps(risk_flags)}",
        f"target_question_count: {target_question_count}",
        "",
        "Generate exactly target_question_count questions. "
        "At least one question MUST have resume_reference=true, "
        "directly citing a specific detail from the candidate's resume. "
        "Distribute questions across categories per category_weightage counts. "
        "Seed at least one question per risk flag.",
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
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[QUESTION_GENERATION_TOOL],
            tool_choice={"type": "tool", "name": "generate_question_set"},
            messages=[{
                "role": "user",
                "content": _build_user_message(
                    job_profile, candidate_profile, category_weightage,
                    difficulty_level, risk_flags, target_question_count,
                ),
            }],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return list(tool_block.input["questions"])
    except Exception:
        logger.exception("Question generation agent failed — returning None")
        return None
