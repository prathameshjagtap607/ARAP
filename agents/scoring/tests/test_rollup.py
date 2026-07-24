import pytest

from agents.scoring.agent import roll_up
from agents.scoring.rubric import (
    COMPETENCY_TO_COMPOSITE,
    COMPOSITES,
    DIFFICULTY_WEIGHTS,
    VERDICT_BANDS,
    derive_verdict,
)


def test_difficulty_weights_keys():
    assert set(DIFFICULTY_WEIGHTS) == {"easy", "medium", "hard", "expert"}
    assert DIFFICULTY_WEIGHTS["easy"] == 1.0
    assert DIFFICULTY_WEIGHTS["expert"] == 3.0


def test_composites_list():
    assert set(COMPOSITES) == {"Technical", "Leadership", "Communication", "Behavior"}


def test_competency_to_composite_coverage():
    assert len(COMPETENCY_TO_COMPOSITE) == 20, (
        f"Expected 20 competency entries, got {len(COMPETENCY_TO_COMPOSITE)}"
    )
    for comp, cat in COMPETENCY_TO_COMPOSITE.items():
        assert cat in COMPOSITES, f"{comp} maps to unknown composite {cat}"


def test_verdict_bands_coverage():
    # every verdict value must be one of the 5 PRD bands
    valid = {"strong_hire", "hire", "consider", "borderline", "reject"}
    for _, v in VERDICT_BANDS:
        assert v in valid


def test_derive_verdict_thresholds():
    assert derive_verdict(4.25) == "strong_hire"
    assert derive_verdict(4.5) == "strong_hire"
    assert derive_verdict(3.50) == "hire"
    assert derive_verdict(3.49) == "consider"
    assert derive_verdict(2.75) == "consider"
    assert derive_verdict(2.00) == "borderline"
    assert derive_verdict(1.99) == "reject"
    assert derive_verdict(0.0) == "reject"


def _make_q(competency: str, score: int, difficulty: str = "medium") -> dict:
    return {
        "target_competencies": [competency],
        "difficulty": difficulty,
        "evaluation": {
            "competency_scores": [{"competency": competency, "score": score}]
        },
    }


def test_rollup_single_question():
    questions = [_make_q("problem_solving", 4, "medium")]
    result = roll_up(questions, job_weightage={"problem_solving": 100.0})
    assert result["competency_scores"]["problem_solving"] == pytest.approx(4.0)
    assert result["composite_scores"]["Technical"] == pytest.approx(4.0)
    assert result["overall"] == pytest.approx(4.0)
    assert result["question_count"] == 1
    assert result["answered_count"] == 1


def test_rollup_difficulty_weighting():
    # easy score=2, hard score=4 → weighted: (2*1.0 + 4*2.0)/(1.0+2.0) = 10/3 ≈ 3.333
    questions = [
        _make_q("problem_solving", 2, "easy"),
        _make_q("problem_solving", 4, "hard"),
    ]
    result = roll_up(questions, job_weightage={"problem_solving": 100.0})
    assert result["competency_scores"]["problem_solving"] == pytest.approx(10 / 3, rel=1e-3)


def test_rollup_skips_unevaluated():
    # question with no evaluation key is not counted
    q_unevaluated = {"target_competencies": ["communication"], "difficulty": "easy", "evaluation": None}
    questions = [_make_q("problem_solving", 3), q_unevaluated]
    result = roll_up(questions, job_weightage={"problem_solving": 50.0, "communication": 50.0})
    assert "communication" not in result["competency_scores"]
    assert result["answered_count"] == 1


def test_rollup_overall_is_mean_of_composites():
    # Two composites, each with one competency
    questions = [
        _make_q("problem_solving", 4),   # Technical
        _make_q("communication", 2),      # Communication
    ]
    result = roll_up(questions, job_weightage={"problem_solving": 50.0, "communication": 50.0})
    expected_overall = (result["composite_scores"]["Technical"] + result["composite_scores"]["Communication"]) / 2
    assert result["overall"] == pytest.approx(expected_overall, rel=1e-3)


def test_rollup_empty_questions():
    result = roll_up([], job_weightage={})
    assert result["overall"] == 0.0
    assert result["competency_scores"] == {}
    assert result["composite_scores"] == {}
