from __future__ import annotations

from agent.models import ClaimCheck, ClaimStatus, Draft, ResearchPlan, SubQuestion, VerificationResult
from agent.writer import Writer, _extract_cited_ids


def _plan() -> ResearchPlan:
    return ResearchPlan(
        original_query="What is the state of solid-state batteries?",
        clarified_goal="Summarize current progress on solid-state battery technology.",
        sub_questions=[
            SubQuestion(question="What is the current state of the technology?", search_queries=["solid state batteries 2026"]),
            SubQuestion(question="What are the main risks?", search_queries=["solid state battery risks"]),
        ],
    )


def test_write_produces_draft_with_citations(mock_llm, sample_sources):
    writer = Writer(mock_llm)
    draft = writer.write(_plan(), sample_sources)

    assert isinstance(draft, Draft)
    assert draft.markdown
    assert draft.revision == 0
    assert len(draft.sources_used) > 0


def test_extract_cited_ids_handles_multiple_brackets():
    text = "Some claim [1][2]. Another claim [3]. Repeated [1]."
    assert _extract_cited_ids(text) == [1, 2, 3]


def test_extract_cited_ids_empty_when_no_citations():
    assert _extract_cited_ids("No citations here at all.") == []


def test_revise_increments_revision_counter(mock_llm, sample_sources):
    writer = Writer(mock_llm)
    previous = Draft(markdown="Old draft with a claim [1].", sources_used=[1], revision=0)
    verification = VerificationResult(claims=[
        ClaimCheck(claim="Old draft with a claim", cited_sources=[1], status=ClaimStatus.UNSUPPORTED, explanation="not in source"),
    ], revision_notes="Remove or qualify the unsupported claim.")

    revised = writer.revise(_plan(), sample_sources, previous, verification)
    assert revised.revision == 1
