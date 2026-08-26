"""
Tests for agents.report_generator.pdf.render_pdf.

xhtml2pdf is pure Python (no native GTK/Pango dependency like WeasyPrint),
so these run a real render rather than mocking the PDF engine.
"""
from unittest.mock import MagicMock, patch

from agents.report_generator.pdf import render_pdf

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


# ---------------------------------------------------------------------------
# Case 1: render_pdf returns real PDF bytes
# ---------------------------------------------------------------------------
def test_render_pdf_returns_pdf_bytes():
    result = render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer")

    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"
    assert len(result) > 1000


# ---------------------------------------------------------------------------
# Case 2: transcript section absent when include_transcript=False
# ---------------------------------------------------------------------------
def test_render_pdf_no_transcript_by_default():
    mock_result = MagicMock()
    mock_result.err = 0

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result) as mock_create:
        render_pdf(
            _SAMPLE_REPORT,
            candidate_name="Alice",
            job_title="Senior Engineer",
            include_transcript=False,
        )

        html_string = mock_create.call_args.args[0]
        # The Jinja2 {% if include_transcript %} block should NOT render
        assert "transcript-section" not in html_string
        assert "Raw Transcript" not in html_string


# ---------------------------------------------------------------------------
# Case 3: transcript section present when include_transcript=True
# ---------------------------------------------------------------------------
def test_render_pdf_includes_transcript_when_requested():
    result = render_pdf(
        _SAMPLE_REPORT,
        candidate_name="Alice",
        job_title="Senior Engineer",
        include_transcript=True,
        transcript=[{"sequence_no": 1, "question": "Describe your approach.", "answer": "I planned first."}],
    )

    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Case 5: DISC-Based Generative Leadership Question Framework — Developmental
# Insights and Natural-vs-Adaptive sections render when present, and the old
# judgmental sections (removed from the web results page) no longer render.
# ---------------------------------------------------------------------------
def test_render_pdf_includes_developmental_insights_and_qa_pairs():
    mock_result = MagicMock()
    mock_result.err = 0

    report_with_insights = {
        **_SAMPLE_REPORT,
        "developmental_insights": {
            "natural_leadership_tendencies": "Tends to plan carefully.",
            "behavioural_strengths": ["Strong at building consensus"],
            "potential_blind_spots": ["May move slowly under time pressure"],
            "behaviour_under_pressure": "Stays methodical.",
            "communication_preferences": "Prefers written detail.",
            "conflict_tendencies": "Seeks common ground.",
            "decision_making_tendencies": "Data-driven and deliberate.",
            "adaptability_assessment": "Can adapt when explicitly prompted.",
            "areas_for_behavioural_development": ["Practice faster decision-making"],
        },
    }
    qa_pairs = [{
        "question_text": "A team member disagrees with your decision. What do you do?",
        "natural": "Seek more data before responding.",
        "adaptive": "Address it directly in the moment.",
    }]

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result) as mock_create:
        render_pdf(
            report_with_insights,
            candidate_name="Alice",
            job_title="Senior Engineer",
            qa_pairs=qa_pairs,
        )

    html_string = mock_create.call_args.args[0]
    assert "Developmental Insights" in html_string
    assert "Strong at building consensus" in html_string
    assert "Natural vs. Adaptive Response" in html_string
    assert "Address it directly in the moment." in html_string
    # old judgmental sections must no longer render
    assert "Weaknesses</h2>" not in html_string
    assert "Potential Risks</h2>" not in html_string
    assert "Salary Recommendation</h2>" not in html_string
    assert "Final Verdict</h2>" not in html_string
    assert "Recommended Next Round</h2>" not in html_string
    assert "Training Needs</h2>" not in html_string


def test_render_pdf_includes_other_responses_for_unpaired_formats():
    """Situational Response, First Action, standalone Behavioural Choice, and
    Self-Awareness formats have no adaptive pair, ranking, or reflection text
    — they were previously silently dropped from the PDF entirely. This
    fills that gap without touching the existing 3 sections above."""
    mock_result = MagicMock()
    mock_result.err = 0

    other_pairs = [{
        "question_text": "What would you do first?",
        "answer": "I would gather the affected team leads.",
    }]

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result) as mock_create:
        render_pdf(
            _SAMPLE_REPORT,
            candidate_name="Alice",
            job_title="Senior Engineer",
            other_pairs=other_pairs,
        )

    html_string = mock_create.call_args.args[0]
    assert "Other Responses" in html_string
    assert "I would gather the affected team leads." in html_string


def test_render_pdf_no_other_responses_section_when_absent():
    mock_result = MagicMock()
    mock_result.err = 0

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result) as mock_create:
        render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer")

    html_string = mock_create.call_args.args[0]
    assert "Other Responses" not in html_string


def test_render_pdf_no_developmental_insights_section_when_absent():
    mock_result = MagicMock()
    mock_result.err = 0

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result) as mock_create:
        render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer")

    html_string = mock_create.call_args.args[0]
    assert "Developmental Insights" not in html_string
    assert "Natural vs. Adaptive Response" not in html_string


# ---------------------------------------------------------------------------
# Case 4: pisa reporting an error raises instead of returning bad bytes
# ---------------------------------------------------------------------------
def test_render_pdf_replaces_unicode_dashes_that_xhtml2pdf_cannot_render():
    """xhtml2pdf's default fonts have no glyph for non-breaking hyphens / en
    dashes / em dashes — the AI frequently writes hyphenated words like
    "high‑stakes" using these, which renders as a solid black box in the
    PDF instead of a hyphen. render_pdf must normalize them to plain ASCII
    hyphens before handing the HTML to pisa."""
    mock_result = MagicMock()
    mock_result.err = 0

    report_with_unicode_dashes = {
        **_SAMPLE_REPORT,
        "executive_summary": "Thrives in high‑stakes, cross–functional settings.",
        "strengths": ["Strong step‑by‑step execution—even under pressure."],
    }

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result) as mock_create:
        render_pdf(
            report_with_unicode_dashes,
            candidate_name="Ali‑ce",
            job_title="Senior Engineer",
        )

    html_string = mock_create.call_args.args[0]
    assert "‑" not in html_string
    assert "–" not in html_string
    assert "—" not in html_string
    assert "high-stakes, cross-functional" in html_string
    assert "step-by-step execution-even" in html_string
    assert "Ali-ce" in html_string


def test_render_pdf_raises_on_pisa_error():
    mock_result = MagicMock()
    mock_result.err = 1

    with patch("agents.report_generator.pdf.pisa.CreatePDF", return_value=mock_result):
        try:
            render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer")
            raise AssertionError("expected RuntimeError")
        except RuntimeError:
            pass
