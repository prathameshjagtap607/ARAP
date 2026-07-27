import uuid
import pytest
from sqlalchemy import inspect, text

from src.models.orgs import Org
from src.models.question_fingerprints import QuestionFingerprint


def test_question_fingerprints_table_exists(engine):
    assert "question_fingerprints" in inspect(engine).get_table_names()


def test_question_fingerprints_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("question_fingerprints")}
    assert cols == {"id", "org_id", "question_text", "question_embedding", "question_set_id", "created_at"}


def test_insert_and_cosine_similarity(db, engine):
    org = Org(name="VecOrg")
    db.add(org)
    db.flush()

    vec_a = [0.1] * 1536
    vec_b = [0.1] * 1536  # identical → cosine distance 0
    vec_c = [-0.1] * 1536  # opposite → cosine distance 2

    qf_a = QuestionFingerprint(org_id=org.id, question_text="Q A", question_embedding=vec_a)
    qf_b = QuestionFingerprint(org_id=org.id, question_text="Q B", question_embedding=vec_b)
    qf_c = QuestionFingerprint(org_id=org.id, question_text="Q C", question_embedding=vec_c)
    db.add_all([qf_a, qf_b, qf_c])
    db.flush()

    # Nearest neighbour to vec_a should be qf_b (distance ≈ 0), not qf_c
    result = db.execute(
        text(
            "SELECT id FROM question_fingerprints "
            "WHERE org_id = :org_id AND id != :self_id "
            "ORDER BY question_embedding <=> CAST(:vec AS vector) "
            "LIMIT 1"
        ),
        {"org_id": str(org.id), "self_id": str(qf_a.id), "vec": str(vec_a)},
    ).fetchone()

    assert result is not None
    assert uuid.UUID(str(result[0])) == qf_b.id


def test_embedding_rejects_wrong_dimension(db):
    org = Org(name="DimOrg")
    db.add(org)
    db.flush()
    from sqlalchemy.exc import DataError
    with pytest.raises((DataError, Exception)):
        qf = QuestionFingerprint(org_id=org.id, question_text="Q", question_embedding=[0.1] * 10)
        db.add(qf)
        db.flush()
    db.rollback()
