import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.question_generation.agent import run_question_generation_agent
from agents.question_generation.prompts import CATEGORY_TO_COMPETENCY, PROMPT_VERSION
from src.models.assessment_sessions import AssessmentSession
from src.models.candidate_profiles import CandidateProfile
from src.models.job_assessments import JobAssessment
from src.models.question_fingerprints import QuestionFingerprint
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
from src.modules.question_sets.embeddings import embed_texts
from src.modules.question_sets.schemas import QuestionItem, QuestionSetResponse

_SIMILARITY_THRESHOLD = 0.92
_DEFAULT_TARGET = 10


def _derive_category_counts(competency_weightage: dict, target: int) -> dict[str, int]:
    lower_weight: dict[str, float] = {k.lower().replace(" ", "_"): v for k, v in competency_weightage.items()}

    category_weights: dict[str, float] = {}
    for cat, alias in CATEGORY_TO_COMPETENCY.items():
        w = lower_weight.get(alias)
        if w is None:
            # substring fallback
            for k, v in lower_weight.items():
                if alias in k or k in alias:
                    w = v
                    break
        if w is not None:
            category_weights[cat] = float(w)

    if not category_weights:
        each = target // len(CATEGORY_TO_COMPETENCY)
        counts = {cat: each for cat in CATEGORY_TO_COMPETENCY}
        remainder = target - each * len(CATEGORY_TO_COMPETENCY)
        for cat in list(CATEGORY_TO_COMPETENCY.keys())[:remainder]:
            counts[cat] += 1
        return {k: v for k, v in counts.items() if v > 0}

    total_weight = sum(category_weights.values())
    counts: dict[str, int] = {}
    allocated = 0
    cats = list(category_weights.keys())
    for i, cat in enumerate(cats):
        if i == len(cats) - 1:
            counts[cat] = max(target - allocated, 0)
        else:
            n = round(category_weights[cat] / total_weight * target)
            counts[cat] = max(n, 0)
            allocated += counts[cat]
    return {k: v for k, v in counts.items() if v > 0}


def _is_duplicate(db: Session, org_id: uuid.UUID, embedding: list[float]) -> bool:
    row = db.execute(
        text(
            "SELECT 1 - (question_embedding <=> CAST(:vec AS vector)) AS similarity "
            "FROM question_fingerprints "
            "WHERE org_id = :org_id "
            "ORDER BY question_embedding <=> CAST(:vec AS vector) "
            "LIMIT 1"
        ),
        {"org_id": str(org_id), "vec": str(embedding)},
    ).fetchone()
    if row is None:
        return False
    return float(row[0]) >= _SIMILARITY_THRESHOLD


def _dedup(
    db: Session,
    org_id: uuid.UUID,
    questions: list[dict],
    embeddings: list[list[float]],
) -> list[tuple[dict, list[float]]]:
    return [
        (q, emb)
        for q, emb in zip(questions, embeddings)
        if not _is_duplicate(db, org_id, emb)
    ]


def _call_agent(
    job_profile: dict,
    candidate_profile_dict: dict,
    category_counts: dict,
    difficulty_level: str,
    risk_flags: list,
    count: int,
) -> list[dict] | None:
    return run_question_generation_agent(
        job_profile=job_profile,
        candidate_profile=candidate_profile_dict,
        category_weightage=category_counts,
        difficulty_level=difficulty_level,
        risk_flags=risk_flags,
        target_question_count=count,
    )


