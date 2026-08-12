"""
Writer: synthesizes a `ResearchPlan` + a list of `Source` objects into a
cited markdown `Draft`. Also handles revision: given verifier feedback and
the previous draft, it produces a corrected draft.
"""
from __future__ import annotations

import logging
import re

from agent.config import PROMPTS_DIR, settings
from agent.formatting import render_sources_block
from agent.llm import BaseLLM
from agent.models import Draft, ResearchPlan, Source, VerificationResult

logger = logging.getLogger(__name__)


class Writer:
    def __init__(self, llm: BaseLLM, model: str | None = None):
        self.llm = llm
        self.model = model or settings.writer_model
        self.system_prompt = (PROMPTS_DIR / "writer_prompt.txt").read_text(encoding="utf-8")

    def write(self, plan: ResearchPlan, sources: list[Source]) -> Draft:
        sub_questions_block = "\n".join(f"- {sq.question}" for sq in plan.sub_questions)
        user = (
            f"Research goal: {plan.clarified_goal}\n\n"
            f"Sub-questions investigated:\n{sub_questions_block}\n\n"
            f"SOURCES:\n{render_sources_block(sources)}\n\n"
            f"Write the report now."
        )
        markdown = self.llm.complete(self.system_prompt, user, model=self.model, max_tokens=3000, temperature=0.3)
        return Draft(markdown=markdown.strip(), sources_used=_extract_cited_ids(markdown))

    def revise(self, plan: ResearchPlan, sources: list[Source], previous: Draft,
               verification: VerificationResult) -> Draft:
        flagged = [c for c in verification.claims if c.status.value in ("unsupported", "uncited", "partially_supported")]
        flagged_block = "\n".join(
            f'- "{c.claim}" (cited {c.cited_sources or "none"}): {c.status.value} -- {c.explanation}'
            for c in flagged
        ) or "(none flagged, but tighten citations generally)"

        sub_questions_block = "\n".join(f"- {sq.question}" for sq in plan.sub_questions)
        user = (
            f"Research goal: {plan.clarified_goal}\n\n"
            f"Sub-questions investigated:\n{sub_questions_block}\n\n"
            f"SOURCES:\n{render_sources_block(sources)}\n\n"
            f"PREVIOUS DRAFT:\n{previous.markdown}\n\n"
            f"VERIFIER FEEDBACK -- claims that must be fixed:\n{flagged_block}\n\n"
            f"Verifier's overall guidance: {verification.revision_notes or 'N/A'}\n\n"
            f"Revise the report now, addressing every flagged claim."
        )
        markdown = self.llm.complete(self.system_prompt, user, model=self.model, max_tokens=3000, temperature=0.3)
        return Draft(
            markdown=markdown.strip(),
            sources_used=_extract_cited_ids(markdown),
            revision=previous.revision + 1,
        )


def _extract_cited_ids(markdown: str) -> list[int]:
    ids = {int(n) for n in re.findall(r"\[(\d+)\]", markdown)}
    return sorted(ids)
