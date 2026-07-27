import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import anthropic
from sqlalchemy.orm import Session

from agents.report_generator.prompts import (
    NARRATIVE_SYSTEM_PROMPT,
    NARRATIVE_TOOL,
    STRUCTURED_SYSTEM_PROMPT,
    STRUCTURED_TOOL,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096
_HIRE_BAR = 3.50


def _get_org_historical_bar(db: Session, role_family: str | None, org_id) -> str | float:
    if not role_family:
        return "insufficient_data"
    from src.models.assessment_sessions import AssessmentSession
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment

    rows = (
        db.query(HiringReport)
        .join(AssessmentSession, HiringReport.session_id == AssessmentSession.id)
        .join(JobAssessment, AssessmentSession.job_assessment_id == JobAssessment.id)
        .filter(
            JobAssessment.role_family == role_family,
            JobAssessment.org_id == org_id,
            HiringReport.verdict.in_(["hire", "strong_hire"]),
        )
        .all()
    )
    overalls = [r.score_rollup.get("overall") for r in rows if r.score_rollup and r.score_rollup.get("overall")]
    if len(overalls) < 3:
        return "insufficient_data"
    overalls.sort()
    mid = len(overalls) // 2
    median = overalls[mid] if len(overalls) % 2 else (overalls[mid - 1] + overalls[mid]) / 2
    return round(median, 4)


def _build_score_section(composite_scores: dict, org_bar) -> dict:
    scores = {}
    for composite, score in composite_scores.items():
        delta_job = round(score - _HIRE_BAR, 2)
        vs_job = f"{'+' if delta_job >= 0 else ''}{delta_job}"
        if org_bar == "insufficient_data":
            vs_org = "insufficient_data"
        else:
            delta_org = round(score - float(org_bar), 2)
            vs_org = f"{'+' if delta_org >= 0 else ''}{delta_org}"
        scores[composite.lower()] = {"score": round(score, 2), "vs_job_bar": vs_job, "vs_org_bar": vs_org}
    return scores


def generate_full_report(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.candidate_profiles import CandidateProfile
    from src.models.candidates import Candidate
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("generate_full_report: session %s not found", session_id)
            return

        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if not report:
            logger.error("generate_full_report: no report for session %s", session_id)
            return

        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
        behavior = db.query(BehaviorProfile).filter_by(session_id=session_id).first()
        candidate_profile = None
        if session.candidate_profile_id:
            candidate_profile = db.query(CandidateProfile).filter_by(id=session.candidate_profile_id).first()
        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        questions = []
        if qset:
            questions = (
                db.query(SessionQuestion)
                .filter(
                    SessionQuestion.question_set_id == qset.id,
                    SessionQuestion.answer_text.isnot(None),
                )
                .order_by(SessionQuestion.sequence_no)
                .all()
            )

        rollup = dict(report.score_rollup or {})
        composite_scores = rollup.get("composite_scores", {})
        integrity_summary = dict(report.integrity_summary or {})
        confidence = float(report.ai_confidence_score or 0)
        requires_human_review = confidence < 60

        org_bar = _get_org_historical_bar(db, getattr(job, "role_family", None), session.org_id)
        score_section = _build_score_section(composite_scores, org_bar)

        answer_excerpts = "\n".join(
            f"Q{q.sequence_no} [{q.category}]: {q.question.get('text', '')}\n"
            f"A: {q.answer_text}\n"
            f"Evaluation note: {(q.evaluation or {}).get('explanation', '')}"
            for q in questions
        )

        behavior_text = ""
        if behavior:
            behavior_text = (
                f"DISC: {behavior.disc_style}, Big Five: {behavior.big_five}, "
                f"Leadership: {behavior.leadership_style}, EQ: {behavior.eq_signal}"
            )

        narrative_input = "\n".join([
            f"Candidate: {candidate.name if candidate else 'Unknown'}",
            f"Role: {job.title if job else 'Unknown'}",
            f"Verdict: {report.verdict}",
            f"Verdict reasoning: {(report.full_report or {}).get('_recommendation_context', {}).get('verdict_reasoning', '')}",
            f"Overall score: {rollup.get('overall', 0):.2f} / 5.0",
            "Composite scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in composite_scores.items()),
            f"Salary band: {report.salary_band}",
            (f"Integrity: risk={integrity_summary.get('overall_risk', 'low')}, "
            f"flags={integrity_summary.get('flagged_count', 0)}"),
            f"Behavior: {behavior_text or 'Not available'}",
            f"Resume summary: {candidate_profile.summary if candidate_profile else 'Not available'}",
            f"Culture values: {', '.join(getattr(job, 'culture_values', []))}",
            "",
            "Answer excerpts (use Q numbers when citing):",
            answer_excerpts or "No answers available.",
        ])

        client = anthropic.Anthropic()

        # Call 1 — narrative sections
        narrative_resp = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=NARRATIVE_SYSTEM_PROMPT,
            tools=[NARRATIVE_TOOL],
            tool_choice={"type": "tool", "name": "generate_report_narrative"},
            messages=[{"role": "user", "content": narrative_input}],
        )
        narrative_block = next(b for b in narrative_resp.content if b.type == "tool_use")
        narrative = dict(narrative_block.input)

        # Call 2 — structured sections
        structured_input = "\n".join([
            "Narrative summary (for context):",
            narrative.get("executive_summary", ""),
            narrative.get("skill_gap_analysis", ""),
            "",
            "Score data:",
            "Composite scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in composite_scores.items()),
            f"Salary band: {report.salary_band}",
            "Existing CEO questions from recommendation: "
            + ", ".join(report.suggested_ceo_questions or []),
            "Training needs from recommendation: " + ", ".join(report.training_needs or []),
        ])
        structured_resp = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=STRUCTURED_SYSTEM_PROMPT,
            tools=[STRUCTURED_TOOL],
            tool_choice={"type": "tool", "name": "generate_report_structured"},
            messages=[{"role": "user", "content": structured_input}],
        )
        structured_block = next(b for b in structured_resp.content if b.type == "tool_use")
        structured = dict(structured_block.input)

        full_report = {
            "meta": {
                "schema_version": "1.0",
                "generated_at": datetime.now(UTC).isoformat(),
                "requires_human_review": requires_human_review,
                "confidence_rationale": (
                    f"AI confidence score: {confidence}. "
                    + ("Mandatory human review required (score < 60)." if requires_human_review else "")
                ),
            },
            "executive_summary": narrative["executive_summary"],
            "candidate_overview": narrative["candidate_overview"],
            "resume_summary": narrative["resume_summary"],
            "interview_summary": narrative["interview_summary"],
            "scores": score_section,
            "overall_rating": round(rollup.get("overall", 0), 2),
            "culture_fit": narrative["culture_fit"],
            "domain_knowledge": narrative["domain_knowledge"],
            "skill_gap_analysis": narrative["skill_gap_analysis"],
            "strengths": narrative["strengths"],
            "weaknesses": narrative["weaknesses"],
            "potential_risks": narrative["potential_risks"],
            "learning_curve_estimate": narrative["learning_curve_estimate"],
            "management_readiness": narrative["management_readiness"],
            "promotion_potential": narrative["promotion_potential"],
            "salary_recommendation": {
                "band": report.salary_band,
                "rationale": (report.full_report or {}).get("_recommendation_context", {}).get("salary_band_rationale", ""),
            },
            "ai_confidence_score": confidence,
            "recommended_next_round": structured["recommended_next_round"],
            "training_needs": structured["training_needs_detailed"],
            "suggested_hr_questions": structured["suggested_hr_questions"],
            "suggested_ceo_questions": structured["suggested_ceo_questions"],
            "integrity_summary": integrity_summary,
            "integrity_summary_prose": narrative["integrity_summary_prose"],
            "final_verdict": narrative["final_verdict"],
        }

        report.full_report = full_report
        report.executive_summary = narrative["executive_summary"]
        report.recommended_next_round = structured["recommended_next_round"]
        report.suggested_hr_questions = structured["suggested_hr_questions"]

        db.commit()
        logger.info("generate_full_report: complete for session %s", session_id)

    except Exception:
        logger.exception("generate_full_report failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()
