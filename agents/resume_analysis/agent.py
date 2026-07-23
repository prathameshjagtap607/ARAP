import logging

import anthropic

from agents.resume_analysis.prompts import RESUME_EXTRACTION_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _build_user_message(raw_text: str, job_profile: dict | None) -> str:
    lines = [f"RESUME TEXT:\n{raw_text[:12000]}"]
    if job_profile:
        req = ", ".join(job_profile.get("required_skills", []))
        pref = ", ".join(job_profile.get("preferred_skills", []))
        lines.append(f"\nJOB REQUIRED SKILLS: {req}")
        lines.append(f"JOB PREFERRED SKILLS: {pref}")
    return "\n".join(lines)


def _derive_leadership_level(max_team_size: int | None) -> str:
    if not max_team_size:
        return "IC"
    if max_team_size < 2:
        return "IC"
    if max_team_size <= 4:
        return "Team Lead"
    if max_team_size <= 15:
        return "Manager"
    if max_team_size <= 50:
        return "Director"
    return "VP-equiv"


def run_resume_analysis_agent(raw_text: str, job_profile: dict | None) -> dict | None:
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[RESUME_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_resume"},
            messages=[{"role": "user", "content": _build_user_message(raw_text, job_profile)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        result = dict(tool_block.input)
        result["_leadership_level"] = _derive_leadership_level(
            result.get("leadership_indicators", {}).get("max_team_size")
        )
        return result
    except Exception:
        logger.exception("Resume analysis agent failed — returning None")
        return None
