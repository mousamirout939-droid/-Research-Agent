from __future__ import annotations

from agent.models import ClaimCheck, ClaimStatus, Draft, ResearchPlan, Source, SubQuestion, VerificationResult
from agent.render import (
    render_pipeline_html,
    render_plan_html,
    render_report_html,
    render_sources_html,
    render_stat_row_html,
    render_verification_html,
)


def test_render_pipeline_html_marks_current_stage_active():
    html = render_pipeline_html("researching")
    assert 'is-active">' in html or "is-active" in html
    assert "Search" in html


def test_render_pipeline_html_error_state():
    html = render_pipeline_html("error")
    assert "is-error" in html
    assert "Error" in html


def test_render_report_html_escapes_nothing_breaks_on_empty_state():
    html = render_report_html()
    assert "report-panel" in html
    assert "empty-state" in html


def test_render_report_html_wraps_citation_markers():
    draft = Draft(markdown="A claim with a citation [1].", sources_used=[1])
    html = render_report_html(draft=draft)
    assert '<sup class="cite">[1]</sup>' in html


def test_render_sources_html_escapes_html_in_titles():
    sources = [Source(id=1, url="https://x.com", title="<script>alert(1)</script>", domain="x.com",
                       content="some content", fetched_ok=True)]
    html = render_sources_html(sources)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_verification_html_renders_each_claim():
    verification = VerificationResult(claims=[
        ClaimCheck(claim="Claim one", status=ClaimStatus.SUPPORTED, cited_sources=[1]),
        ClaimCheck(claim="Claim two", status=ClaimStatus.UNSUPPORTED, cited_sources=[2]),
    ])
    html = render_verification_html(verification)
    assert "Claim one" in html
    assert "Claim two" in html
    assert "status-supported" in html
    assert "status-unsupported" in html


def test_render_plan_html_includes_search_queries():
    plan = ResearchPlan(
        original_query="q", clarified_goal="Clarified goal here.",
        sub_questions=[SubQuestion(question="A question?", search_queries=["query a", "query b"])],
    )
    html = render_plan_html(plan)
    assert "Clarified goal here." in html
    assert "query a" in html
    assert "query b" in html


def test_render_stat_row_html_handles_no_data():
    html = render_stat_row_html()
    assert "stat-row" in html
