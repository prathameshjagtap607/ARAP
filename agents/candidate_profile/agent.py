import json
import logging
import re

from agents.candidate_profile.prompts import CANDIDATE_PROFILE_TOOL, SYSTEM_PROMPT
from agents.common.groq_client import call_tool

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096

_NUMBER_RE = re.compile(r"\d+")
_NULLISH = {"null", "none", "n/a", "na", "unknown", ""}


def _coerce_count(value):
    """Normalize team_size, which the schema now accepts as integer OR
    string, into a real int or None — instead of rejecting the response and
    forcing a costly retry when the model doesn't hand back a plain
    integer (mirrors the same fix in agents/resume_analysis/agent.py)."""
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in _NULLISH:
            return None
        match = _NUMBER_RE.search(value)
        return int(match.group()) if match else None
    return None


def _normalize_team_size(result: dict) -> dict:
    scope = (result.get("leadership") or {}).get("scope")
    if scope:
        scope["team_size"] = _coerce_count(scope.get("team_size"))
    return result


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
        result = call_tool(
            SYSTEM_PROMPT,
            CANDIDATE_PROFILE_TOOL,
            _build_user_message(extraction, job_profile),
            max_tokens=_MAX_TOKENS,
        )
        return _normalize_team_size(result)
    except Exception:
        logger.exception("Candidate profile agent failed — returning None")
        return None
