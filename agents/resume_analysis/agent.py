import logging
import re

from agents.common.groq_client import call_tool
from agents.resume_analysis.prompts import RESUME_EXTRACTION_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096

_YEAR_RE = re.compile(r"\d{4}")
_NUMBER_RE = re.compile(r"\d+")
_NULLISH = {"null", "none", "n/a", "na", "unknown", ""}


def _coerce_int(value, pattern: re.Pattern) -> int | None:
    """Normalize a numeric field that the schema now accepts as integer OR
    string (real resumes write dates as ranges like "12/2024 - Present" or
    as the literal text "null") into a real int or None — instead of
    rejecting the response and forcing a costly retry when the model
    doesn't hand back a plain integer."""
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in _NULLISH:
            return None
        match = pattern.search(value)
        return int(match.group()) if match else None
    return None


def _coerce_year(value) -> int | None:
    return _coerce_int(value, _YEAR_RE)


def _coerce_count(value) -> int | None:
    return _coerce_int(value, _NUMBER_RE)


def _normalize_years(result: dict) -> dict:
    for edu in result.get("education") or []:
        edu["year"] = _coerce_year(edu.get("year"))
    for cert in result.get("certifications") or []:
        cert["year"] = _coerce_year(cert.get("year"))
    for job in result.get("employment_history") or []:
        job["team_size"] = _coerce_count(job.get("team_size"))
    leadership = result.get("leadership_indicators")
    if leadership:
        leadership["max_team_size"] = _coerce_count(leadership.get("max_team_size"))
    return result


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
    if max_team_size <= 4:
        return "Team Lead"
    if max_team_size <= 15:
        return "Manager"
    if max_team_size <= 50:
        return "Director"
    return "VP-equiv"


def run_resume_analysis_agent(raw_text: str, job_profile: dict | None) -> dict | None:
    try:
        result = call_tool(
            SYSTEM_PROMPT,
            RESUME_EXTRACTION_TOOL,
            _build_user_message(raw_text, job_profile),
            max_tokens=_MAX_TOKENS,
        )
        result = _normalize_years(result)
        result["_leadership_level"] = _derive_leadership_level(
            result.get("leadership_indicators", {}).get("max_team_size")
        )
        return result
    except Exception:
        logger.exception("Resume analysis agent failed — returning None")
        return None
