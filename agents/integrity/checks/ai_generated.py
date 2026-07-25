import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import UTC

_LATENCY_THRESHOLD_CPS = 3.0
_STRUCTURAL_STD_THRESHOLD = 0.1
_PHRASING_SIM_THRESHOLD = 0.30


@dataclass
class FlagResult:
    flag_type: str
    severity: str
    evidence: str
    session_question_id: uuid.UUID | None


def check_ai_generated(questions: list, session) -> list[FlagResult]:
    long_qs = [q for q in questions if q.answer_format == "long_text" and q.answer_text]
    if len(long_qs) < 2:
        return []

    signals: list[str] = []
    stats_parts: list[str] = []

    # Signal 1: structural uniformity
    sentence_counts = [_count_sentences(q.answer_text) for q in long_qs]
    std_dev = statistics.pstdev(sentence_counts)
    all_same_format = all(_is_bulleted(q.answer_text) for q in long_qs) or all(
        not _is_bulleted(q.answer_text) for q in long_qs
    )
    stats_parts.append(f"structural_std={std_dev:.2f}")
    if std_dev < _STRUCTURAL_STD_THRESHOLD and all_same_format:
        signals.append("structural_uniformity")

    # Signal 2: latency anomaly
    started = session.started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    max_cps = 0.0
    if started:
        for q in long_qs:
            answered = q.answered_at
            if answered is None or not q.answer_text:
                continue
            if answered.tzinfo is None:
                answered = answered.replace(tzinfo=UTC)
            elapsed = (answered - started).total_seconds()
            if elapsed > 0:
                cps = len(q.answer_text) / elapsed
                max_cps = max(max_cps, cps)
    stats_parts.append(f"latency_max={max_cps:.1f}cps")
    if max_cps > _LATENCY_THRESHOLD_CPS:
        signals.append("latency_anomaly")

    # Signal 3: phrasing divergence (best-effort — skipped if embedding fails)
    all_answered = [q.answer_text for q in questions if q.answer_text]
    if all_answered:
        formal_texts = [q.answer_text for q in long_qs]
        casual = min(all_answered, key=len)
        embeddings = _embed_texts_safe(formal_texts + [casual])
        if embeddings is not None:
            formal_embs = embeddings[: len(formal_texts)]
            casual_emb = embeddings[-1]
            sims = [_cosine(fe, casual_emb) for fe in formal_embs]
            mean_sim = sum(sims) / len(sims)
            stats_parts.append(f"phrasing_sim={mean_sim:.2f}")
            if mean_sim < _PHRASING_SIM_THRESHOLD:
                signals.append("phrasing_divergence")

    if not signals:
        return []

    n = len(signals)
    severity = "low" if n == 1 else ("medium" if n == 2 else "high")
    return [
        FlagResult(
            flag_type="ai_generated",
            severity=severity,
            evidence=", ".join(stats_parts),
            session_question_id=None,
        )
    ]


def _count_sentences(text: str) -> int:
    return max(1, text.count(".") + text.count("!") + text.count("?"))


def _is_bulleted(text: str) -> bool:
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    bullet_lines = sum(1 for ln in lines if ln.strip().startswith(("-", "*", "•", "–")))
    return bullet_lines / len(lines) >= 0.5


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _embed_texts_safe(texts: list[str]) -> list[list[float]] | None:
    try:
        from src.modules.question_sets.embeddings import embed_texts
        return embed_texts(texts)
    except Exception:
        return None
