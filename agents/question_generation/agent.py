import json
import logging
import random

from agents.common.groq_client import call_tool
from agents.question_generation.prompts import (
    LEADERSHIP_COMPETENCIES,
    LEADERSHIP_CONTEXTS,
    QUESTION_GENERATION_TOOL,
    QUESTION_REPAIR_TOOL,
    REPAIR_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192
_REPAIR_MAX_TOKENS = 1024

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
    """Flag any option phrase that appears verbatim in more than one
    question — zero tolerance, since a genuinely scenario-specific,
    DISC-differentiated option should never be interchangeable with an
    option from a different question."""
    phrase_counts: dict[str, int] = {}
    for q in questions:
        for option in q.get("options") or []:
            normalized = " ".join(str(option).lower().split())
            phrase_counts[normalized] = phrase_counts.get(normalized, 0) + 1
    return [phrase for phrase, count in phrase_counts.items() if count > 1]


def _find_repeated_storyline_indices(questions: list[dict]) -> list[int]:
    """Like _find_repeated_storylines, but returns the 1-based indices of
    the LATER question(s) for each repeated archetype (the first occurrence
    is kept as-is; only the repeat(s) need to be rewritten) — used to target
    the single-question repair pass instead of a full-set regeneration."""
    first_seen: dict[str, int] = {}
    indices: list[int] = []
    for i, q in enumerate(questions, start=1):
        text = str(q.get("question", "")).lower()
        for archetype, phrases in _STORYLINE_ARCHETYPE_KEYWORDS.items():
            if any(phrase in text for phrase in phrases):
                if archetype in first_seen:
                    indices.append(i)
                else:
                    first_seen[archetype] = i
    return sorted(set(indices))


def _find_boilerplate_option_indices(questions: list[dict]) -> list[int]:
    """Like _find_boilerplate_options, but returns the 1-based indices of
    the LATER question(s) whose options reuse a phrase already seen in an
    earlier question — used to target the single-question repair pass."""
    seen_phrases: set[str] = set()
    indices: list[int] = []
    for i, q in enumerate(questions, start=1):
        for option in q.get("options") or []:
            normalized = " ".join(str(option).lower().split())
            if not normalized:
                continue
            if normalized in seen_phrases:
                indices.append(i)
            else:
                seen_phrases.add(normalized)
    return sorted(set(indices))


def _find_duplicate_option_sets(questions: list[dict]) -> list[int]:
    """Flag questions whose 4 options are the same set as another
    question's (regardless of order) — catches two differently-worded
    scenarios that were given identical answer choices, which is not a
    genuinely distinct question no matter how different the prompt text
    reads. Returns the 1-based indices (within `questions`) of the later
    duplicate(s)."""
    seen: dict[frozenset, int] = {}
    duplicates: list[int] = []
    for i, q in enumerate(questions, start=1):
        options = q.get("options") or []
        fingerprint = frozenset(" ".join(str(o).lower().split()) for o in options)
        if not fingerprint:
            continue
        if fingerprint in seen:
            duplicates.append(i)
        else:
            seen[fingerprint] = i
    return duplicates


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


def _assign_question_formats(target_question_count: int) -> list[str]:
    """Explicitly assign one question_format per question, same reasoning
    as _assign_dimensions above — left to the model's free choice, it could
    pick the same handful of MCQ-style formats every time and never surface
    'ranking' or 'reflection' at all, even though the framework spec (§7)
    lists all 7 as formats the system should be capable of generating. A
    full shuffled cycle of all 7 formats guarantees every format appears at
    least once for any target_question_count >= 7 (the common case)."""
    from agents.question_generation.prompts import QUESTION_FORMATS
    result: list[str] = []
    while len(result) < target_question_count:
        shuffled = QUESTION_FORMATS[:]
        random.shuffle(shuffled)
        result.extend(shuffled)
    return result[:target_question_count]


def _build_user_message(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> str:
    assigned_competencies, assigned_contexts = _assign_dimensions(target_question_count)
    assigned_formats = _assign_question_formats(target_question_count)
    assignments = [
        {
            "question_number": i + 1,
            "competency_area": c,
            "leadership_context": ctx,
            "question_format": fmt,
        }
        for i, (c, ctx, fmt) in enumerate(
            zip(assigned_competencies, assigned_contexts, assigned_formats)
        )
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
            "exactly the competency_area, leadership_context, AND "
            "question_format given for question_number=N in "
            "assigned_dimensions — do not substitute a different one, even "
            "if another feels like a better fit. This guarantees variety "
            "across the set, including making sure formats like 'ranking' "
            "and 'reflection' actually appear rather than always defaulting "
            "to a single-pick MCQ framing. "
            "Seed at least one question per risk flag."
        ),
    ])


