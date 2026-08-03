
SYSTEM_PROMPT = (
    "You are a resume parsing assistant. "
    "Given raw resume text and an optional job profile, extract structured candidate information "
    "using the provided tool. For each field, assign a confidence score between 0.0 and 1.0 "
    "reflecting how clearly the information was stated (1.0 = explicitly stated, "
    "0.5 = inferred, 0.0 = not found/guessed). Be factual — do not invent information."
)

RESUME_EXTRACTION_TOOL = {
    "name": "extract_resume",
    "description": "Extract structured candidate information from resume text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skills": {
                "type": "object",
                "properties": {
                    "explicit": {"type": "array", "items": {"type": "string"}},
                    "inferred": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["explicit", "inferred"],
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "tech": {"type": "array", "items": {"type": "string"}},
                        "description": {"type": "string"},
                    },
                    "required": ["name", "tech", "description"],
                },
            },
            "tech_used": {"type": "array", "items": {"type": "string"}},
            "employment_history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "start": {"type": "string"},
                        "end": {"type": ["string", "null"]},
                        "team_size": {"type": ["integer", "null"]},
                        "scope": {"type": ["string", "null"]},
                        "key_achievements": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["company", "title", "start", "end", "team_size", "scope", "key_achievements"],
                },
            },
            "education": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "degree": {"type": "string"},
                        "field": {"type": "string"},
                        "institution": {"type": ["string", "null"]},
                        "year": {"type": ["integer", "null"]},
                    },
                    "required": ["degree", "field", "institution", "year"],
                },
            },
            "certifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "issuer": {"type": "string"},
                        "year": {"type": ["integer", "null"]},
                    },
                    "required": ["name", "issuer", "year"],
                },
            },
            "achievements": {"type": "array", "items": {"type": "string"}},
            "leadership_indicators": {
                "type": "object",
                "properties": {
                    "max_team_size": {"type": ["integer", "null"]},
                    "scope": {"type": ["string", "null"]},
                    "budget_ownership": {"type": ["string", "null"]},
                },
                "required": ["max_team_size", "scope", "budget_ownership"],
            },
            "career_timeline": {
                "type": "object",
                "properties": {
                    "total_years": {"type": "number"},
                    "job_count": {"type": "integer"},
                    "gaps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "months": {"type": "integer"},
                            },
                            "required": ["start", "end", "months"],
                        },
                    },
                },
                "required": ["total_years", "job_count", "gaps"],
            },
            "domain_keywords": {"type": "array", "items": {"type": "string"}},
            "field_confidence": {
                "type": "object",
                "properties": {
                    "skills": {"type": "number"},
                    "projects": {"type": "number"},
                    "tech_used": {"type": "number"},
                    "employment_history": {"type": "number"},
                    "education": {"type": "number"},
                    "certifications": {"type": "number"},
                    "achievements": {"type": "number"},
                    "leadership_indicators": {"type": "number"},
                    "career_timeline": {"type": "number"},
                    "domain_keywords": {"type": "number"},
                },
                "required": [
                    "skills", "projects", "tech_used", "employment_history",
                    "education", "certifications", "achievements",
                    "leadership_indicators", "career_timeline", "domain_keywords",
                ],
            },
        },
        "required": [
            "skills", "projects", "tech_used", "employment_history", "education",
            "certifications", "achievements", "leadership_indicators",
            "career_timeline", "domain_keywords", "field_confidence",
        ],
        "additionalProperties": False,
    },
}
