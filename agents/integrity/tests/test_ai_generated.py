import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from agents.integrity.checks.ai_generated import FlagResult, check_ai_generated


def _make_session(started_at=None):
    class Sess:
        pass
    sess = Sess()
    sess.started_at = started_at or datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    return sess


def _make_q(seq, text, fmt="long_text", answered_offset_s=300):
    class Q:
        pass
    q = Q()
    q.id = uuid.uuid4()
    q.sequence_no = seq
    q.answer_text = text
    q.answer_format = fmt
    q.answered_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=answered_offset_s)
    return q


# Case 1: fewer than 2 long_text questions → skip, no flags
def test_too_few_long_text_skips():
    session = _make_session()
    qs = [_make_q(1, "Short answer.", fmt="short_text")]
    result = check_ai_generated(qs, session)
    assert result == []


# Case 2: varied sentence counts (std_dev=2.0 > 1.5) → no structural flag;
#          slow answers → no latency flag → no flags at all
def test_varied_answers_no_flag():
    session = _make_session()
    # sentence counts: 1, 5, 3 → pstdev = 1.63 > 1.5 → structural does NOT fire
    qs = [
        _make_q(1, "One sentence only.", fmt="long_text", answered_offset_s=300),
        _make_q(2, "A. B. C. D. E.", fmt="long_text", answered_offset_s=600),
        _make_q(3, "First. Second. Third.", fmt="long_text", answered_offset_s=900),
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert result == []


# Case 3: uniform sentence counts (std_dev=0 < 1.5) + slow (0.14 cps < 20) → structural only → low
def test_structural_uniformity_flag_low():
    session = _make_session()
    # all 2-sentence prose answers, submitted slowly
    uniform_answer = "This is sentence one. This is sentence two."  # 43 chars
    qs = [
        _make_q(i, uniform_answer, fmt="long_text", answered_offset_s=300 * i)
        for i in range(1, 4)
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].flag_type == "ai_generated"
    assert result[0].severity == "low"
    assert result[0].session_question_id is None


# Case 4: fast answer (500 chars / 10s = 50 cps > 20) + varied counts (pstdev=2.5 > 1.5) → latency only → low
def test_latency_anomaly_flag_low():
    session = _make_session()
    # Q1: 500 chars in 10s = 50 cps (fires latency)
    # Q2: 5 sentences vs Q1's 0 → pstdev([0,5])=2.5 > 1.5 → structural does NOT fire
    qs = [
        _make_q(1, "x" * 500, fmt="long_text", answered_offset_s=10),
        _make_q(2, "First. Second. Third. Fourth. Fifth.", fmt="long_text", answered_offset_s=600),
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].severity == "low"
    assert "latency_max" in result[0].evidence


# Case 5: uniform counts (std_dev=0 < 1.5) + fast (50cps > 20) → both signals → medium
def test_two_signals_medium():
    session = _make_session()
    # 506-char uniform answer: sentence_count=23 for all, pstdev=0 < 1.5 → structural fires
    # Q1 submitted in 10s: 506/10=50.6 cps > 20 → latency fires
    long_uniform = "This is sentence one. " * 23  # ~506 chars, 23 sentences
    qs = [
        _make_q(1, long_uniform, fmt="long_text", answered_offset_s=10),
        _make_q(2, long_uniform, fmt="long_text", answered_offset_s=300),
        _make_q(3, long_uniform, fmt="long_text", answered_offset_s=600),
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].severity == "medium"
