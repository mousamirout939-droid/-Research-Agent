from __future__ import annotations

from agent.models import (
    ClaimCheck,
    ClaimStatus,
    Draft,
    ResearchPlan,
    ResearchReport,
    Source,
    VerificationResult,
)


def test_source_citation_label():
    source = Source(id=7, url="https://example.com")
    assert source.citation_label() == "[7]"


def test_verification_result_counts():
    result = VerificationResult(claims=[
        ClaimCheck(claim="a", status=ClaimStatus.SUPPORTED),
        ClaimCheck(claim="b", status=ClaimStatus.SUPPORTED),
        ClaimCheck(claim="c", status=ClaimStatus.PARTIALLY_SUPPORTED),
        ClaimCheck(claim="d", status=ClaimStatus.UNSUPPORTED),
    ])
    assert result.total == 4
    assert result.supported == 2
    assert result.faithfulness_score == 0.5


def test_research_report_markdown_with_footnotes_filters_unused_sources():
    plan = ResearchPlan(original_query="q", clarified_goal="g")
    sources = [
        Source(id=1, url="https://a.com", title="A", domain="a.com"),
        Source(id=2, url="https://b.com", title="B", domain="b.com"),
    ]
    draft = Draft(markdown="Body text citing [1] only.", sources_used=[1])
    report = ResearchReport(query="q", plan=plan, sources=sources, draft=draft,
                             verification=VerificationResult(claims=[]))

    rendered = report.markdown_with_footnotes()
    assert "[1]" in rendered
    assert "b.com" not in rendered  # source 2 was never cited, shouldn't appear in footnotes
