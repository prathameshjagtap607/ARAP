from unittest.mock import patch

from agents.resume_analysis.agent import run_resume_analysis_agent

RAW_TEXT = (
    "John Doe, Python Developer\n"
    "5 years experience at TechCorp (2020-2025). Team size: 5.\n"
    "Skills: Python, FastAPI, PostgreSQL.\n"
    "Education: B.Tech CS, MIT 2019.\n"
    "Achievements: Reduced API latency 40%."
)

JOB_PROFILE = {"required_skills": ["Python"], "preferred_skills": ["Docker"]}

MOCK_TOOL_OUTPUT = {
    "skills": {"explicit": ["Python", "FastAPI"], "inferred": ["REST APIs"]},
    "projects": [],
    "tech_used": ["PostgreSQL"],
    "employment_history": [
        {"company": "TechCorp", "title": "Developer", "start": "2020-01",
         "end": "2025-01", "team_size": 5, "scope": "regional", "key_achievements": []}
    ],
    "education": [{"degree": "B.Tech", "field": "CS", "institution": "MIT", "year": 2019}],
    "certifications": [],
    "achievements": ["Reduced API latency 40%"],
    "leadership_indicators": {"max_team_size": 5, "scope": "regional", "budget_ownership": None},
    "career_timeline": {"total_years": 5.0, "job_count": 1, "gaps": []},
    "domain_keywords": ["backend"],
    "field_confidence": {
        "skills": 0.92, "projects": 0.85, "tech_used": 0.90,
        "employment_history": 0.95, "education": 0.97, "certifications": 0.80,
        "achievements": 0.75, "leadership_indicators": 0.70,
        "career_timeline": 0.88, "domain_keywords": 0.83,
    },
}

EXPECTED_FIELDS = {
    "skills", "projects", "tech_used", "employment_history", "education",
    "certifications", "achievements", "leadership_indicators", "career_timeline",
    "domain_keywords", "field_confidence", "_leadership_level",
}


def test_agent_returns_extraction_shape():
    with patch("agents.resume_analysis.agent.call_tool", return_value=dict(MOCK_TOOL_OUTPUT)):
        result = run_resume_analysis_agent(RAW_TEXT, JOB_PROFILE)
    assert result is not None
    assert EXPECTED_FIELDS == set(result.keys())
    assert set(result["field_confidence"].keys()) == {
        "skills", "projects", "tech_used", "employment_history", "education",
        "certifications", "achievements", "leadership_indicators", "career_timeline", "domain_keywords",
    }


def test_agent_field_confidence_values_in_range():
    with patch("agents.resume_analysis.agent.call_tool", return_value=dict(MOCK_TOOL_OUTPUT)):
        result = run_resume_analysis_agent(RAW_TEXT, JOB_PROFILE)
    for field, score in result["field_confidence"].items():
        assert 0.0 <= score <= 1.0, f"{field} confidence out of range: {score}"


def test_agent_returns_none_on_api_error():
    with patch("agents.resume_analysis.agent.call_tool", side_effect=Exception("API down")):
        result = run_resume_analysis_agent(RAW_TEXT, JOB_PROFILE)
    assert result is None


def test_agent_accepts_none_job_profile():
    with patch("agents.resume_analysis.agent.call_tool", return_value=dict(MOCK_TOOL_OUTPUT)):
        result = run_resume_analysis_agent(RAW_TEXT, None)
    assert result is not None


def test_derive_leadership_level_boundaries():
    from agents.resume_analysis.agent import _derive_leadership_level
    assert _derive_leadership_level(None) == "IC"
    assert _derive_leadership_level(0) == "IC"
    assert _derive_leadership_level(1) == "Team Lead"
    assert _derive_leadership_level(4) == "Team Lead"
    assert _derive_leadership_level(5) == "Manager"
    assert _derive_leadership_level(15) == "Manager"
    assert _derive_leadership_level(16) == "Director"
    assert _derive_leadership_level(50) == "Director"
    assert _derive_leadership_level(51) == "VP-equiv"
