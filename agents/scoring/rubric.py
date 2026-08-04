DIFFICULTY_WEIGHTS: dict[str, float] = {
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0,
    "expert": 3.0,
}

COMPOSITES: list[str] = ["Technical", "Leadership", "Communication", "Behavior"]

COMPETENCY_TO_COMPOSITE: dict[str, str] = {
    "technical": "Technical",
    "problem_solving": "Technical",
    "analytical": "Technical",
    "financial": "Technical",
    "business_strategy": "Technical",
    "leadership": "Leadership",
    "decision_making": "Leadership",
    "innovation": "Leadership",
    "priority_management": "Leadership",
    "negotiation": "Leadership",
    "communication": "Communication",
    "presentation": "Communication",
    "conflict_resolution": "Communication",
    "customer_handling": "Communication",
    "ethics": "Behavior",
    "culture_fit": "Behavior",
    "stress": "Behavior",
    "situational_judgment": "Behavior",
    "behavioral": "Behavior",
    "case_study": "Technical",
    "scenario": "Technical",
    "disc": "Behavior",
}

# Ordered high → low; first threshold the overall score meets wins.
VERDICT_BANDS: list[tuple[float, str]] = [
    (4.25, "strong_hire"),
    (3.50, "hire"),
    (2.75, "consider"),
    (2.00, "borderline"),
]


def derive_verdict(overall: float) -> str:
    for threshold, verdict in VERDICT_BANDS:
        if overall >= threshold:
            return verdict
    return "reject"
