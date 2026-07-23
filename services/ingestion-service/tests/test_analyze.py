import uuid
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import MOCK_AGENT_OUTPUT, MOCK_EMBEDDING


def _set_candidate_s3_key(db, candidate, key):
    candidate.resume_file_url = key
    db.commit()
    db.refresh(candidate)


def test_analyze_writes_candidate_profile(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=b"John Doe Python Developer with 5 years experience at TechCorp building scalable microservices"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer with 5 years experience at TechCorp building scalable microservices"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    data = response.json()
    assert data["field_confidence"] is not None
    assert len(data["field_confidence"]) == 10
    assert 0.0 <= data["match_score"] <= 1.0
    assert data["parsing_confidence"] is not None


def test_analyze_field_confidence_all_10_keys(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer with 5+ years experience"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    expected_keys = {
        "skills", "projects", "tech_used", "employment_history", "education",
        "certifications", "achievements", "leadership_indicators", "career_timeline", "domain_keywords",
    }
    assert set(response.json()["field_confidence"].keys()) == expected_keys


def test_analyze_agent_error_returns_null_confidence(client, db, seed, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    db.commit()

    with patch("src.routers.analyze.run_resume_analysis_agent", return_value=None), \
         patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer experience"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    assert response.json()["parsing_confidence"] is None
    assert response.json()["field_confidence"] is None


def test_analyze_404_unknown_candidate(client, seed, mock_agent, mock_embed):
    response = client.post("/analyze", json={
        "candidate_id": str(uuid.uuid4()),
        "job_assessment_id": str(seed["job"].id),
        "org_id": str(seed["org"].id),
    })
    assert response.status_code == 404


def test_analyze_no_resume_url(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    cand.resume_file_url = None
    db.commit()

    response = client.post("/analyze", json={
        "candidate_id": str(cand.id),
        "job_assessment_id": str(seed["job"].id),
        "org_id": str(seed["org"].id),
    })
    assert response.status_code == 422
    assert "resume" in response.json()["detail"].lower()


def test_get_analyze_returns_profile(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/r2.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience"):
        client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    response = client.get(f"/analyze/{cand.id}/{job.id}")
    assert response.status_code == 200
    assert response.json()["candidate_id"] == str(cand.id)


def test_get_analyze_404_not_yet_written(client, seed):
    response = client.get(f"/analyze/{uuid.uuid4()}/{uuid.uuid4()}")
    assert response.status_code == 404
