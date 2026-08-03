import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from agents.common.groq_client import call_tool
from agents.behavior_analysis.prompts import (
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_TOOL,
    SYNTHESIZE_SYSTEM_PROMPT,
    build_synthesize_tool,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _extract_signals(transcript: str) -> dict:
    return call_tool(EXTRACT_SYSTEM_PROMPT, EXTRACT_TOOL, transcript, max_tokens=_MAX_TOKENS)


def _synthesize_profile(signals: dict, org_working_style: str | None) -> dict:
    tool = build_synthesize_tool(org_working_style)
    signals_text = "\n".join(f"{k}: {v}" for k, v in signals.items())
    return call_tool(SYNTHESIZE_SYSTEM_PROMPT, tool, signals_text, max_tokens=_MAX_TOKENS)


def infer_behavior(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
    org_working_style: str | None = None,
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("infer_behavior: session %s not found", session_id)
            return

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("infer_behavior: no question set for session %s", session_id)
            return

        questions = (
            db.query(SessionQuestion)
            .filter(
                SessionQuestion.question_set_id == qset.id,
                SessionQuestion.answer_text.isnot(None),
            )
            .order_by(SessionQuestion.sequence_no)
            .all()
        )

        if not questions:
            logger.info("infer_behavior: no answered questions for session %s — skipping", session_id)
            return

        transcript = "\n\n".join(
            f"Q{q.sequence_no} [{q.category}]: {q.question.get('text', '')}\nA: {q.answer_text}"
            for q in questions
        )

        signals = _extract_signals(transcript)
        profile_data = _synthesize_profile(signals, org_working_style)

        existing = db.query(BehaviorProfile).filter_by(session_id=session_id).first()
        if existing:
            existing.disc_style = profile_data["disc_style"]
            existing.big_five = profile_data["big_five"]
            existing.leadership_style = profile_data.get("leadership_style")
            existing.decision_style = profile_data.get("decision_style")
            existing.communication_style = profile_data.get("communication_style")
            existing.work_style = profile_data.get("work_style")
            existing.stress_signal = profile_data.get("stress_signal")
            existing.eq_signal = profile_data.get("eq_signal")
            existing.team_compatibility_signal = profile_data.get("team_compatibility_signal")
        else:
            db.add(BehaviorProfile(
                org_id=session.org_id,
                session_id=session_id,
                disc_style=profile_data["disc_style"],
                big_five=profile_data["big_five"],
                leadership_style=profile_data.get("leadership_style"),
                decision_style=profile_data.get("decision_style"),
                communication_style=profile_data.get("communication_style"),
                work_style=profile_data.get("work_style"),
                stress_signal=profile_data.get("stress_signal"),
                eq_signal=profile_data.get("eq_signal"),
                team_compatibility_signal=profile_data.get("team_compatibility_signal"),
            ))

        db.commit()
        logger.info("infer_behavior: behavior profile written for session %s", session_id)

    except Exception:
        logger.exception("infer_behavior failed for session %s — skipping", session_id)
        db.rollback()
    finally:
        db.close()
