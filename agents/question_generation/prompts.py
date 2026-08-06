PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = (
    "You are the Question Generation Agent for a DISC personality assessment. "
    "EVERY question you generate is category 'DISC' — this is a pure personality/"
    "behavioral assessment, never a technical, skill, or knowledge test. "
    "Generate the COMPLETE question set for this candidate in one pass. Never "
    "repeat or closely paraphrase any question already generated for this org's "
    "question-fingerprint history. Match the difficulty level supplied. "
    "IMPORTANT: the input's overall job difficulty_level (junior/mid/senior/"
    "executive) is a DIFFERENT field from each question's own 'difficulty' "
    "value. Each question's 'difficulty' MUST be exactly one of: easy, medium, "
    "hard, expert — never reuse the job difficulty_level word (e.g. never "
    "output 'mid'; use 'medium' instead). "
    "target_competencies MUST only contain values from the fixed competency "
    "vocabulary provided in the tool schema. "
    "\n\nSTRICT FORMAT for every question: write a short, concrete workplace "
    "scenario relevant to the candidate's role (a situation involving a "
    "deadline, a disagreement, a decision, a team dynamic, etc.), then give "
    "EXACTLY 4 options — never 3, never 5. Each of the 4 options must be a "
    "DIFFERENT ACTION the candidate could take IN THAT SCENARIO, each written "
    "in a distinctly different DISC style: "
    "Dominance (takes charge, pushes for a fast decisive outcome), "
    "Influence (persuades/rallies others, prioritizes relationships and morale), "
    "Steadiness (stays calm, seeks consensus, prefers a steady/patient approach), "
    "Conscientiousness (analyzes the facts/data first, follows process carefully). "
    "Do not label the options with D/I/S/C — only phrase them so each one "
    "reflects one style; the behavior-analysis step infers the candidate's "
    "style from which option they pick. "
    "\n\nNEVER generate generic self-rating or self-assessment options such as "
    "'I have no experience' / 'I have some experience' / 'I have a lot of "
    "experience', or any option that ranks/grades the candidate on a scale — "
    "these are NOT DISC options and must never appear. Every option must be a "
    "concrete ACTION taken in response to the scenario, not a self-description."
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
    "DISC": "disc",
}

VALID_CATEGORIES = list(CATEGORY_TO_COMPETENCY.keys())
VALID_COMPETENCIES = sorted(set(CATEGORY_TO_COMPETENCY.values()))

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
                            "items": {"type": "string", "enum": ["disc"]},
                            "description": "Always exactly ['disc'] — every question in this assessment is DISC.",
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
                            "minItems": 4,
                            "maxItems": 4,
                            "description": (
                                "EXACTLY 4 options — one per DISC style (Dominance/Influence/"
                                "Steadiness/Conscientiousness), each a concrete action in the "
                                "scenario, never a self-rating."
                            ),
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
