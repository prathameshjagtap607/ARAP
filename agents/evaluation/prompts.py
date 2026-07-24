PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = (
    "You are the Evaluation Agent for a structured recruitment assessment. "
    "Score only the competencies listed in target_competencies — never others. "
    "Use the 1-5 scale: 1=no evidence, 2=partial/weak, 3=adequate, 4=strong, 5=exceptional. "
    "For evidence_quote, copy an exact verbatim excerpt from the candidate's answer. "
    "Be concise and specific."
)


def build_evaluation_tool(target_competencies: list[str]) -> dict:
    return {
        "name": "evaluate_answer",
        "description": "Score the candidate answer against the specified competencies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competency_scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "competency": {
                                "type": "string",
                                "enum": target_competencies,
                            },
                            "score": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "explanation": {"type": "string"},
                            "evidence_quote": {
                                "type": "string",
                                "description": "Verbatim excerpt from the candidate's answer.",
                            },
                            "strength": {"type": "string"},
                            "improvement": {"type": "string"},
                        },
                        "required": [
                            "competency", "score", "explanation",
                            "evidence_quote", "strength", "improvement",
                        ],
                    },
                    "minItems": len(target_competencies),
                    "maxItems": len(target_competencies),
                }
            },
            "required": ["competency_scores"],
        },
    }
