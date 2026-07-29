import uuid
from unittest.mock import patch

import pytest
from src.models.candidate_profiles import CandidateProfile


def test_synthesize_profile_writes_all_fields(db, seed, mock_cp_agent):
    from src.modules.candidate_profiles.service import synthesize_profile

    org_id = seed["org"].id
    candidate_id = seed["candidate"].id
    job_id = seed["job"].id

    result = synthesize_profile(db, org_id, candidate_id, job_id)

    assert result.summary == "Jane is a seasoned backend engineer with 8 years of Python expertise."
    assert result.leadership_level_estimate == "Manager"
    assert result.strengths == ["Deep Python expertise", "Cross-functional leadership"]
    assert len(result.risk_flags) == 1
    assert "people-management" in result.risk_flags[0]
    aligned = result.skill_matrix.get("aligned")
    assert aligned is not None
    assert aligned[0]["skill"] == "Python"
    assert aligned[0]["alignment"] == "yes"
    raw = result.skill_matrix.get("raw")
    assert raw is not None
    assert "explicit" in raw
    assert "leadership_scope" in result.experience_matrix
    assert "career_velocity" in result.experience_matrix
    assert result.experience_matrix["career_velocity"] == "Promoted twice in 4 years"


def test_synthesize_profile_raises_lookup_when_no_profile(db, seed):
    from src.modules.candidate_profiles.service import synthesize_profile

    with pytest.raises(LookupError):
        synthesize_profile(db, seed["org"].id, uuid.uuid4(), seed["job"].id)


def test_synthesize_profile_raises_value_error_when_parsing_confidence_null(db, seed):
    from src.modules.candidate_profiles.service import synthesize_profile

    profile = db.query(CandidateProfile).filter_by(
        candidate_id=seed["candidate"].id,
        job_assessment_id=seed["job"].id,
    ).first()
    original = profile.parsing_confidence
    profile.parsing_confidence = None
    db.commit()

    try:
        with pytest.raises(ValueError, match="parsing"):
            synthesize_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)
    finally:
        profile.parsing_confidence = original
        db.commit()


def test_synthesize_profile_raises_runtime_when_agent_returns_none(db, seed):
    from src.modules.candidate_profiles.service import synthesize_profile

    with patch(
        "src.modules.candidate_profiles.service.run_candidate_profile_agent",
        return_value=None,
    ), pytest.raises(RuntimeError, match="agent"):
        synthesize_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)


def test_get_profile_returns_row(db, seed, mock_cp_agent):
    from src.modules.candidate_profiles.service import get_profile, synthesize_profile

    synthesize_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)
    result = get_profile(db, seed["org"].id, seed["candidate"].id, seed["job"].id)
    assert result is not None
    assert str(result.candidate_id) == str(seed["candidate"].id)


def test_get_profile_raises_lookup_when_missing(db, seed):
    from src.modules.candidate_profiles.service import get_profile

    with pytest.raises(LookupError):
        get_profile(db, seed["org"].id, uuid.uuid4(), seed["job"].id)
