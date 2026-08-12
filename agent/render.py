"""
Rendering helpers: turn agent data structures (ResearchPlan, Source list,
Draft, VerificationResult, ResearchReport) into the HTML fragments the
Gradio UI displays. Kept separate from app.py so the templates can be
unit-tested without spinning up a Gradio server.
"""
from __future__ import annotations

import html as _html
import re
from typing import Optional

import markdown as _markdown

from agent.models import ClaimStatus, Draft, ResearchPlan, ResearchReport, Source, VerificationResult

_STAGE_NODES = [
    ("planning", "Plan"),
    ("researching", "Search"),
    ("writing", "Draft"),
    ("verifying", "Verify"),
    ("done", "Done"),
]
_STAGE_ORDER = [k for k, _ in _STAGE_NODES]


def render_pipeline_html(stage: str, revisions: int = 0, faithfulness: Optional[float] = None) -> str:
    effective_stage = "writing" if stage == "revising" else stage
    cur_idx = _STAGE_ORDER.index(effective_stage) if effective_stage in _STAGE_ORDER else 0

    rows = []
    if stage == "error":
        rows.append(
            '<div class="rail-step is-error"><span class="rail-label">⚠ Error</span>'
            '<span class="rail-detail">The agent stopped early — see the Report tab.</span></div>'
        )

    for i, (key, label) in enumerate(_STAGE_NODES):
        if stage == "error":
            css_class = "is-complete" if i < cur_idx else ""
        elif i < cur_idx or (key == "done" and stage == "done"):
            css_class = "is-complete"
        elif i == cur_idx:
            css_class = "is-active"
        else:
            css_class = ""

        label_display = f"Draft · revision {revisions}" if (key == "writing" and stage == "revising") else label
        detail = ""
        if key == "verifying" and faithfulness is not None and css_class in ("is-complete", "is-active"):
            detail = f"faithfulness {faithfulness:.0%}"

        detail_html = f'<span class="rail-detail">{detail}</span>' if detail else ""
        rows.append(f'<div class="rail-step {css_class}"><span class="rail-label">{label_display}</span>{detail_html}</div>')

    return f'<div class="margin-rail">{"".join(rows)}</div>'


def render_status_message_html(message: str, stage: str) -> str:
    icon = "⚠" if stage == "error" else "›"
    return f'<div class="control-rail-note"><span class="source-id">{icon}</span> {_html.escape(message)}</div>'


def render_stat_row_html(report: Optional[ResearchReport] = None, sources_count: int = 0,
                          verification: Optional[VerificationResult] = None,
                          elapsed: Optional[float] = None, revisions: int = 0) -> str:
    if report is not None:
        sources_count = len(report.sources)
        verification = report.verification
        elapsed = report.elapsed_seconds
        revisions = report.revisions

    faithfulness = verification.faithfulness_score if verification else None
    accent = "accent-verified" if (faithfulness or 0) >= 0.85 else "accent-partial" if faithfulness is not None else ""
    faith_display = f"{faithfulness:.0%}" if faithfulness is not None else "—"
    elapsed_display = f"{elapsed:.1f}s" if elapsed is not None else "—"

    chips = [
        ("Sources", str(sources_count), ""),
        ("Faithfulness", faith_display, accent),
        ("Revisions", str(revisions), ""),
        ("Elapsed", elapsed_display, ""),
    ]
    chip_html = "".join(
        f'<div class="stat-chip {cls}"><div class="stat-value">{val}</div><div class="stat-label">{label}</div></div>'
        for label, val, cls in chips
    )
    return f'<div class="stat-row">{chip_html}</div>'


_CITATION_RE = re.compile(r"\[(\d{1,2})\]")


def render_report_html(draft: Optional[Draft] = None, report: Optional[ResearchReport] = None) -> str:
    if report is not None:
        body_md = report.markdown_with_footnotes()
    elif draft is not None:
        body_md = draft.markdown
    else:
        return '<div class="report-panel"><div class="empty-state">Run a query to generate a report.</div></div>'

    body_html = _markdown.markdown(body_md, extensions=["extra", "sane_lists", "nl2br"])
    body_html = _CITATION_RE.sub(r'<sup class="cite">[\1]</sup>', body_html)
    return f'<div class="report-panel">{body_html}</div>'


def render_sources_html(sources: list[Source]) -> str:
    if not sources:
        return '<div class="report-panel"><div class="empty-state">Sources will appear here once research begins.</div></div>'
    cards = []
    for s in sources:
        status_cls = "ok" if s.fetched_ok else "fail"
        status_label = "fetched" if s.fetched_ok else "snippet only"
        snippet = _html.escape((s.content or s.snippet or "")[:220]).strip()
        cards.append(
            '<div class="source-card">'
            f'<span class="source-id">[{s.id}]</span><span class="source-domain">{_html.escape(s.domain)}</span>'
            f'<div class="source-title"><a href="{_html.escape(s.url)}" target="_blank" rel="noopener noreferrer">'
            f'{_html.escape(s.title or s.url)}</a></div>'
            f'<div class="source-snippet">{snippet}…</div>'
            f'<span class="fetch-status {status_cls}">{status_label}</span>'
            "</div>"
        )
    return f'<div class="sources-grid">{"".join(cards)}</div>'


def render_verification_html(verification: Optional[VerificationResult]) -> str:
    if verification is None or not verification.claims:
        return '<div class="report-panel"><div class="empty-state">Claim-level verification will appear here after the first draft is checked.</div></div>'
    rows = []
    for c in verification.claims:
        status_value = c.status.value if isinstance(c.status, ClaimStatus) else str(c.status)
        sources_str = ", ".join(f"[{n}]" for n in c.cited_sources) or "none"
        explanation_html = (
            f'<div class="claim-explanation">{_html.escape(c.explanation)}</div>'
            if c.explanation else ""
        )
        rows.append(
            f'<div class="claim-row status-{status_value}">'
            f'<div class="claim-text">{_html.escape(c.claim)}</div>'
            '<div class="claim-meta">'
            f'<span class="status-badge status-{status_value}">{status_value.replace("_", " ")}</span>'
            f'<span class="claim-sources">cites {sources_str}</span>'
            "</div>"
            f'{explanation_html}'
            "</div>"
        )
    notes = (
        f'<div class="control-rail-note" style="margin-top:14px;">{_html.escape(verification.revision_notes)}</div>'
        if verification.revision_notes else ""
    )
    return f'<div class="claims-list">{"".join(rows)}</div>{notes}'


def render_plan_html(plan: Optional[ResearchPlan]) -> str:
    if plan is None:
        return '<div class="report-panel"><div class="empty-state">The research plan will appear here once planning completes.</div></div>'
    cards = []
    for sq in plan.sub_questions:
        chips = "".join(f'<span class="query-chip">{_html.escape(q)}</span>' for q in sq.search_queries)
        cards.append(
            '<div class="subq-card">'
            f'<div class="subq-question">{_html.escape(sq.question)}</div>'
            f'<div class="subq-rationale">{_html.escape(sq.rationale)}</div>'
            f"{chips}"
            "</div>"
        )
    goal_html = f'<div class="plan-goal">{_html.escape(plan.clarified_goal)}</div>' if plan.clarified_goal else ""
    return f"{goal_html}{''.join(cards)}"