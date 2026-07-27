"""
PDF renderer for hiring reports.
Produces a PDF byte stream from report_data using weasyprint + jinja2.
"""
from __future__ import annotations

import io

from jinja2 import Environment, BaseLoader

_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Hiring Report</title>
<style>
  body { font-family: sans-serif; margin: 40px; color: #222; }
  h1 { color: #1a3c5e; }
  .section { margin-top: 24px; }
  .label { font-weight: bold; }
</style>
</head>
<body>
  <h1>Hiring Report</h1>
  <p><span class="label">Candidate:</span> {{ candidate_name }}</p>
  <p><span class="label">Role:</span> {{ job_title }}</p>
  <p><span class="label">Verdict:</span> {{ report_data.get('verdict', 'N/A') }}</p>
  <p><span class="label">AI Confidence:</span> {{ report_data.get('ai_confidence_score', 'N/A') }}</p>
  <div class="section">
    <p class="label">Executive Summary</p>
    <p>{{ report_data.get('executive_summary', '') }}</p>
  </div>
  {% if include_transcript and report_data.get('transcript') %}
  <div class="section">
    <p class="label">Transcript</p>
    <pre>{{ report_data['transcript'] }}</pre>
  </div>
  {% endif %}
</body>
</html>
"""


def render_pdf(
    report_data: dict,
    candidate_name: str,
    job_title: str,
    include_transcript: bool = False,
) -> bytes:
    """Render a PDF from report_data and return raw bytes."""
    from weasyprint import HTML  # deferred import — weasyprint is heavy

    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(_TEMPLATE)
    html_str = tmpl.render(
        report_data=report_data,
        candidate_name=candidate_name,
        job_title=job_title,
        include_transcript=include_transcript,
    )
    buf = io.BytesIO()
    HTML(string=html_str).write_pdf(buf)
    return buf.getvalue()
