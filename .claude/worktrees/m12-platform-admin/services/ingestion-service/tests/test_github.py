from unittest.mock import MagicMock, patch


GITHUB_REPOS = [
    {"name": "api-service", "language": "Python", "stargazers_count": 5,
     "pushed_at": "2026-07-01T00:00:00Z"},
    {"name": "frontend", "language": "TypeScript", "stargazers_count": 2,
     "pushed_at": "2026-06-15T00:00:00Z"},
]


def test_github_enrichment_populated(client, db, seed, mock_agent, mock_embed):
    from tests.conftest import MOCK_AGENT_OUTPUT, MOCK_EMBEDDING
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    cand.github_url = "https://github.com/johndoe"
    db.commit()

    mock_response_user = MagicMock()
    mock_response_user.status_code = 200
    mock_response_user.json.return_value = {"login": "johndoe", "public_repos": 10}

    mock_response_repos = MagicMock()
    mock_response_repos.status_code = 200
    mock_response_repos.json.return_value = GITHUB_REPOS

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience"), \
         patch("src.routers.analyze.httpx.get", side_effect=[mock_response_user, mock_response_repos]):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    enrichment = response.json()["github_enrichment"]
    assert enrichment is not None
    assert "Python" in enrichment["top_languages"]
    assert enrichment["public_repos"] == 10


def test_github_404_returns_null_enrichment(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    cand.github_url = "https://github.com/nobody-xyz"
    db.commit()

    mock_not_found = MagicMock()
    mock_not_found.status_code = 404

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience"), \
         patch("src.routers.analyze.httpx.get", return_value=mock_not_found):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    assert response.json()["github_enrichment"] is None
