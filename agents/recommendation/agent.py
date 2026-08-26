import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from agents.common.groq_client import call_tool
from agents.recommendation.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_TOOL,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _compute_confidence(
    rollup: dict, integrity_summary: dict, has_behavior: bool, disc_confidence: float | None = None
) -> float:
    """AI confidence in this report's assessment. Since the DISC-only pivot,
    there's no per-competency 0-5 scoring left to measure answer consistency
    with (that belonged to the old skills-scoring pipeline) — using the
    actual DISC classification confidence instead (how clearly the
    candidate's answers pointed to one behavioural style) is the real
    DISC-relevant signal available here, and it varies per candidate rather
    than silently defaulting to the same constant for everyone."""
    question_count = rollup.get("question_count", 1) or 1
    answered_count = rollup.get("answered_count", 0)
    coverage = min(answered_count / question_count, 1.0)

    consistency = disc_confidence if disc_confidence is not None else 0.7

    integrity_factor = {"low": 1.0, "medium": 0.6, "high": 0.3}.get(
        integrity_summary.get("overall_risk", "low"), 1.0
    )
    behavior_factor = 1.0 if has_behavior else 0.7

    raw = coverage * 0.40 + consistency * 0.30 + integrity_factor * 0.20 + behavior_factor * 0.10
    return round(raw * 100, 1)


def synthesize_recommendation(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.candidates import Candidate
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("synthesize_recommendation: session %s not found", session_id)
            return

        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if not report:
            logger.error("synthesize_recommendation: no report for session %s", session_id)
            return

        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
        behavior = db.query(BehaviorProfile).filter_by(session_id=session_id).first()

        rollup = dict(report.score_rollup or {})
        integrity_summary = dict(report.integrity_summary or {})
        has_behavior = behavior is not None
        disc_confidence = (
            behavior.disc_style.get("confidence") if behavior and behavior.disc_style else None
        )

        confidence = _compute_confidence(rollup, integrity_summary, has_behavior, disc_confidence)

        composite_scores = rollup.get("composite_scores", {})
        competency_scores = rollup.get("competency_scores", {})
        overall = rollup.get("overall", 0.0)

        behavior_summary = ""
        if behavior:
            behavior_summary = (
                f"DISC: {behavior.disc_style}, "
                f"Leadership style: {behavior.leadership_style}, "
                f"Decision style: {behavior.decision_style}, "
                f"EQ signal: {behavior.eq_signal}"
            )

        user_message = "\n".join([
            f"Candidate: {candidate.name if candidate else 'Unknown'}",
            f"Role: {job.title if job else 'Unknown'} ({getattr(job, 'difficulty_level', 'mid')})",
            f"Role family: {getattr(job, 'role_family', 'N/A')}",
            f"Required skills: {', '.join(getattr(job, 'required_skills', []))}",
            f"Experience required: {getattr(job, 'experience_min', 'N/A')}–{getattr(job, 'experience_max', 'N/A')} years",
            f"Overall score: {overall:.2f} / 5.0",
            f"Verdict: {report.verdict}",
            "Composite scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in composite_scores.items()),
            "Competency scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in list(competency_scores.items())[:8]),
            f"AI confidence score: {confidence}",
            f"Integrity risk: {integrity_summary.get('overall_risk', 'low')} ({integrity_summary.get('flagged_count', 0)} flags)",
            f"Behavior profile: {behavior_summary or 'Not available'}",
        ])

        result = call_tool(RECOMMENDATION_SYSTEM_PROMPT, RECOMMENDATION_TOOL, user_message, max_tokens=_MAX_TOKENS)

        report.salary_band = result["salary_band"]
        report.ai_confidence_score = confidence
        report.suggested_ceo_questions = result["suggested_ceo_questions"]
        # Flatten training_needs objects to strings for ARRAY(Text) column
        report.training_needs = [
            f"{tn['area']} ({tn['priority']})" for tn in result.get("training_needs", [])
        ]
        report.full_report = {
            **(report.full_report or {}),
            "_recommendation_context": {
                "verdict_reasoning": result.get("verdict_reasoning", ""),
                "salary_band_rationale": result.get("salary_band_rationale", ""),
                "training_needs": result.get("training_needs", []),
            },
        }

        db.commit()
        logger.info(
            "synthesize_recommendation: complete for session %s — band=%s confidence=%.1f",
            session_id,
            result["salary_band"],
            confidence,
        )

    except Exception:
        logger.exception("synthesize_recommendation failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()
