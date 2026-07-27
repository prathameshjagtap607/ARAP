from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_pdf(
    report_data: dict,
    candidate_name: str,
    job_title: str,
    include_transcript: bool = False,
    transcript: list[dict] | None = None,
) -> bytes:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("report.html")
    html_content = template.render(
        report=report_data,
        candidate_name=candidate_name,
        job_title=job_title,
        include_transcript=include_transcript,
        transcript=transcript or [],
    )
    return HTML(string=html_content).write_pdf()
