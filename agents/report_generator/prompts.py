_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

NARRATIVE_SYSTEM_PROMPT = (
    "You are a senior HR analyst writing sections of a hiring report. "
    "Base every statement strictly on the data provided. "
    "Every strength and weakness bullet MUST include a direct quote from the candidate's answer, "
    "formatted as: '…(cited from Q{n}: \"…excerpt…\")'. "
    "Never invent quotes or information not present in the input. "
    "The final_verdict must be a full paragraph — never a bare label. "
    + _SECTION_15_EXCLUSION
)

NARRATIVE_TOOL = {
    "name": "generate_report_narrative",
    "description": "Write all narrative prose sections of the hiring report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-3 sentences. State verdict with reasoning. Never a bare label.",
            },
            "candidate_overview": {
                "type": "string",
                "description": "2-3 sentences on the candidate's background and suitability.",
            },
            "resume_summary": {
                "type": "string",
                "description": "3-4 sentences summarising key experience from the parsed resume.",
            },
            "interview_summary": {
                "type": "string",
                "description": "3-4 sentences on overall interview performance across categories.",
            },
            "culture_fit": {
                "type": "string",
                "description": "2-3 sentences on alignment with org culture values provided.",
            },
            "domain_knowledge": {
                "type": "string",
                "description": "2-3 sentences on depth of domain expertise evidenced in answers.",
            },
            "skill_gap_analysis": {
                "type": "string",
                "description": "Paragraph identifying skills below the job bar with specific evidence.",
            },
            "strengths": {
                "type": "array",
                "description": "2-4 strength bullets. Each MUST cite a quoted answer excerpt.",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "weaknesses": {
                "type": "array",
                "description": "2-4 weakness bullets. Each MUST cite a quoted answer excerpt.",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "potential_risks": {
                "type": "string",
                "description": "Paragraph on risks if hired, based on score patterns and integrity flags.",
            },
            "learning_curve_estimate": {
                "type": "string",
                "description": "2-3 sentences estimating ramp-up time and key learning areas.",
            },
            "management_readiness": {
                "type": "string",
                "description": "2-3 sentences on readiness to manage a team, based on leadership scores.",
            },
            "promotion_potential": {
                "type": "string",
                "description": "2-3 sentences on long-term growth trajectory.",
            },
            "integrity_summary_prose": {
                "type": "string",
                "description": (
                    "Human-readable summary of integrity flags. If risk is low or no flags, "
                    "state 'No integrity concerns identified.' "
                    "Never suggest automatic rejection — human makes the call."
                ),
            },
            "final_verdict": {
                "type": "string",
                "description": (
                    "Full paragraph. Start with the verdict label, then explain with specific "
                    "score references and at least one behavioral observation."
                ),
            },
        },
        "required": [
            "executive_summary", "candidate_overview", "resume_summary", "interview_summary",
            "culture_fit", "domain_knowledge", "skill_gap_analysis", "strengths", "weaknesses",
            "potential_risks", "learning_curve_estimate", "management_readiness",
            "promotion_potential", "integrity_summary_prose", "final_verdict",
        ],
    },
}

STRUCTURED_SYSTEM_PROMPT = (
    "You are a senior HR analyst completing the structured data sections of a hiring report. "
    "Use the narrative context and score data provided. Be specific and consistent with the narrative. "
    + _SECTION_15_EXCLUSION
)

STRUCTURED_TOOL = {
    "name": "generate_report_structured",
    "description": "Write structured data sections: scores with benchmarks, questions, training needs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommended_next_round": {
                "type": "string",
                "description": "E.g. 'Technical Panel Interview' or 'Final HR Round'.",
            },
            "training_needs_detailed": {
                "type": "array",
                "description": "1-3 training needs with priority.",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string"},
                    },
                    "required": ["area", "priority", "rationale"],
                },
            },
            "suggested_hr_questions": {
                "type": "array",
                "description": "3 HR-round questions targeting weak competencies.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
            "suggested_ceo_questions": {
                "type": "array",
                "description": "3 CEO-round questions on strategic fit and leadership depth.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": [
            "recommended_next_round",
            "training_needs_detailed",
            "suggested_hr_questions",
            "suggested_ceo_questions",
        ],
    },
}
