import logging

import anthropic

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048

_SUMMARY_TOOL = {
    "name": "generate_report_summary",
    "description": "Generate the executive summary and supporting report fields for a hiring report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-3 sentence plain-English summary of the candidate's performance.",
            },
            "suggested_hr_questions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 3,
                "description": "3 follow-up questions based on weak competencies.",
            },
            "recommended_next_round": {
                "type": "string",
                "description": "E.g. 'Technical Panel Interview' or 'Final HR Round'.",
            },
            "training_needs": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
                "description": "Top 1-3 competency gaps to address if hired.",
            },
        },
        "required": [
            "executive_summary",
            "suggested_hr_questions",
            "recommended_next_round",
            "training_needs",
        ],
    },
}

_SYSTEM_PROMPT = (
    "You are a senior HR analyst writing a concise hiring recommendation. "
    "Base everything on the score data provided. Be specific and objective. "
    "Do not invent information not present in the scores."
)


def generate_summary(job_title: str, rollup: dict, verdict: str, candidate_name: str = "Unknown") -> dict | None:
    composite_scores = rollup.get("composite_scores", {})
    overall = rollup.get("overall", 0.0)

    user_message = "\n".join([
        f"Candidate: {candidate_name}",
        f"Role: {job_title}",
        f"Verdict: {verdict}",
        f"Overall score: {overall:.2f} / 5.0",
        "Composite scores:",
        *[f"  {k}: {v:.2f}" for k, v in composite_scores.items()],
    ])

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=[_SUMMARY_TOOL],
            tool_choice={"type": "tool", "name": "generate_report_summary"},
            messages=[{"role": "user", "content": user_message}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return dict(tool_block.input)
    except Exception:
        logger.exception("Summary generation failed")
        return None
