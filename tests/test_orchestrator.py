from __future__ import annotations

from agent.orchestrator import ResearchAgent


def test_run_returns_complete_report():
    agent = ResearchAgent(mock=True)
    report = agent.run("What is the outlook for carbon capture technology?",
                        max_sub_questions=3, max_revisions=1)

    assert report.query.startswith("What is the outlook")
    assert len(report.plan.sub_questions) <= 3
    assert len(report.sources) > 0
    assert report.draft.markdown
    assert 0.0 <= report.verification.faithfulness_score <= 1.0
    assert report.elapsed_seconds >= 0


def test_stream_emits_expected_stage_sequence():
    agent = ResearchAgent(mock=True)
    stages = [event.stage for event in agent.stream("Test query", max_sub_questions=3, max_revisions=0)]

    assert stages[0] == "planning"
    assert "researching" in stages
    assert "writing" in stages
    assert "verifying" in stages
    assert stages[-1] in ("done", "error")


def test_run_with_zero_revisions_still_completes():
    agent = ResearchAgent(mock=True)
    report = agent.run("Test query with no revisions allowed", max_sub_questions=3, max_revisions=0)
    assert report.revisions == 0
    assert report.draft.markdown


def test_markdown_with_footnotes_includes_only_cited_sources():
    agent = ResearchAgent(mock=True)
    report = agent.run("Another test query", max_sub_questions=3, max_revisions=0)
    rendered = report.markdown_with_footnotes()

    assert "### Sources" in rendered
    for source_id in report.draft.sources_used:
        assert f"[{source_id}]" in rendered
