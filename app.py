"""
Gradio entry point -- the demo UI.

Run with:
    python app.py

This wires `agent.orchestrator.ResearchAgent.stream()` to four live panels
(Report, Sources, Verification, Plan) plus a "margin rail" pipeline
stepper, so the person watches the agent plan, search, draft, and verify
its own work in real time instead of staring at a single spinner.
"""
from __future__ import annotations

import logging
import os

import gradio as gr

import agent.config as config_module
from agent.config import ROOT_DIR, settings
from agent.orchestrator import ResearchAgent
from agent.render import (
    render_pipeline_html,
    render_plan_html,
    render_report_html,
    render_sources_html,
    render_stat_row_html,
    render_status_message_html,
    render_verification_html,
)
from agent.theme import night_margin_theme

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO),
                     format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")

CSS = (ROOT_DIR / "static" / "theme.css").read_text(encoding="utf-8")

EXAMPLE_QUERIES = [
    "What are the trade-offs between RAG and long-context LLMs for enterprise search?",
    "How is small modular nuclear reactor technology progressing in 2026?",
    "What do recent studies say about GLP-1 drugs and long-term cardiovascular risk?",
    "Compare the current approaches to AI agent memory: vector stores vs. graph memory.",
]

HEADER_HTML = """
<div class="app-header">
  <div>
    <div class="wordmark">Night<span>Margin</span> Research Agent</div>
    <div class="tagline">plan &rarr; search &rarr; draft &rarr; verify &rarr; revise</div>
  </div>
  <div class="badges">
    <span class="pill">{llm_pill}</span>
    <span class="pill">{search_pill}</span>
  </div>
</div>
"""


def _header_html() -> str:
    llm_pill = f"LLM: {settings.writer_model}" if settings.has_llm_key else "LLM: offline mock"
    if settings.has_search_key:
        search_pill = "Search: Tavily"
    elif settings.search_provider == "mock":
        search_pill = "Search: offline mock"
    else:
        search_pill = "Search: DuckDuckGo"
    return HEADER_HTML.format(llm_pill=llm_pill, search_pill=search_pill)


def run_research(query: str, max_sub_questions: int, max_revisions: int,
                  search_provider: str, mock_mode: bool):
    """Generator driving every live panel as the agent works through a query."""
    query = (query or "").strip()
    if not query:
        yield (
            render_pipeline_html("error"),
            render_status_message_html("Enter a research question first.", "error"),
            render_stat_row_html(),
            render_report_html(),
            render_sources_html([]),
            render_verification_html(None),
            render_plan_html(None),
            gr.update(interactive=True),
        )
        return

    # The dropdown overrides the global default search provider for this run only.
    original_provider = config_module.settings.search_provider
    object.__setattr__(config_module.settings, "search_provider", search_provider)

    agent_ = ResearchAgent(mock=mock_mode)
    plan = sources = draft = verification = report = None
    revisions = 0

    try:
        yield (
            render_pipeline_html("planning"),
            render_status_message_html("Starting up…", "planning"),
            render_stat_row_html(),
            render_report_html(),
            render_sources_html([]),
            render_verification_html(None),
            render_plan_html(None),
            gr.update(interactive=False),
        )

        for event in agent_.stream(query, max_sub_questions=int(max_sub_questions), max_revisions=int(max_revisions)):
            plan = event.plan or plan
            sources = event.sources or sources
            draft = event.draft or draft
            verification = event.verification or verification
            report = event.report or report
            if event.stage == "revising":
                revisions += 1

            faithfulness = verification.faithfulness_score if verification else None
            yield (
                render_pipeline_html(event.stage, revisions=revisions, faithfulness=faithfulness),
                render_status_message_html(event.message, event.stage),
                render_stat_row_html(
                    report=report,
                    sources_count=len(sources or []),
                    verification=verification,
                    revisions=revisions,
                ),
                render_report_html(draft=draft, report=report),
                render_sources_html(sources or []),
                render_verification_html(verification),
                render_plan_html(plan),
                gr.update(interactive=(event.stage in ("done", "error"))),
            )
    finally:
        object.__setattr__(config_module.settings, "search_provider", original_provider)


def build_app() -> gr.Blocks:
    with gr.Blocks(title=settings.app_title, fill_width=True, analytics_enabled=False) as demo:
        gr.HTML(_header_html())

        with gr.Row(equal_height=False):
            with gr.Column(scale=4, elem_classes=["control-rail"]):
                gr.Markdown(
                    "Ask a research question. The agent breaks it into sub-questions, "
                    "searches the web, drafts a cited report, then checks every claim "
                    "against its sources before handing it back to you."
                )
                query_box = gr.Textbox(
                    label="Research question",
                    placeholder="e.g. What are the latest advances in solid-state batteries?",
                    lines=3,
                )
                gr.Examples(examples=EXAMPLE_QUERIES, inputs=query_box, label="Try one of these")

                with gr.Accordion("Settings", open=False):
                    sub_q_slider = gr.Slider(3, 6, value=settings.max_sub_questions, step=1,
                                              label="Sub-questions to research")
                    revision_slider = gr.Slider(0, 3, value=settings.max_revisions, step=1,
                                                 label="Max revision passes")
                    provider_dd = gr.Dropdown(
                        choices=["auto", "tavily", "duckduckgo", "mock"],
                        value=settings.search_provider, label="Search provider",
                    )
                    mock_cb = gr.Checkbox(
                        value=not settings.has_llm_key,
                        label="Offline demo mode (mock LLM, no API key needed)",
                    )

                run_btn = gr.Button("Run research", variant="primary")
                status_html = gr.HTML(render_status_message_html("Idle.", "planning"))
                pipeline_html = gr.HTML(render_pipeline_html("planning"))
                gr.Markdown(
                    "<span class='control-rail-note'>Search results and fetched pages are cached on "
                    "disk under <code>cache/</code> so repeat runs don't re-hit paid APIs.</span>"
                )

            with gr.Column(scale=8):
                stat_html = gr.HTML(render_stat_row_html())
                with gr.Tabs():
                    with gr.Tab("Report"):
                        report_html = gr.HTML(render_report_html())
                    with gr.Tab("Sources"):
                        sources_html = gr.HTML(render_sources_html([]))
                    with gr.Tab("Verification"):
                        verification_html = gr.HTML(render_verification_html(None))
                    with gr.Tab("Plan"):
                        plan_html = gr.HTML(render_plan_html(None))

        run_btn.click(
            fn=run_research,
            inputs=[query_box, sub_q_slider, revision_slider, provider_dd, mock_cb],
            outputs=[pipeline_html, status_html, stat_html, report_html, sources_html,
                     verification_html, plan_html, run_btn],
        )
        query_box.submit(
            fn=run_research,
            inputs=[query_box, sub_q_slider, revision_slider, provider_dd, mock_cb],
            outputs=[pipeline_html, status_html, stat_html, report_html, sources_html,
                     verification_html, plan_html, run_btn],
        )

    return demo


demo = build_app()

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4).launch(
        theme=night_margin_theme,
        css=CSS,
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
    )
