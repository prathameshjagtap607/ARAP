"""
Tests for agents.report_generator.pdf.render_pdf.

WeasyPrint requires native GTK/Pango libraries that are not available in all
CI/dev environments (notably Windows without GTK). We therefore inject a
sys.modules stub for 'weasyprint' before the production module is imported so
that the import itself does not fail, and each test controls the return value
via unittest.mock.patch.
"""
import sys
import types
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# sys.modules stub for weasyprint — must happen before any import of pdf.py
# ---------------------------------------------------------------------------
_weasyprint_stub = types.ModuleType("weasyprint")
_mock_html_cls = MagicMock()
_weasyprint_stub.HTML = _mock_html_cls
sys.modules.setdefault("weasyprint", _weasyprint_stub)

# Now safe to import the production module
from agents.report_generator.pdf import render_pdf  # noqa: E402

# ---------------------------------------------------------------------------
# Shared test fixture
# ---------------------------------------------------------------------------
_SAMPLE_REPORT = {
    "meta": {"generated_at": "2026-07-27T00:00:00+00:00", "requires_human_review": False, "confidence_rationale": ""},
    "executive_summary": "Strong hire.",
    "candidate_overview": "Experienced engineer.",
    "resume_summary": "5 years Python.",
    "interview_summary": "Performed well.",
    "scores": {"technical": {"score": 3.8, "vs_job_bar": "+0.3", "vs_org_bar": "-0.1"}},
    "overall_rating": 3.8,
    "culture_fit": "Good fit.",
    "domain_knowledge": "Deep expertise.",
    "skill_gap_analysis": "Leadership gap.",
    "strengths": ['Strong problem-solving (cited from Q3: "I designed it")'],
    "weaknesses": ['Thin leadership (cited from Q5: "I worked alone")'],
    "potential_risks": "Limited management experience.",
    "learning_curve_estimate": "2-3 months.",
    "management_readiness": "Not ready yet.",
    "promotion_potential": "Strong IC trajectory.",
    "salary_recommendation": {"band": "L4 / Senior", "rationale": "Senior scores."},
    "ai_confidence_score": 72.0,
    "recommended_next_round": "Technical Panel",
    "training_needs": [{"area": "Leadership", "priority": "medium", "rationale": "Low score."}],
    "suggested_hr_questions": ["Q1?", "Q2?", "Q3?"],
    "suggested_ceo_questions": ["CQ1?", "CQ2?", "CQ3?"],
    "integrity_summary": {"overall_risk": "low", "flagged_count": 0},
    "integrity_summary_prose": "No integrity concerns identified.",
    "final_verdict": "Hire — Strong technical profile supports a hire recommendation.",
}

_FAKE_PDF = b"%PDF-1.4 fake pdf content for testing" + b"x" * 1000


# ---------------------------------------------------------------------------
# Case 1: render_pdf returns bytes starting with PDF magic bytes
# ---------------------------------------------------------------------------
def test_render_pdf_returns_pdf_bytes():
    mock_inst = MagicMock()
    mock_inst.write_pdf.return_value = _FAKE_PDF

    with patch("agents.report_generator.pdf.HTML", return_value=mock_inst):
        result = render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer")

    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Case 2: transcript section absent when include_transcript=False
# ---------------------------------------------------------------------------
def test_render_pdf_no_transcript_by_default():
    mock_inst = MagicMock()
    mock_inst.write_pdf.return_value = _FAKE_PDF

    with patch("agents.report_generator.pdf.HTML", return_value=mock_inst) as mock_html_cls:
        result = render_pdf(
            _SAMPLE_REPORT,
            candidate_name="Alice",
            job_title="Senior Engineer",
            include_transcript=False,
        )

        # Inspect the HTML string passed to the HTML() constructor
        call_args = mock_html_cls.call_args
        html_string = call_args.kwargs.get("string", "") or (call_args.args[0] if call_args.args else "")
        # The Jinja2 {% if include_transcript %} block should NOT render
        assert "transcript-section" not in html_string

    # PDF bytes should still be non-trivially sized
    assert len(result) > 1000
