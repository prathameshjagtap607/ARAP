import io

from pypdf import PdfReader

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
_MIN_CHARS = 50


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}")

    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = file_bytes.decode("utf-8", errors="replace")

    if len(text.strip()) < _MIN_CHARS:
        raise ValueError("resume too short to parse")
    return text