def generate_question_set(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    target: int = _DEFAULT_TARGET,
) -> QuestionSetResponse:
    session = db.query(AssessmentSession).filter_by(
        id=session_id, org_id=org_id
    ).first()
    if session is None:
        raise LookupError("Assessment session not found")

    job = db.query(JobAssessment).filter_by(
        id=session.job_assessment_id, org_id=org_id
    ).first()
    if job is None or job.job_profile is None:
        raise ValueError("Job profile not generated — retry job assessment creation")

    if session.candidate_profile_id is None:
        raise ValueError("Candidate profile not yet synthesized — run M3 first")

    profile = db.query(CandidateProfile).filter_by(
        id=session.candidate_profile_id, org_id=org_id
    ).first()
    if profile is None:
        raise ValueError("Candidate profile record missing — run M3 first")

    difficulty_level = job.job_profile.get("difficulty_level", "mid")
    category_counts = _derive_category_counts(job.competency_weightage or {}, target)
    risk_flags = profile.risk_flags or []

    candidate_profile_dict = {
        "summary": profile.summary,
        "skill_matrix": profile.skill_matrix,
        "strengths": profile.strengths,
        "risk_flags": risk_flags,
        "experience_matrix": profile.experience_matrix,
    }

    # Pass 1: target + 25% buffer
    first_count = target + math.ceil(target * 0.25)
    questions = _call_agent(
        job.job_profile, candidate_profile_dict, category_counts,
        difficulty_level, risk_flags, first_count,
    )
    if questions is None:
        raise RuntimeError("Question generation agent failed — retry request")

    embeddings = embed_texts([q["question"] for q in questions])
    accepted = _dedup(db, org_id, questions, embeddings)

    # Pass 2: fill the gap if needed
    if len(accepted) < target:
        gap = target - len(accepted)
        gap_questions = _call_agent(
            job.job_profile, candidate_profile_dict, category_counts,
            difficulty_level, risk_flags, gap + math.ceil(gap * 0.25),
        )
        if gap_questions:
            gap_embeddings = embed_texts([q["question"] for q in gap_questions])
            accepted += _dedup(db, org_id, gap_questions, gap_embeddings)

    if len(accepted) < target:
        raise RuntimeError(
            f"Could not generate {target} unique questions after 2 passes — retry request"
        )

    accepted = accepted[:target]

    # Ensure at least one resume-referenced question (M4-F03)
    if not any(q.get("resume_reference") for q, _ in accepted):
        ref_batch = _call_agent(
            job.job_profile, candidate_profile_dict, {"Behavioral": 2},
            difficulty_level, risk_flags, 2,
        )
        if ref_batch:
            ref_q = next((q for q in ref_batch if q.get("resume_reference")), None)
            if ref_q:
                ref_emb = embed_texts([ref_q["question"]])[0]
                if not _is_duplicate(db, org_id, ref_emb):
                    accepted[-1] = (ref_q, ref_emb)

    # Persist: question_set → session_questions → fingerprints → lock
    question_set = QuestionSet(
        org_id=org_id,
        session_id=session_id,
        generation_prompt_version=PROMPT_VERSION,
    )
    db.add(question_set)
    db.flush()

    session_questions: list[SessionQuestion] = []
    fingerprints: list[QuestionFingerprint] = []

    for seq, (q, emb) in enumerate(accepted, start=1):
        question_obj = {
            "question": q["question"],
            "category": q["category"],
            "target_competencies": q.get("target_competencies", []),
            "difficulty": q["difficulty"],
            "answer_format": q["answer_format"],
        }
        if q["answer_format"] == "multiple_choice":
            question_obj["options"] = q.get("options", [])

        sq = SessionQuestion(
            org_id=org_id,
            question_set_id=question_set.id,
            sequence_no=seq,
            question=question_obj,
            category=q["category"],
            target_competencies=q.get("target_competencies", []),
            difficulty=q["difficulty"],
            answer_format=q["answer_format"],
            options=q.get("options") if q["answer_format"] == "multiple_choice" else None,
        )
        session_questions.append(sq)
        fingerprints.append(QuestionFingerprint(
            org_id=org_id,
            question_text=q["question"],
            question_embedding=emb,
            question_set_id=question_set.id,
        ))

    db.add_all(session_questions)
    db.add_all(fingerprints)
    db.flush()

    question_set.locked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(question_set)
    for sq in session_questions:
        db.refresh(sq)

    return _build_response(question_set, session_questions)


def get_question_set(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
) -> QuestionSetResponse:
    qs = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if qs is None:
        raise LookupError("Question set not found — generate it first")

    # Verify the set belongs to this org
    if str(qs.org_id) != str(org_id):
        raise LookupError("Question set not found")

    sqs = (
        db.query(SessionQuestion)
        .filter_by(question_set_id=qs.id, org_id=org_id)
        .order_by(SessionQuestion.sequence_no)
        .all()
    )
    return _build_response(qs, sqs)


def _build_response(qs: QuestionSet, sqs: list[SessionQuestion]) -> QuestionSetResponse:
    items = [
        QuestionItem(
            id=sq.id,
            sequence_no=sq.sequence_no,
            question=sq.question.get("question", ""),
            category=sq.category,
            target_competencies=list(sq.target_competencies),
            difficulty=sq.difficulty,
            answer_format=sq.answer_format,
            options=list(sq.options) if sq.options else None,
        )
        for sq in sorted(sqs, key=lambda x: x.sequence_no)
    ]
    return QuestionSetResponse(
        id=qs.id,
        session_id=qs.session_id,
        generated_at=qs.generated_at,
        locked_at=qs.locked_at,
        generation_prompt_version=qs.generation_prompt_version,
        questions=items,
    )
