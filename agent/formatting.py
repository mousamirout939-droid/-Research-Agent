"""
Small shared helpers for rendering `Source` lists into the text blocks the
writer and verifier prompts expect. Kept separate so both modules format
sources identically -- a citation checker is only as good as its ability
to see exactly what the writer saw.
"""
from __future__ import annotations

from typing import List

from agent.models import Source

PER_SOURCE_CHAR_BUDGET = 1800


def render_sources_block(sources: List[Source], char_budget: int = PER_SOURCE_CHAR_BUDGET) -> str:
    parts = []
    for s in sources:
        body = (s.content or s.snippet or "(no content could be retrieved for this source)")
        body = body[:char_budget]
        parts.append(
            f"[{s.id}] {s.title or s.url}\n"
            f"URL: {s.url}\n"
            f"Domain: {s.domain}\n"
            f"Content: {body}\n"
        )
    return "\n---\n".join(parts)
