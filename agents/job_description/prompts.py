SYSTEM_PROMPT = (
    "You are a job description normalization assistant. "
    "Given raw job assessment data, produce a structured job_profile JSON "
    "using the provided tool. Be concise and factual — do not invent requirements "
    "not present in the input."
)

JOB_PROFILE_TOOL = {
    "name": "produce_job_profile",
    "description": "Produce a normalized job_profile from the raw assessment data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "normalized_title": {"type": "string"},
            "role_summary": {"type": "string"},
            "key_responsibilities": {"type": "array", "items": {"type": "string"}},
            "required_skills": {"type": "array", "items": {"type": "string"}},
            "preferred_skills": {"type": "array", "items": {"type": "string"}},
            "education_requirements": {"type": "string"},
            "certifications": {"type": "array", "items": {"type": "string"}},
            "competency_weightage_map": {
                "type": "object",
                "additionalProperties": {"type": "number"},
            },
            "difficulty_level": {
                "type": "string",
                "enum": ["junior", "mid", "senior", "executive"],
            },
            "generated_at": {"type": "string", "format": "date-time"},
        },
        "required": [
            "normalized_title", "role_summary", "key_responsibilities",
            "required_skills", "preferred_skills", "education_requirements",
            "certifications", "competency_weightage_map", "difficulty_level",
            "generated_at",
        ],
    },
}
