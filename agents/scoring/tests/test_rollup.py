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
