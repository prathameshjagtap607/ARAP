import io
import re

from pypdf import PdfReader

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
_MIN_CHARS = 50


def _looks_letter_spaced(text: str) -> bool:
    """Detect the pypdf artifact where some PDFs extract as 'D E C L A R E D'
    (every glyph its own token) instead of real words — common with certain
    embedded fonts. Word boundaries in that artifact are 2+ spaces; letters
    within a word are single-spaced.
    """
    tokens = text.split(" ")
    if len(tokens) < 20:
        return False
    single_char_ratio = sum(1 for t in tokens if len(t) == 1) / len(tokens)
    return single_char_ratio > 0.6


def _fix_letter_spacing(text: str) -> str:
    if not _looks_letter_spaced(text):
        return text
    text = re.sub(r" {2,}", "\x00", text)
    text = text.replace(" ", "")
    return text.replace("\x00", " ")


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}")

    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(_fix_letter_spacing(page.extract_text() or "") for page in reader.pages)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = file_bytes.decode("utf-8", errors="replace")

    if len(text.strip()) < _MIN_CHARS:
        raise ValueError("resume too short to parse")
    return text
