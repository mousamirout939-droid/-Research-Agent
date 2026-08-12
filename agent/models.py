"""
Typed data structures shared across the research agent pipeline.

Keeping these in one place means the planner, researcher, writer and
verifier are all speaking the same language, and it gives us free
validation + JSON (de)serialization via Pydantic.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
class SubQuestion(BaseModel):
    """A single, narrowly-scoped research question produced by the planner."""

    id: str = Field(default_factory=_new_id)
    question: str
    search_queries: List[str] = Field(default_factory=list)
    rationale: str = ""


class ResearchPlan(BaseModel):
    original_query: str
    clarified_goal: str = ""
    sub_questions: List[SubQuestion] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --------------------------------------------------------------------------- #
# Evidence gathering
# --------------------------------------------------------------------------- #
class Source(BaseModel):
    """A single piece of retrieved evidence (a web page / search snippet)."""

    id: int
    url: str
    title: str = ""
    snippet: str = ""
    content: str = ""          # cleaned, extracted full-page text (truncated)
    sub_question_id: Optional[str] = None
    fetched_ok: bool = False
    domain: str = ""
    published_date: Optional[str] = None

    def citation_label(self) -> str:
        return f"[{self.id}]"


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
class Draft(BaseModel):
    markdown: str
    sources_used: List[int] = Field(default_factory=list)
    revision: int = 0


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    UNCITED = "uncited"


class ClaimCheck(BaseModel):
    claim: str
    cited_sources: List[int] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.UNCITED
    explanation: str = ""


class VerificationResult(BaseModel):
    claims: List[ClaimCheck] = Field(default_factory=list)
    revision_notes: str = ""

    @property
    def total(self) -> int:
        return len(self.claims)

    @property
    def supported(self) -> int:
        return sum(1 for c in self.claims if c.status == ClaimStatus.SUPPORTED)

    @property
    def faithfulness_score(self) -> float:
        """Fraction of claims that are fully supported by a cited source."""
        if not self.claims:
            return 1.0
        return round(self.supported / self.total, 4)

    @property
    def needs_revision(self) -> bool:
        return any(
            c.status in (ClaimStatus.UNSUPPORTED, ClaimStatus.UNCITED)
            for c in self.claims
        )


# --------------------------------------------------------------------------- #
# Final report returned to the caller / UI
# --------------------------------------------------------------------------- #
class ResearchReport(BaseModel):
    query: str
    plan: ResearchPlan
    sources: List[Source]
    draft: Draft
    verification: VerificationResult
    revisions: int = 0
    elapsed_seconds: float = 0.0

    def markdown_with_footnotes(self) -> str:
        """Final markdown body + a rendered source list."""
        lines = [self.draft.markdown, "\n\n---\n\n### Sources\n"]
        for s in self.sources:
            if s.id in self.draft.sources_used:
                title = s.title or s.url
                lines.append(f"{s.citation_label()} [{title}]({s.url}) — *{s.domain}*")
        return "\n".join(lines)
