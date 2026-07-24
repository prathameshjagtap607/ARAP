import logging

from agents.scoring.rubric import (
    COMPETENCY_TO_COMPOSITE,
    COMPOSITES,
    DIFFICULTY_WEIGHTS,
)

logger = logging.getLogger(__name__)


def roll_up(answered_questions: list[dict], job_weightage: dict[str, float]) -> dict:
    """
    Compute per-competency weighted scores and 4 composite scores from evaluated questions.
    answered_questions: each must have 'target_competencies', 'difficulty', 'evaluation'.
    job_weightage: competency key → weight (from job_assessments.competency_weightage).
    """
    # Accumulate weighted scores per competency: {competency: (sum_weighted, sum_weights)}
    accum: dict[str, list[float]] = {}  # competency → [sum_weighted_scores, sum_weights]
    answered_count = 0

    for q in answered_questions:
        evaluation = q.get("evaluation")
        if not evaluation or "competency_scores" not in evaluation:
            continue
        answered_count += 1
        diff = q.get("difficulty", "medium")
        w = DIFFICULTY_WEIGHTS.get(diff, 1.5)
        for cs in evaluation["competency_scores"]:
            comp = cs.get("competency")
            score = cs.get("score")
            if comp is None or score is None:
                continue
            if comp not in accum:
                accum[comp] = [0.0, 0.0]
            accum[comp][0] += score * w
            accum[comp][1] += w

    competency_scores: dict[str, float] = {
        comp: vals[0] / vals[1]
        for comp, vals in accum.items()
        if vals[1] > 0
    }

    # Composite scores: weighted average of constituent competencies using job_weightage
    composite_accum: dict[str, list[float]] = {c: [0.0, 0.0] for c in COMPOSITES}
    for comp, score in competency_scores.items():
        cat = COMPETENCY_TO_COMPOSITE.get(comp)
        if cat is None:
            logger.warning("competency %r not in rubric — skipped in composite", comp)
            continue
        jw = job_weightage.get(comp, 1.0)
        composite_accum[cat][0] += score * jw
        composite_accum[cat][1] += jw

    composite_scores: dict[str, float] = {
        cat: vals[0] / vals[1]
        for cat, vals in composite_accum.items()
        if vals[1] > 0
    }

    overall = (
        sum(composite_scores.values()) / len(composite_scores)
        if composite_scores
        else 0.0
    )

    return {
        "competency_scores": competency_scores,
        "composite_scores": composite_scores,
        "overall": round(overall, 4),
        "question_count": len(answered_questions),
        "answered_count": answered_count,
    }
