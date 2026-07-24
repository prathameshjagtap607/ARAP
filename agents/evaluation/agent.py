import logging

import anthropic

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
        client = anthropic.Anthropic()
        tool = build_evaluation_tool(target_competencies)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[tool],
            tool_choice={"type": "tool", "name": "evaluate_answer"},
            messages=[{"role": "user", "content": user_message}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return {"competency_scores": list(tool_block.input["competency_scores"])}
    except Exception:
        logger.exception("Evaluation agent failed for question — returning error sentinel")
        return {"error": "evaluation_failed"}
