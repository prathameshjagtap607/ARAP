import sys
import uuid
from unittest.mock import MagicMock, patch

# Mock ORM models before importing the module under test
_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.answer_corpus": MagicMock(),
    "src.modules": MagicMock(),
    "src.modules.question_sets": MagicMock(),
    "src.modules.question_sets.embeddings": MagicMock(),
}

_ORG_ID = uuid.uuid4()
_SESSION_ID = uuid.uuid4()


def _make_session():
    s = MagicMock()
    s.org_id = _ORG_ID
    s.id = _SESSION_ID
    return s


def _make_q(text="Some answer text here.", fmt="long_text"):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.answer_text = text
    q.answer_format = fmt
    return q


def _make_db(similarity_rows):
    """similarity_rows: list of (session_question_id, similarity) tuples returned by ANN query."""
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.fetchall.return_value = [
        MagicMock(session_question_id=r[0], similarity=r[1])
        for r in similarity_rows
    ]
    db.execute.return_value = execute_result
    return db


# Case 1: similarity >= 0.92 → flag high
def test_high_similarity_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import check_duplicate

        other_sq_id = uuid.uuid4()
        questions = [_make_q()]
        session = _make_session()
        db = _make_db([(other_sq_id, 0.95)])

        fake_embed = MagicMock(return_value=[[0.1] * 1536])
        with patch("agents.integrity.checks.duplicate._embed_answers", fake_embed):
            result = check_duplicate(questions, session, db)

    assert len(result) == 1
    assert result[0].flag_type == "duplicate_answer"
    assert result[0].severity == "high"
    assert "0.950" in result[0].evidence
    assert result[0].session_question_id == questions[0].id


# Case 2: similarity 0.87 → flag medium
def test_medium_similarity_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import check_duplicate

        other_sq_id = uuid.uuid4()
        questions = [_make_q()]
        session = _make_session()
        db = _make_db([(other_sq_id, 0.87)])

        with patch("agents.integrity.checks.duplicate._embed_answers", return_value=[[0.1] * 1536]):
            result = check_duplicate(questions, session, db)

    assert len(result) == 1
    assert result[0].severity == "medium"


# Case 3: similarity 0.80 → no flag
def test_low_similarity_no_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import check_duplicate

        other_sq_id = uuid.uuid4()
        questions = [_make_q()]
        session = _make_session()
        db = _make_db([(other_sq_id, 0.80)])

        with patch("agents.integrity.checks.duplicate._embed_answers", return_value=[[0.1] * 1536]):
            result = check_duplicate(questions, session, db)

    assert result == []


# Case 4: ingest_corpus bulk-inserts one row per answered question
def test_ingest_corpus_inserts_rows():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import ingest_corpus

        questions = [_make_q(), _make_q()]
        session = _make_session()
        db = MagicMock()
        embeddings = [[0.1] * 1536, [0.2] * 1536]

        ingest_corpus(questions, session, db, embeddings)

    assert db.add.call_count == 2
    db.flush.assert_called_once()
