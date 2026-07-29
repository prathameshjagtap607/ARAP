import io
import pytest

from src.parsers import extract_text, SUPPORTED_MIME_TYPES


def _make_docx_bytes() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("John Doe, Python Developer with 5 years of experience building APIs and services.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_plain_text():
    text = "John Doe\nPython Developer with 5 years of experience in FastAPI and PostgreSQL systems."
    result = extract_text(text.encode(), "text/plain")
    assert "Python" in result
    assert len(result.strip()) >= 50


def test_extract_plain_text_utf8_errors():
    raw = b"Python Developer \xff with experience in cloud systems and microservices architecture."
    result = extract_text(raw, "text/plain")
    assert "Python" in result


def test_extract_docx():
    result = extract_text(_make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert "Python" in result
    assert len(result.strip()) >= 50


def test_extract_too_short_raises():
    with pytest.raises(ValueError, match="resume too short"):
        extract_text(b"Hi", "text/plain")


def test_unsupported_mime_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(b"data", "image/png")


def test_supported_mime_types_constant():
    assert "application/pdf" in SUPPORTED_MIME_TYPES
    assert "text/plain" in SUPPORTED_MIME_TYPES
