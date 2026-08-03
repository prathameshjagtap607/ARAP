from unittest.mock import patch

_FAKE_RESULT = {
    "summary": "Jane is a senior backend engineer with 8 years of Python experience.",
    "skill_matrix_aligned": [
        {
            "skill": "Python",
            "source": "required",
            "alignment": "yes",
            "estimated_years": 8.0,
            "confidence": 0.95,
            "evidence": "8 years Python development across 3 companies",
        }
    ],
    "leadership": {
        "level": "Manager",
        "career_velocity": "Promoted twice in 4 years",
        "scope": {"team_size": 8, "budget": None, "geography": "Remote — APAC"},
    },
    "strengths": ["Deep Python expertise", "Cross-functional leadership"],
    "risk_flags": ["No direct people-management despite Manager title at Acme Corp"],
}


_EXTRACTION = {
    "skill_matrix": {
        "explicit": ["Python", "FastAPI"],
        "inferred": ["REST APIs"],
        "tech_used": ["PostgreSQL"],
    },
    "experience_matrix": {
        "employment_history": [
            {
                "company": "Acme Corp",
                "title": "Engineering Manager",
                "start": "2020-01",
                "end": None,
                "team_size": 8,
                "scope": "Backend platform",
                "key_achievements": ["Reduced latency by 40%"],
            }
        ],
        "career_timeline": {"total_years": 8, "job_count": 3, "gaps": []},
    },
    "leadership_level_estimate": "Manager",
    "field_confidence": {"skills": 0.9, "employment_history": 0.85},
}

_JOB_PROFILE = {
    "normalized_title": "Senior Backend Engineer",
    "role_summary": "Build scalable APIs.",
    "key_responsibilities": ["Design REST APIs", "Mentor junior engineers"],
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": ["Docker"],
    "difficulty_level": "senior",
}


def test_agent_returns_structured_output():
    from agents.candidate_profile.agent import run_candidate_profile_agent

    with patch("agents.candidate_profile.agent.call_tool", return_value=_FAKE_RESULT):
        result = run_candidate_profile_agent(_EXTRACTION, _JOB_PROFILE)

    assert result is not None
    assert "summary" in result
    assert "skill_matrix_aligned" in result
    assert isinstance(result["skill_matrix_aligned"], list)
    assert result["skill_matrix_aligned"][0]["skill"] == "Python"
    assert result["skill_matrix_aligned"][0]["alignment"] == "yes"
    assert "leadership" in result
    assert result["leadership"]["level"] == "Manager"
    assert "strengths" in result
    assert "risk_flags" in result
    assert isinstance(result["risk_flags"], list)


def test_agent_returns_none_on_api_error():
    from agents.candidate_profile.agent import run_candidate_profile_agent

    with patch("agents.candidate_profile.agent.call_tool", side_effect=Exception("API down")):
        result = run_candidate_profile_agent(_EXTRACTION, _JOB_PROFILE)

    assert result is None
