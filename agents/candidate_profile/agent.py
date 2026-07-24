import json
import logging

import anthropic

from agents.candidate_profile.prompts import CANDIDATE_PROFILE_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _build_user_message(extraction: dict, job_profile: dict) -> str:
    sm = extraction.get("skill_matrix", {})
    em = extraction.get("experience_matrix", {})
    lines = [
        "RESUME EXTRACTION:",
        f"  skills.explicit: {sm.get('explicit', [])}",
        f"  skills.inferred: {sm.get('inferred', [])}",
        f"  tech_used: {sm.get('tech_used', [])}",
        f"  employment_history: {json.dumps(em.get('employment_history', []))}",
        f"  career_timeline: {json.dumps(em.get('career_timeline', {}))}",
        f"  leadership_level_estimate: {extraction.get('leadership_level_estimate')}",
        f"  field_confidence: {json.dumps(extraction.get('field_confidence', {}))}",
        "",
        "JOB PROFILE:",
        f"  normalized_title: {job_profile.get('normalized_title', '')}",
        f"  role_summary: {job_profile.get('role_summary', '')}",
        f"  key_responsibilities: {job_profile.get('key_responsibilities', [])}",
        f"  required_skills: {job_profile.get('required_skills', [])}",
        f"  preferred_skills: {job_profile.get('preferred_skills', [])}",
        f"  difficulty_level: {job_profile.get('difficulty_level', '')}",
    ]
    return "\n".join(lines)


def run_candidate_profile_agent(extraction: dict, job_profile: dict) -> dict | None:
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[CANDIDATE_PROFILE_TOOL],
            tool_choice={"type": "tool", "name": "synthesize_candidate_profile"},
            messages=[{"role": "user", "content": _build_user_message(extraction, job_profile)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return dict(tool_block.input)
    except Exception:
        logger.exception("Candidate profile agent failed — returning None")
        return None
