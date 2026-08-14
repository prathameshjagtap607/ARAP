SYSTEM_PROMPT = (
    "You are a candidate profile synthesis assistant. "
    "Given structured resume extraction data and a normalized job profile, "
    "produce a comprehensive candidate profile using the provided tool. "
    "Base all claims strictly on the provided data — do not invent information. "
    "Risk flags must be specific and actionable (e.g. cite the company name, "
    "the gap dates, or the exact missing skill). "
    "The summary must cover: current role, career trajectory, standout achievements, "
    "and fit for this specific job. Write 2-3 paragraphs."
)

CANDIDATE_PROFILE_TOOL = {
    "name": "synthesize_candidate_profile",
    "description": "Synthesize a structured candidate profile from resume extraction and job profile data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-3 paragraph narrative: current role, trajectory, standout achievements, domain fit for this job.",
            },
            "skill_matrix_aligned": {
                "type": "array",
                "description": "One entry per required/preferred skill from the job profile.",
                "items": {
                    "type": "object",
                    "properties": {
                        "skill": {"type": "string"},
                        "source": {"type": "string", "enum": ["required", "preferred"]},
                        "alignment": {
                            "type": "string",
                            "enum": ["yes", "partial", "no"],
                            "description": "yes = clearly evidenced, partial = inferred/limited, no = not found",
                        },
                        "estimated_years": {"type": ["number", "null"]},
                        "confidence": {
                            "type": "number",
                            "description": "0.0–1.0 reflecting how clearly the evidence was stated",
                        },
                        "evidence": {
                            "type": ["string", "null"],
                            "description": "Short phrase or quote from resume supporting the alignment",
                        },
                    },
                    "required": ["skill", "source", "alignment", "estimated_years", "confidence", "evidence"],
                },
            },
            "leadership": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["IC", "Team Lead", "Manager", "Director", "VP-equiv"],
                    },
                    "career_velocity": {
                        "type": "string",
                        "description": "e.g. 'Promoted 3 times in 5 years' or 'Lateral moves only'",
                    },
                    "scope": {
                        "type": "object",
                        "properties": {
                            "team_size": {
                                "type": ["integer", "string", "null"],
                                "description": "Largest team size managed. Prefer a plain integer, but a string is accepted if the resume states it non-numerically.",
                            },
                            "budget": {"type": ["string", "null"]},
                            "geography": {"type": ["string", "null"]},
                        },
                        "required": ["team_size", "budget", "geography"],
                    },
                },
                "required": ["level", "career_velocity", "scope"],
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3–5 concise strength statements grounded in resume evidence.",
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1–5 specific flags that seed targeted interview questions (e.g. 'No direct people-management despite Manager title at Acme Corp').",
            },
        },
        "required": ["summary", "skill_matrix_aligned", "leadership", "strengths", "risk_flags"],
    },
}
