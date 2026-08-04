_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

EXTRACT_SYSTEM_PROMPT = (
    "You are a behavioral analyst reading a structured interview transcript. "
    "Identify observable patterns in how the candidate communicates and reasons — "
    "language choice, decision framing, response structure, stress responses, "
    "conflict and teamwork patterns, and cross-answer themes. "
    "Questions tagged [DISC] present a scenario with options each phrased in a "
    "distinct DISC style (Dominance/Influence/Steadiness/Conscientiousness) — "
    "give the option the candidate picked on these questions the most weight "
    "when describing decision_framing and cross_answer_themes, since they are "
    "the strongest direct signal for DISC classification. "
    "Base every observation strictly on the text of the answers. "
    + _SECTION_15_EXCLUSION
)

EXTRACT_TOOL = {
    "name": "extract_behavioral_signals",
    "description": "Extract observable behavioral signals from the full Q&A transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "language_patterns": {
                "type": "string",
                "description": "Directive vs collaborative phrasing; use of 'I' vs 'we'; assertiveness level.",
            },
            "decision_framing": {
                "type": "string",
                "description": "Data-driven vs intuitive; risk tolerance; deliberate vs spontaneous.",
            },
            "response_structure": {
                "type": "string",
                "description": "Systematic/structured vs free-flowing; use of examples and frameworks.",
            },
            "stress_response": {
                "type": "string",
                "description": (
                    "Observable patterns in Stress-category answers. "
                    "Write 'No stress-category questions in this set.' if none present."
                ),
            },
            "conflict_eq_patterns": {
                "type": "string",
                "description": (
                    "Emotional intelligence indicators from Conflict Resolution and Teamwork answers. "
                    "Write 'No conflict or teamwork questions in this set.' if none present."
                ),
            },
            "cross_answer_themes": {
                "type": "string",
                "description": "Recurring patterns, values, or tendencies visible across multiple answers.",
            },
        },
        "required": [
            "language_patterns",
            "decision_framing",
            "response_structure",
            "stress_response",
            "conflict_eq_patterns",
            "cross_answer_themes",
        ],
    },
}

SYNTHESIZE_SYSTEM_PROMPT = (
    "You are a behavioral psychologist synthesizing a candidate's behavioral profile "
    "from pre-extracted interview signals. Produce concise, evidence-grounded assessments. "
    "For team_compatibility_signal, always begin with 'Recruiter discussion prompt:' and "
    "describe the candidate's collaboration style — never render a hiring verdict. "
    + _SECTION_15_EXCLUSION
)


def build_synthesize_tool(org_working_style: str | None) -> dict:
    team_compat_desc = (
        "Recruiter discussion prompt: describe the candidate's preferred collaboration style "
        "and how it might complement or contrast with the org working style: "
        f"'{org_working_style}'."
        if org_working_style
        else (
            "Recruiter discussion prompt: describe the candidate's preferred collaboration "
            "style. Always begin with 'Recruiter discussion prompt:'."
        )
    )
    return {
        "name": "synthesize_behavior_profile",
        "description": "Synthesize behavioral signals into a structured behavior profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "disc_style": {
                    "type": "object",
                    "properties": {
                        "primary": {"type": "string", "enum": ["D", "I", "S", "C"]},
                        "secondary": {"type": "string", "enum": ["D", "I", "S", "C"]},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "rationale": {"type": "string"},
                    },
                    "required": ["primary", "secondary", "confidence", "rationale"],
                },
                "big_five": {
                    "type": "object",
                    "properties": {
                        "openness": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "conscientiousness": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "extraversion": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "agreeableness": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "emotional_stability": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                    },
                    "required": [
                        "openness", "conscientiousness", "extraversion",
                        "agreeableness", "emotional_stability",
                    ],
                },
                "leadership_style": {"type": "string"},
                "decision_style": {"type": "string"},
                "communication_style": {"type": "string"},
                "work_style": {"type": "string"},
                "stress_signal": {"type": "string"},
                "eq_signal": {"type": "string"},
                "team_compatibility_signal": {
                    "type": "string",
                    "description": team_compat_desc,
                },
            },
            "required": [
                "disc_style", "big_five", "leadership_style", "decision_style",
                "communication_style", "work_style", "stress_signal", "eq_signal",
                "team_compatibility_signal",
            ],
        },
    }
