from unittest.mock import patch


def test_large_doc_returns_202(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    big_bytes = b"x" * (6 * 1024 * 1024)  # 6 MB > 5 MB threshold
    cand.resume_file_url = "resumes/test/big.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=big_bytes), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience microservices"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })
    assert response.status_code == 202
    assert response.json()["status"] == "processing"
