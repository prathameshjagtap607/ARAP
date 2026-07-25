import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

import agents.integrity.checks.ai_generated as _f01
import agents.integrity.checks.behavioral_anomaly as _f04
import agents.integrity.checks.duplicate as _f02
import agents.integrity.checks.resume_consistency as _f03
from agents.integrity.checks.ai_generated import FlagResult

logger = logging.getLogger(__name__)


def run_integrity_checks(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.candidate_profiles import CandidateProfile
    from src.models.hiring_reports import HiringReport
    from src.models.integrity_flags import IntegrityFlag
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("run_integrity_checks: session %s not found", session_id)
            return

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("run_integrity_checks: no question set for session %s", session_id)
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

        all_flags: list[FlagResult] = []

        # F01 — statistical heuristics
        try:
            all_flags.extend(_f01.check_ai_generated(questions, session))
        except Exception:
            logger.exception("F01 ai_generated check failed for session %s", session_id)

        # F02 — duplicate detection
        try:
            dup_flags = _f02.check_duplicate(questions, session, db)
            all_flags.extend(dup_flags)
        except Exception:
            logger.exception("F02 duplicate check failed for session %s", session_id)

        # F02 — corpus ingest (isolated so a UNIQUE constraint violation doesn't drop the flags)
        try:
            _f02.ingest_corpus(questions, session, db)
        except Exception:
            logger.exception("answer_corpus ingest failed for session %s", session_id)

        # F03 — resume consistency (skip if no candidate profile)
        try:
            candidate_profile = None
            if session.candidate_profile_id:
                candidate_profile = (
                    db.query(CandidateProfile)
                    .filter_by(id=session.candidate_profile_id)
                    .first()
                )
            if candidate_profile:
                all_flags.extend(_f03.check_resume_consistency(questions, candidate_profile))
            else:
                logger.info(
                    "run_integrity_checks: no candidate profile for session %s — skipping F03",
                    session_id,
                )
        except Exception:
            logger.exception("F03 resume_consistency check failed for session %s", session_id)

        # F04 — stub (always returns [])
        try:
            all_flags.extend(_f04.check_behavioral_anomalies(session_id, db))
        except Exception:
            logger.exception("F04 behavioral_anomaly check failed for session %s", session_id)

        # Persist integrity_flags rows
        for flag in all_flags:
            db.add(
                IntegrityFlag(
                    org_id=session.org_id,
                    session_id=session_id,
                    session_question_id=flag.session_question_id,
                    flag_type=flag.flag_type,
                    severity=flag.severity,
                    evidence=flag.evidence,
                )
            )
        db.flush()

        # F05 — compile summary → hiring_reports.integrity_summary
        summary = _compile_integrity_summary(all_flags)
        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if report:
            report.integrity_summary = summary

        db.commit()
        logger.info(
            "run_integrity_checks: %d flag(s) written for session %s, risk=%s",
            len(all_flags),
            session_id,
            summary["overall_risk"],
        )

    except Exception:
        logger.exception("run_integrity_checks failed for session %s", session_id)
        db.rollback()


def _compile_integrity_summary(flags: list[FlagResult]) -> dict:
    severities = [f.severity for f in flags]
    if "high" in severities:
        overall_risk = "high"
    elif severities.count("medium") >= 2:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    human_review_required = overall_risk in ("high", "medium")

    return {
        "flagged_count": len(flags),
        "overall_risk": overall_risk,
        "human_review_required": human_review_required,
        "flags": [
            {
                "type": f.flag_type,
                "severity": f.severity,
                "evidence": f.evidence,
                "question_id": (
                    str(f.session_question_id) if f.session_question_id else None
                ),
            }
            for f in flags
        ],
        "open_question": (
            "Labeled validation set not available; recall >85% / FP <10% targets "
            "(PRD §3) cannot be verified — see TASK-002 Open Question #4."
        ),
    }
