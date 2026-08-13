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
_MAX_GENERATION_ATTEMPTS = 3

# Keyword fingerprints for the 6 storyline archetypes the prompt already
# bans from repeating more than once per set (see prompts.py SYSTEM_PROMPT).
# Prompt wording alone doesn't reliably stop the model from repeating a
# storyline — this is a deterministic code-level check that catches it
# before a bad set ever reaches a real candidate, triggering a regeneration
# instead of silently shipping it.
_STORYLINE_ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "underperforming_team_member": [
        "not meeting their performance", "not meeting your performance",
        "not meeting their targets", "not meeting your targets",
        "missing deadlines", "struggling to keep up", "underperform",
        "lacking confidence and motivation", "not pulling their weight",
        "falling behind on their work",
    ],
    "new_to_role_unprepared": [
        "new to your role", "new to the role", "new to their role",
        "just started", "recently promoted", "feel unprepared",
        "feels unprepared",
    ],
    "structural_change": [
        "organizational change", "organisational change", "restructuring",
        "undergoing a merger", "new technology is being introduced",
        "new process is being rolled out", "workflow change",
    ],
    "peer_conflict": [
        "two team members", "two of your team members",
        "team members are in conflict", "disagree with each other",
        "conflict between", "at odds with each other",
    ],
    "stakeholder_or_crisis": [
        "unhappy customer", "customer complaint", "demanding a refund",
        "client is unhappy", "a crisis has occurred", "crisis situation",
    ],
    "high_stakes_decision": [
        "high-stakes decision", "significant implications",
        "business-critical decision", "difficult decision",
        "essential to make the right choice",
    ],
}


def _find_repeated_storylines(questions: list[dict]) -> list[str]:
    """Return archetype names that appear in more than one question's text —
    a violation of the hard once-per-set rule the prompt asks the model to
    self-enforce."""
    counts: dict[str, int] = {name: 0 for name in _STORYLINE_ARCHETYPE_KEYWORDS}
    for q in questions:
        text = str(q.get("question", "")).lower()
        for archetype, phrases in _STORYLINE_ARCHETYPE_KEYWORDS.items():
            if any(phrase in text for phrase in phrases):
                counts[archetype] += 1
    return [name for name, count in counts.items() if count > 1]


def _find_boilerplate_options(questions: list[dict]) -> list[str]:
    """Flag generic option phrases reused across many different questions —
    a sign the 4 options aren't genuinely DISC-differentiated per scenario,
    just the same reworded 'communicate and make a plan' template."""
    phrase_counts: dict[str, int] = {}
    for q in questions:
        for option in q.get("options") or []:
            normalized = " ".join(str(option).lower().split())
            phrase_counts[normalized] = phrase_counts.get(normalized, 0) + 1
    threshold = max(3, len(questions) // 2)
    return [phrase for phrase, count in phrase_counts.items() if count >= threshold]


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
    last_questions: list[dict] | None = None
    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        try:
            # Rebuilding the user message each attempt reshuffles
            # assigned_dimensions, giving a genuinely different generation
            # rather than repeating the same failing prompt verbatim.
            user_message = _build_user_message(
                job_profile, candidate_profile, category_weightage,
                difficulty_level, risk_flags, target_question_count,
            )
            result = call_tool(SYSTEM_PROMPT, QUESTION_GENERATION_TOOL, user_message, max_tokens=_MAX_TOKENS)
            questions = list(result["questions"])
        except Exception:
            logger.exception("Question generation agent failed — returning None")
            return None

        last_questions = questions
        repeated = _find_repeated_storylines(questions)
        boilerplate = _find_boilerplate_options(questions)
        if not repeated and not boilerplate:
            return questions

        logger.warning(
            "Question generation attempt %d/%d failed quality checks — "
            "repeated storylines: %s, boilerplate options: %s. %s",
            attempt, _MAX_GENERATION_ATTEMPTS, repeated, boilerplate,
            "Retrying." if attempt < _MAX_GENERATION_ATTEMPTS else "Returning last attempt.",
        )

    return last_questions
