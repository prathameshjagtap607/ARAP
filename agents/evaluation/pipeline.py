import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from agents.scoring.rubric import derive_verdict

logger = logging.getLogger(__name__)


def _resolve_answer_text(q) -> str | None:
    """For multiple_choice questions, the stored answer_text is just the
    selected option's letter key (e.g. "B") — resolve it to the actual
    option text so the scoring model has something meaningful to evaluate.
    Other answer formats have no options and pass through unchanged.
    """
    if q.answer_format == "multiple_choice" and q.options and q.answer_text in q.options:
        return q.options[q.answer_text]
    return q.answer_text


def evaluation_pipeline(session_id: uuid.UUID, db_factory: Callable[[], Session]) -> None:
    """
    Runs after submit_session completes. Owns its own DB session (not request-scoped).
    This is a DISC-only assessment — there is no correct/incorrect answer to
    score, so per-question LLM scoring is skipped entirely (it was ~10 of the
    ~23 AI calls made per invite, for a score/verdict no DISC view displays).
    Phase 1: Build a minimal rollup (answered/question count only).
    Phase 2: Write hiring_reports row.
    """
    from src.models.assessment_sessions import AssessmentSession
    from src.models.candidates import Candidate
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("evaluation_pipeline: session %s not found", session_id)
            return

        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        job_title = job.title if job else ""

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("evaluation_pipeline: question set not found for session %s", session_id)
            return

        candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
        candidate_name = candidate.name if candidate else "Unknown"

        questions = (
            db.query(SessionQuestion)
            .filter(SessionQuestion.question_set_id == qset.id)
            .order_by(SessionQuestion.sequence_no)
            .all()
        )

        # Phase 1 — minimal rollup: just how many questions were answered
        # (feeds the AI Confidence Score's coverage input). No per-competency
        # scores exist for a DISC-only assessment, so those stay empty.
        answered_count = sum(1 for q in questions if q.answer_text)
        rollup = {
            "competency_scores": {},
            "composite_scores": {},
            "overall": 0.0,
            "question_count": len(questions),
            "answered_count": answered_count,
        }
        verdict = derive_verdict(rollup["overall"])
        logger.info(
            "evaluation_pipeline: phase 1 complete — %d/%d questions answered for session %s",
            answered_count,
            len(questions),
            session_id,
        )

        # Phase 3 — write report (exec summary added by report_service later)
        existing_report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if existing_report:
            existing_report.score_rollup = rollup
            existing_report.verdict = verdict
        else:
            report = HiringReport(
                org_id=session.org_id,
                session_id=session_id,
                score_rollup=rollup,
                verdict=verdict,
                executive_summary=None,
            )
            db.add(report)

        db.commit()
        logger.info(
            "evaluation_pipeline: report written session=%s verdict=%s overall=%.2f",
            session_id,
            verdict,
            rollup["overall"],
        )

        _generate_executive_summary(db, session_id, job_title, candidate_name, rollup, verdict)
        _run_behavior_inference(db, session_id, job)
        _run_integrity_checks(db, session_id)
        _run_recommendation(db, session_id)
        _run_report_generator(db, session_id)

    except Exception:
        logger.exception("evaluation_pipeline failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()


def _generate_executive_summary(
    db: Session,
    session_id: uuid.UUID,
    job_title: str,
    candidate_name: str,
    rollup: dict,
    verdict: str,
) -> None:
    try:
        from src.models.hiring_reports import HiringReport

        from agents.evaluation.summary import generate_summary

        result = generate_summary(job_title=job_title, rollup=rollup, verdict=verdict, candidate_name=candidate_name)
        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if report and result:
            report.executive_summary = result.get("executive_summary")
            report.suggested_hr_questions = result.get("suggested_hr_questions", [])
            report.recommended_next_round = result.get("recommended_next_round")
            report.training_needs = result.get("training_needs", [])
            db.commit()
    except Exception:
        logger.exception(
            "evaluation_pipeline: executive summary generation failed for session %s", session_id
        )


def _run_behavior_inference(
    db: Session,
    session_id: uuid.UUID,
    job,
) -> None:
    try:
        from agents.behavior_analysis.agent import infer_behavior

        org_working_style = (
            ", ".join(job.culture_values)
            if job and job.culture_values
            else None
        )
        infer_behavior(
            session_id=session_id,
            db_factory=lambda: db,
            org_working_style=org_working_style,
        )
    except Exception:
        logger.exception("behavior inference failed for session %s", session_id)


def _run_integrity_checks(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.integrity.agent import run_integrity_checks
        run_integrity_checks(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("integrity checks failed for session %s", session_id)


def _run_recommendation(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.recommendation.agent import synthesize_recommendation
        synthesize_recommendation(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("recommendation synthesis failed for session %s", session_id)


def _run_report_generator(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.report_generator.agent import generate_full_report
        generate_full_report(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("report generation failed for session %s", session_id)
