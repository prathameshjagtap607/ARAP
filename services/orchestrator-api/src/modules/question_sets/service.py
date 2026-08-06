import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from agents.question_generation.agent import run_question_generation_agent
from agents.question_generation.prompts import PROMPT_VERSION
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
_OPTION_LETTERS = "ABCDEFGH"


def _options_list_to_dict(options: list[str]) -> dict[str, str]:
    return {_OPTION_LETTERS[i]: opt for i, opt in enumerate(options)}


def _resolve_competency_names(db: Session, org_id: uuid.UUID, competency_weightage: dict) -> dict:
    """job_assessments.competency_weightage is keyed by competency_library UUIDs
    (set by the assessment form), but category matching in _derive_category_counts
    works on names like "leadership". Resolve UUID keys to their library names
    so weightage is actually respected instead of silently falling back to an
    equal split across every category.
    """
    from src.models.competency_library import CompetencyLibrary

    resolved: dict[str, float] = {}
    id_keys: list[str] = []
    for key, weight in competency_weightage.items():
        try:
            uuid.UUID(str(key))
            id_keys.append(str(key))
        except (ValueError, AttributeError, TypeError):
            resolved[key] = weight  # not a UUID — already a plain name, keep as-is

    if id_keys:
        rows = (
            db.query(CompetencyLibrary)
            .filter(CompetencyLibrary.org_id == org_id, CompetencyLibrary.id.in_(id_keys))
            .all()
        )
        id_to_name = {str(r.id): r.name for r in rows}
        for key in id_keys:
            name = id_to_name.get(key)
            if name:
                resolved[name] = competency_weightage[key]

    return resolved


def _derive_category_counts(competency_weightage: dict, target: int) -> dict[str, int]:
    # This assessment is a pure DISC personality test: every generated
    # question is DISC-style regardless of which competencies are selected
    # or how they're weighted. Competency selection still flows into the
    # DISC prompt as target_competencies context, but no other category
    # (Technical, Behavioral, Leadership, etc.) is generated.
    return {"DISC": target}


# NOTE: The HNSW index covers the full table (not org-scoped). PostgreSQL cannot
# use the index when an org_id WHERE predicate precedes the vector ORDER BY, so
# this degrades to a sequential scan at large fingerprint counts. The separate
# B-tree index on org_id mitigates this for the WHERE filter step. Acceptable
# at MVP scale; revisit with IVFFlat per-org partitioning if fingerprints exceed ~100k rows.
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


def _dedup_within_batch(
    accepted: list[tuple[dict, list[float]]],
) -> list[tuple[dict, list[float]]]:
    result: list[tuple[dict, list[float]]] = []
    for q, emb in accepted:
        emb_arr = emb
        duplicate = False
        for _, prev_emb in result:
            dot = sum(a * b for a, b in zip(emb_arr, prev_emb))
            norm_a = sum(a * a for a in emb_arr) ** 0.5
            norm_b = sum(b * b for b in prev_emb) ** 0.5
            similarity = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
            if similarity >= _SIMILARITY_THRESHOLD:
                duplicate = True
                break
        if not duplicate:
            result.append((q, emb))
    return result


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
    resolved_weightage = _resolve_competency_names(db, org_id, job.competency_weightage or {})
    category_counts = _derive_category_counts(resolved_weightage, target)
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
    accepted = _dedup_within_batch(accepted)

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
            accepted = _dedup_within_batch(accepted)

    if len(accepted) < target:
        raise RuntimeError(
            f"Could not generate {target} unique questions after 2 passes — retry request"
        )

    accepted = accepted[:target]

    # Ensure at least one resume-referenced question (M4-F03)
    if not any(q.get("resume_reference") for q, _ in accepted):
        ref_batch = _call_agent(
            job.job_profile, candidate_profile_dict, {"DISC": 2},
            difficulty_level, risk_flags, 2,
        )
        if ref_batch:
            ref_q = next((q for q in ref_batch if q.get("resume_reference")), None)
            if ref_q:
                ref_emb = embed_texts([ref_q["question"]])[0]
                if not _is_duplicate(db, org_id, ref_emb):
                    accepted[-1] = (ref_q, ref_emb)
        if not any(q.get("resume_reference") for q, _ in accepted):
            logger.warning(
                "M4-F03: resume_reference enforcement failed — persisting question set without a resume-referenced question"
            )

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
        options_dict = (
            _options_list_to_dict(q.get("options", []))
            if q["answer_format"] == "multiple_choice"
            else None
        )

        question_obj = {
            "text": q["question"],
            "category": q["category"],
            "target_competencies": q.get("target_competencies", []),
            "difficulty": q["difficulty"],
            "answer_format": q["answer_format"],
        }
        if options_dict is not None:
            question_obj["options"] = options_dict

        sq = SessionQuestion(
            org_id=org_id,
            question_set_id=question_set.id,
            sequence_no=seq,
            question=question_obj,
            category=q["category"],
            target_competencies=q.get("target_competencies", []),
            difficulty=q["difficulty"],
            answer_format=q["answer_format"],
            options=options_dict,
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
    qs = db.query(QuestionSet).filter_by(session_id=session_id, org_id=org_id).first()
    if qs is None:
        raise LookupError("Question set not found — generate it first")

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
            question=sq.question.get("text", ""),
            category=sq.category,
            target_competencies=list(sq.target_competencies),
            difficulty=sq.difficulty,
            answer_format=sq.answer_format,
            options=list(sq.options.values()) if sq.options else None,
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