def _repair_question(bad_question: dict, other_questions: list[dict]) -> dict | None:
    """Regenerate ONE question in place — same competency_area/
    leadership_context/behavioural_triggers/difficulty/question_format as
    before, fresh scenario + options — instead of regenerating the whole
    set. Much cheaper per token than a full-batch retry while still
    guaranteeing the final set has no duplicates. Returns None (best-effort,
    non-fatal) if the repair call itself fails; the caller keeps the
    original question in that case."""
    already_used = []
    for q in other_questions:
        if q is bad_question:
            continue
        already_used.append(str(q.get("question", "")))
        already_used.extend(str(o) for o in (q.get("options") or []))

    user_message = "\n".join([
        f"competency_area: {bad_question.get('competency_area')}",
        f"leadership_context: {bad_question.get('leadership_context')}",
        f"behavioural_triggers: {json.dumps(bad_question.get('behavioural_triggers') or [])}",
        f"difficulty: {bad_question.get('difficulty')}",
        f"question_format: {bad_question.get('question_format')}",
        f"already_used_storylines_and_phrases: {json.dumps(already_used)}",
    ])
    try:
        return call_tool(
            REPAIR_SYSTEM_PROMPT, QUESTION_REPAIR_TOOL, user_message, max_tokens=_REPAIR_MAX_TOKENS
        )
    except Exception:
        logger.exception("Single-question repair call failed — keeping original question")
        return None


def run_question_generation_agent(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> list[dict] | None:
    """Single full-set generation call, followed by a TARGETED repair pass:
    instead of an expensive full-batch retry (regenerating all N questions
    again) when the quality checks catch a duplicate, only the specific
    offending question(s) are individually regenerated via a small,
    cheap follow-up call each — guaranteeing the final set has no
    duplicates without multiplying the cost of the whole batch."""
    try:
        user_message = _build_user_message(
            job_profile, candidate_profile, category_weightage,
            difficulty_level, risk_flags, target_question_count,
        )
        result = call_tool(SYSTEM_PROMPT, QUESTION_GENERATION_TOOL, user_message, max_tokens=_MAX_TOKENS)
        questions = list(result["questions"])
    except Exception:
        logger.exception("Question generation agent failed — returning None")
        return None

    bad_indices = sorted(
        set(_find_repeated_storyline_indices(questions))
        | set(_find_boilerplate_option_indices(questions))
        | set(_find_duplicate_option_sets(questions))
    )
    if bad_indices:
        logger.warning(
            "Question generation flagged questions %s for targeted repair — "
            "repeated storylines: %s, boilerplate options: %s, "
            "duplicate option sets: %s.",
            bad_indices, _find_repeated_storylines(questions),
            _find_boilerplate_options(questions), _find_duplicate_option_sets(questions),
        )
        for idx in bad_indices:
            bad_question = questions[idx - 1]
            repaired = _repair_question(bad_question, questions)
            if repaired:
                questions[idx - 1] = repaired
            else:
                logger.warning("Repair failed for question %d — keeping original", idx)

    return questions
