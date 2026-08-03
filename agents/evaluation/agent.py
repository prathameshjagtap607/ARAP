import logging

from agents.common.groq_client import call_tool
from agents.evaluation.prompts import SYSTEM_PROMPT, build_evaluation_tool

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _no_answer_fallback(target_competencies: list[str]) -> dict:
    return {
        "competency_scores": [
            {
                "competency": comp,
                "score": 1,
                "explanation": "No answer provided.",
                "evidence_quote": "",
                "strength": "N/A",
                "improvement": "Candidate did not respond to this question.",
            }
            for comp in target_competencies
        ]
    }


def score_answer(
    question_text: str,
    category: str,
    target_competencies: list[str],
    answer_text: str | None,
    difficulty: str,
    job_title: str,
) -> dict:
    if not answer_text or not answer_text.strip():
        return _no_answer_fallback(target_competencies)

    user_message = "\n".join([
        f"job_title: {job_title}",
        f"question_category: {category}",
        f"question_difficulty: {difficulty}",
        f"target_competencies: {target_competencies}",
        "",
        f"QUESTION:\n{question_text}",
        "",
        f"CANDIDATE ANSWER:\n{answer_text}",
    ])

    try:
        tool = build_evaluation_tool(target_competencies)
        result = call_tool(SYSTEM_PROMPT, tool, user_message, max_tokens=_MAX_TOKENS)
        return {"competency_scores": list(result["competency_scores"])}
    except Exception:
        logger.exception("Evaluation agent failed for question — returning error sentinel")
        return {"error": "evaluation_failed"}
