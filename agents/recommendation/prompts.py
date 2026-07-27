_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

RECOMMENDATION_SYSTEM_PROMPT = (
    "You are a senior talent acquisition specialist writing a structured hiring recommendation. "
    "Base every claim strictly on the score data, behavior profile, and integrity summary provided. "
    "Do not invent information. The salary band must be a role-level descriptor (e.g. 'L3 / Mid-Senior'), "
    "never a monetary figure. Every verdict must be accompanied by specific reasoning citing scores. "
    + _SECTION_15_EXCLUSION
)

RECOMMENDATION_TOOL = {
    "name": "synthesize_recommendation",
    "description": "Synthesise scoring, behavior, and integrity data into a hiring recommendation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict_reasoning": {
                "type": "string",
                "description": (
                    "3-4 sentences explaining the verdict. Must cite specific composite scores "
                    "and at least one behavioral or integrity observation."
                ),
            },
            "salary_band": {
                "type": "string",
                "description": "Role-level band label e.g. 'L3 / Mid-Senior'. Never a monetary figure.",
            },
            "salary_band_rationale": {
                "type": "string",
                "description": "1-2 sentences explaining the band choice relative to difficulty_level and scores.",
            },
            "training_needs": {
                "type": "array",
                "description": "1-3 competency gaps to address if hired.",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["area", "priority"],
                },
            },
            "suggested_ceo_questions": {
                "type": "array",
                "description": "3 CEO-round questions targeting strategic fit and leadership depth.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": [
            "verdict_reasoning",
            "salary_band",
            "salary_band_rationale",
            "training_needs",
            "suggested_ceo_questions",
        ],
    },
}
