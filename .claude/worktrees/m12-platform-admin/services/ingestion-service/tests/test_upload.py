import io
from unittest.mock import patch

import pytest

from tests.conftest import SAMPLE_PDF_BYTES


def _make_docx_bytes() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("John Doe, Python Developer with 5 years of experience building APIs and services.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_pdf_returns_s3_key(client):
    with patch("src.routers.upload.upload_file", return_value="resumes/test/abc.pdf"), \
         patch("src.routers.upload.ensure_bucket"):
        response = client.post(
            "/upload",
            files={"file": ("resume.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "s3_key" in data
    assert data["s3_key"].endswith(".pdf")


def test_upload_docx_accepted(client):
    with patch("src.routers.upload.upload_file", return_value="resumes/test/abc.docx"), \
         patch("src.routers.upload.ensure_bucket"):
        response = client.post(
            "/upload",
            files={"file": ("resume.docx", _make_docx_bytes(),
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert response.status_code == 200


def test_upload_plain_text_accepted(client):
    text = b"John Doe\nPython Developer 5 years experience FastAPI PostgreSQL Docker Kubernetes"
    with patch("src.routers.upload.upload_file", return_value="resumes/test/abc.txt"), \
         patch("src.routers.upload.ensure_bucket"):
        response = client.post(
            "/upload",
            files={"file": ("resume.txt", text, "text/plain")},
        )
    assert response.status_code == 200


def test_upload_unsupported_type_returns_422(client):
    response = client.post(
        "/upload",
        files={"file": ("photo.png", b"PNG data", "image/png")},
    )
    assert response.status_code == 422


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
