import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# xhtml2pdf's default built-in fonts have no glyph for these Unicode dash
# variants (the AI frequently writes "high‑stakes" style hyphenated words
# using U+2011 non-breaking hyphen, or occasionally en/em dashes) — the
# missing glyph renders as a solid black box in the PDF. Normalizing to a
# plain ASCII hyphen before rendering avoids that without touching fonts.
_DASH_REPLACEMENTS = {
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‒": "-",  # figure dash
    "–": "-",  # en dash
    "—": "-",  # em dash
    "−": "-",  # minus sign
}


def _sanitize_text(value):
    if isinstance(value, str):
        for bad, good in _DASH_REPLACEMENTS.items():
            value = value.replace(bad, good)
        return value
    if isinstance(value, dict):
        return {k: _sanitize_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_text(v) for v in value]
    return value


def render_pdf(
    report_data: dict,
    candidate_name: str,
    job_title: str,
    include_transcript: bool = False,
    transcript: list[dict] | None = None,
    qa_pairs: list[dict] | None = None,
    ranking_pairs: list[dict] | None = None,
    reflection_pairs: list[dict] | None = None,
    other_pairs: list[dict] | None = None,
) -> bytes:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("report.html")
    html_content = template.render(
        report=_sanitize_text(report_data),
        candidate_name=_sanitize_text(candidate_name),
        job_title=_sanitize_text(job_title),
        include_transcript=include_transcript,
        transcript=_sanitize_text(transcript or []),
        qa_pairs=_sanitize_text(qa_pairs or []),
        ranking_pairs=_sanitize_text(ranking_pairs or []),
        reflection_pairs=_sanitize_text(reflection_pairs or []),
        other_pairs=_sanitize_text(other_pairs or []),
    )
    buffer = io.BytesIO()
    result = pisa.CreatePDF(html_content, dest=buffer)
    if result.err:
        raise RuntimeError(f"PDF generation failed with {result.err} error(s)")
    return buffer.getvalue()
