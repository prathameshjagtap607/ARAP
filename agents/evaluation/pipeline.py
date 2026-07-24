import logging
import uuid
from typing import Callable

from sqlalchemy.orm import Session

from agents.evaluation.agent import score_answer
from agents.scoring.agent import roll_up
from agents.scoring.rubric import derive_verdict

logger = logging.getLogger(__name__)


def evaluation_pipeline(session_id: uuid.UUID, db_factory: Callable[[], Session]) -> None:
    """
    Runs after submit_session completes. Owns its own DB session (not request-scoped).
    Phase 1: Score each answered question via LLM.
    Phase 2: Roll up competency scores.
    Phase 3: Write hiring_reports row.
    """
    from src.models.assessment_sessions import AssessmentSession
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
        job_weightage = dict(job.competency_weightage) if job else {}

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("evaluation_pipeline: question set not found for session %s", session_id)
            return

        questions = (
            db.query(SessionQuestion)
            .filter(SessionQuestion.question_set_id == qset.id)
            .order_by(SessionQuestion.sequence_no)
            .all()
        )

        # Phase 1 — score each question
        evaluated: list[dict] = []
        for q in questions:
            eval_result = score_answer(
                question_text=q.question.get("text", ""),
                category=q.category,
                target_competencies=list(q.target_competencies),
                answer_text=q.answer_text,
                difficulty=q.difficulty,
                job_title=job_title,
            )
            q.evaluation = eval_result
            db.flush()
            evaluated.append({
                "target_competencies": list(q.target_competencies),
                "difficulty": q.difficulty,
                "evaluation": eval_result if "error" not in eval_result else None,
            })

        db.commit()
        logger.info(
            "evaluation_pipeline: scored %d questions for session %s",
            len(questions),
            session_id,
        )

        # Phase 2 — roll up
        rollup = roll_up(evaluated, job_weightage)
        verdict = derive_verdict(rollup["overall"])

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

        _generate_executive_summary(db, session_id, job_title, rollup, verdict)

    except Exception:
        logger.exception("evaluation_pipeline failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()


def _generate_executive_summary(
    db: Session,
    session_id: uuid.UUID,
    job_title: str,
    rollup: dict,
    verdict: str,
) -> None:
    try:
        from agents.evaluation.summary import generate_summary
        from src.models.hiring_reports import HiringReport

        result = generate_summary(job_title=job_title, rollup=rollup, verdict=verdict)
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
