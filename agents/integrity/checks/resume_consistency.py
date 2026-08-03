import json

from agents.common.groq_client import call_tool
from agents.integrity.checks.ai_generated import FlagResult

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048

_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic."
)

_SYSTEM_PROMPT = (
    "You are reviewing a job interview transcript for factual consistency with the "
    "candidate's parsed resume. Identify claims in the answers that contradict or are "
    "entirely absent from the resume data. Focus only on verifiable facts: named skills, "
    "technologies, job titles, company names, dates, and project outcomes. Do not flag "
    "unverifiable soft skills or subjective statements. "
    + _SECTION_15_EXCLUSION
)

_TOOL = {
    "name": "check_resume_consistency",
    "description": "Identify factual discrepancies between interview answers and parsed resume.",
    "input_schema": {
        "type": "object",
        "properties": {
            "discrepancies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "present_in_resume": {"type": "boolean"},
                        "conflict_type": {
                            "type": "string",
                            "enum": [
                                "skill_absent",
                                "experience_absent",
                                "timeline_conflict",
                                "minor_embellishment",
                            ],
                        },
                        "evidence": {"type": "string"},
                        "answer_sequence_no": {"type": "integer"},
                    },
                    "required": [
                        "claim",
                        "present_in_resume",
                        "conflict_type",
                        "evidence",
                        "answer_sequence_no",
                    ],
                },
            }
        },
        "required": ["discrepancies"],
    },
}

_SEVERITY_MAP = {
    "timeline_conflict": "high",
    "skill_absent": "medium",
    "experience_absent": "medium",
    "minor_embellishment": "low",
}


def check_resume_consistency(questions: list, candidate_profile) -> list[FlagResult]:
    long_qs = [q for q in questions if q.answer_format == "long_text" and q.answer_text]
    if not long_qs:
        return []

    transcript = "\n\n".join(
        f"Q{q.sequence_no}: {q.question.get('text', '')}\nA: {q.answer_text}"
        for q in long_qs
    )
    skill_matrix = json.dumps(dict(candidate_profile.skill_matrix or {}))
    experience_matrix = json.dumps(dict(candidate_profile.experience_matrix or {}))

    user_content = (
        f"INTERVIEW TRANSCRIPT:\n{transcript}\n\n"
        f"RESUME SKILL MATRIX:\n{skill_matrix}\n\n"
        f"RESUME EXPERIENCE MATRIX:\n{experience_matrix}"
    )

    result = call_tool(_SYSTEM_PROMPT, _TOOL, user_content, max_tokens=_MAX_TOKENS)
    discrepancies = result.get("discrepancies", [])

    seq_to_id = {q.sequence_no: q.id for q in questions}

    flags: list[FlagResult] = []
    for d in discrepancies:
        if d.get("present_in_resume"):
            continue
        conflict_type = d.get("conflict_type", "skill_absent")
        severity = _SEVERITY_MAP.get(conflict_type, "low")
        sq_id = seq_to_id.get(d.get("answer_sequence_no"))
        flags.append(
            FlagResult(
                flag_type="resume_inconsistency",
                severity=severity,
                evidence=d.get("evidence", ""),
                session_question_id=sq_id,
            )
        )

    return flags
