
from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.integrity.checks.ai_generated import FlagResult

_HIGH_THRESHOLD = 0.92
_MEDIUM_THRESHOLD = 0.85


def check_duplicate(questions: list, session, db: Session) -> list[FlagResult]:
    answered = [q for q in questions if q.answer_text]
    if not answered:
        return []

    embeddings = _embed_answers([q.answer_text for q in answered])
    flags: list[FlagResult] = []

    for q, embedding in zip(answered, embeddings):
        rows = db.execute(
            text(
                "SELECT session_question_id, "
                "1 - (answer_embedding <=> CAST(:vec AS vector)) AS similarity "
                "FROM answer_corpus "
                "WHERE org_id = :org_id "
                "ORDER BY answer_embedding <=> CAST(:vec AS vector) "
                "LIMIT 3"
            ),
            {"vec": str(embedding), "org_id": str(session.org_id)},
        ).fetchall()

        for row in rows:
            sim: float = row.similarity
            if sim >= _HIGH_THRESHOLD:
                severity = "high"
            elif sim >= _MEDIUM_THRESHOLD:
                severity = "medium"
            else:
                continue
            flags.append(
                FlagResult(
                    flag_type="duplicate_answer",
                    severity=severity,
                    evidence=(
                        f"cosine_similarity={sim:.3f} "
                        f"vs session_question_id={row.session_question_id}"
                    ),
                    session_question_id=q.id,
                )
            )
            break  # one flag per answer (highest match only)

    return flags


def ingest_corpus(
    questions: list,
    session,
    db: Session,
    embeddings: list[list[float]] | None = None,
) -> None:
    from src.models.answer_corpus import AnswerCorpus

    answered = [q for q in questions if q.answer_text]
    if not answered:
        return

    if embeddings is None:
        embeddings = _embed_answers([q.answer_text for q in answered])

    for q, embedding in zip(answered, embeddings):
        db.add(
            AnswerCorpus(
                org_id=session.org_id,
                session_id=session.id,
                session_question_id=q.id,
                answer_embedding=embedding,
            )
        )
    db.flush()


def _embed_answers(texts: list[str]) -> list[list[float]]:
    from src.modules.question_sets.embeddings import embed_texts
    return embed_texts(texts)
