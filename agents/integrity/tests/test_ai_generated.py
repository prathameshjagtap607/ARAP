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


# Case 1: Fewer than 2 long_text questions → skip, no flags
def test_too_few_long_text_skips():
    session = _make_session()
    qs = [_make_q(1, "Short answer.", fmt="short_text")]
    result = check_ai_generated(qs, session)
    assert result == []


# Case 2: Varied answers (different sentence counts, reasonable latency) → no flag
def test_varied_answers_no_flag():
    session = _make_session()
    qs = [
        _make_q(1, "I worked at Acme for three years. I built the billing pipeline. It handled $2M/day.", fmt="long_text", answered_offset_s=600),
        _make_q(2, "Yeah, I know Python well. I have used it since college. Sometimes I use Go.", fmt="long_text", answered_offset_s=900),
        _make_q(3, "My biggest challenge was a database migration. We had downtime risk. I solved it by staging the cutover. Then monitored for two days.", fmt="long_text", answered_offset_s=1200),
    ]
    result = check_ai_generated(qs, session)
    assert result == []


# Case 3: Uniform structure only (identical sentence count + all prose, reasonable latency) → flag low
def test_structural_uniformity_flag_low():
    session = _make_session()
    # All answers: exactly 2 sentences, all prose, within normal latency
    uniform_answer = "This is sentence one. This is sentence two."
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


# Case 4: Latency anomaly only (answer typed impossibly fast) → flag low
def test_latency_anomaly_flag_low():
    session = _make_session()
    # 500 chars in 10 seconds = 50 cps (threshold is 20)
    long_text = "x" * 500
    qs = [
        _make_q(1, long_text, fmt="long_text", answered_offset_s=10),
        _make_q(2, "Normal answer here. I took my time. It was good.", fmt="long_text", answered_offset_s=600),
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].severity == "low"
    assert "latency_max" in result[0].evidence


# Case 5: Two signals triggered → flag medium
def test_two_signals_medium():
    session = _make_session()
    uniform_answer = "This is sentence one. This is sentence two."
    qs = [
        _make_q(1, uniform_answer, fmt="long_text", answered_offset_s=10),   # latency anomaly
        _make_q(2, uniform_answer, fmt="long_text", answered_offset_s=300),
        _make_q(3, uniform_answer, fmt="long_text", answered_offset_s=600),  # structural uniform
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].severity == "medium"
