PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = (
    "You are the Question Generation Agent for a personalized recruitment "
    "assessment. Generate the COMPLETE question set for this candidate in one "
    "pass. Never repeat or closely paraphrase any question already generated "
    "for this org's question-fingerprint history. Match the category weightage "
    "and difficulty level supplied. Every question MUST be multiple_choice — "
    "always provide 3-5 plausible options, even for scenario/case-study/"
    "negotiation-style questions. "
    "IMPORTANT: the input's overall job difficulty_level (junior/mid/senior/"
    "executive) is a DIFFERENT field from each question's own 'difficulty' "
    "value. Each question's 'difficulty' MUST be exactly one of: easy, medium, "
    "hard, expert — never reuse the job difficulty_level word (e.g. never "
    "output 'mid'; use 'medium' instead)."
)

# Maps PRD category names to lowercase competency key aliases for weight lookup.
CATEGORY_TO_COMPETENCY: dict[str, str] = {
    "Technical": "technical",
    "Behavioral": "behavioral",
    "Leadership": "leadership",
    "Case Study": "case_study",
    "Scenario": "scenario",
    "Decision-Making": "decision_making",
    "Conflict Resolution": "conflict_resolution",
    "Problem Solving": "problem_solving",
    "Analytical": "analytical",
    "Situational Judgment": "situational_judgment",
    "Communication": "communication",
    "Ethics": "ethics",
    "Innovation": "innovation",
    "Culture Fit": "culture_fit",
    "Stress": "stress",
    "Priority Management": "priority_management",
    "Negotiation": "negotiation",
    "Business Strategy": "business_strategy",
    "Financial": "financial",
    "Presentation": "presentation",
    "Customer Handling": "customer_handling",
}

VALID_CATEGORIES = list(CATEGORY_TO_COMPETENCY.keys())

QUESTION_GENERATION_TOOL: dict = {
    "name": "generate_question_set",
    "description": "Generate a complete personalized question set for the candidate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "category": {"type": "string", "enum": VALID_CATEGORIES},
                        "target_competencies": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard", "expert"],
                        },
                        "answer_format": {
                            "type": "string",
                            "enum": ["multiple_choice"],
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3-5 plausible answer options for this multiple_choice question.",
                        },
                        "resume_reference": {
                            "type": "boolean",
                            "description": "True if this question directly cites the candidate's resume.",
                        },
                    },
                    "required": [
                        "question", "category", "target_competencies",
                        "difficulty", "answer_format", "options", "resume_reference",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}
