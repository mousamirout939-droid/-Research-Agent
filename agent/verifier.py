"""
Verifier: the faithfulness / citation-accuracy check.

Given a draft and the sources it cites, this asks the LLM to fact-check
every claim against the *provided source text only*, producing a
`VerificationResult` the orchestrator uses to decide whether another
writer revision pass is needed, and that the UI renders as a per-claim
faithfulness panel.
"""
from __future__ import annotations

import logging

from agent.config import PROMPTS_DIR, settings
from agent.formatting import render_sources_block
from agent.llm import BaseLLM
from agent.models import ClaimCheck, ClaimStatus, Draft, Source, VerificationResult

logger = logging.getLogger(__name__)

_VALID_STATUSES = {s.value for s in ClaimStatus}


class Verifier:
    def __init__(self, llm: BaseLLM, model: str | None = None):
        self.llm = llm
        self.model = model or settings.verifier_model
        self.system_prompt = (PROMPTS_DIR / "verifier_prompt.txt").read_text(encoding="utf-8")

    def verify(self, draft: Draft, sources: list[Source]) -> VerificationResult:
        cited_sources = [s for s in sources if s.id in draft.sources_used] or sources
        user = (
            f"DRAFT REPORT:\n{draft.markdown}\n\n"
            f"SOURCES:\n{render_sources_block(cited_sources)}\n\n"
            f"Verify every factual claim now."
        )
        data = self.llm.complete_json(self.system_prompt, user, model=self.model, max_tokens=3000)

        claims = []
        for c in data.get("claims", []):
            status_raw = str(c.get("status", "uncited")).strip().lower()
            status = ClaimStatus(status_raw) if status_raw in _VALID_STATUSES else ClaimStatus.UNCITED
            claims.append(ClaimCheck(
                claim=c.get("claim", "").strip(),
                cited_sources=[int(x) for x in c.get("cited_sources", []) if str(x).isdigit()],
                status=status,
                explanation=c.get("explanation", "").strip(),
            ))

        result = VerificationResult(claims=claims, revision_notes=data.get("revision_notes", "").strip())
        logger.info("Verification: %d/%d claims supported (faithfulness=%.2f)",
                    result.supported, result.total, result.faithfulness_score)
        return result
