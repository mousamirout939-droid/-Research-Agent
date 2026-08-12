"""
Orchestrator: wires planner -> researcher -> writer -> verifier into the
agent's core loop, and is the single entry point both `app.py` (Gradio)
and `eval/run_eval.py` call into.

`run()` returns a finished `ResearchReport`.
`stream()` is a generator yielding `ProgressEvent`s as the pipeline moves
through each stage -- the UI subscribes to this to show live status
instead of a single multi-minute spinner.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator, Literal, Optional

from agent.config import settings
from agent.llm import BaseLLM, get_llm
from agent.models import Draft, ResearchPlan, ResearchReport, Source, VerificationResult
from agent.planner import Planner
from agent.researcher import Researcher
from agent.verifier import Verifier
from agent.writer import Writer

logger = logging.getLogger(__name__)

Stage = Literal["planning", "researching", "writing", "verifying", "revising", "done", "error"]


@dataclass
class ProgressEvent:
    stage: Stage
    message: str
    plan: Optional[ResearchPlan] = None
    sources: Optional[list[Source]] = None
    draft: Optional[Draft] = None
    verification: Optional[VerificationResult] = None
    report: Optional[ResearchReport] = None


class ResearchAgent:
    def __init__(self, llm: Optional[BaseLLM] = None, mock: bool = False):
        self.llm = llm or get_llm(mock=mock)
        self.planner = Planner(self.llm)
        self.researcher = Researcher()
        self.writer = Writer(self.llm)
        self.verifier = Verifier(self.llm)

    # ------------------------------------------------------------------ #
    # Streaming entry point (used by the Gradio UI)
    # ------------------------------------------------------------------ #
    def stream(self, query: str, max_sub_questions: Optional[int] = None,
               max_revisions: Optional[int] = None) -> Iterator[ProgressEvent]:
        max_revisions = settings.max_revisions if max_revisions is None else max_revisions
        start = time.time()

        try:
            yield ProgressEvent("planning", f"Breaking down the query into sub-questions…")
            plan = self.planner.plan(query, max_sub_questions=max_sub_questions)
            yield ProgressEvent("planning", f"Plan ready: {len(plan.sub_questions)} sub-questions.", plan=plan)

            yield ProgressEvent("researching", "Searching the web and reading source pages…", plan=plan)
            sources = self.researcher.gather(plan)
            yield ProgressEvent(
                "researching", f"Gathered {len(sources)} sources.", plan=plan, sources=sources
            )

            yield ProgressEvent("writing", "Drafting the report with inline citations…", plan=plan, sources=sources)
            draft = self.writer.write(plan, sources)
            yield ProgressEvent("writing", "Draft complete.", plan=plan, sources=sources, draft=draft)

            verification = None
            revisions = 0
            for attempt in range(max_revisions + 1):
                yield ProgressEvent("verifying", "Checking claims against sources for faithfulness…",
                                     plan=plan, sources=sources, draft=draft)
                verification = self.verifier.verify(draft, sources)
                yield ProgressEvent(
                    "verifying",
                    f"Faithfulness score: {verification.faithfulness_score:.0%} "
                    f"({verification.supported}/{verification.total} claims supported).",
                    plan=plan, sources=sources, draft=draft, verification=verification,
                )

                score_ok = verification.faithfulness_score >= settings.faithfulness_threshold
                if score_ok or attempt == max_revisions:
                    break

                revisions += 1
                yield ProgressEvent("revising", f"Revision {revisions}: rewriting flagged claims…",
                                     plan=plan, sources=sources, draft=draft, verification=verification)
                draft = self.writer.revise(plan, sources, draft, verification)

            report = ResearchReport(
                query=query, plan=plan, sources=sources, draft=draft,
                verification=verification, revisions=revisions, elapsed_seconds=round(time.time() - start, 2),
            )
            yield ProgressEvent("done", "Research complete.", plan=plan, sources=sources,
                                 draft=draft, verification=verification, report=report)

        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI instead of crashing it
            logger.exception("Research pipeline failed")
            yield ProgressEvent("error", f"The agent hit an error: {exc}")

    # ------------------------------------------------------------------ #
    # Simple blocking entry point (used by eval / scripts / tests)
    # ------------------------------------------------------------------ #
    def run(self, query: str, max_sub_questions: Optional[int] = None,
            max_revisions: Optional[int] = None) -> ResearchReport:
        last_report: Optional[ResearchReport] = None
        for event in self.stream(query, max_sub_questions=max_sub_questions, max_revisions=max_revisions):
            if event.stage == "error":
                raise RuntimeError(event.message)
            if event.stage == "done":
                last_report = event.report
        if last_report is None:
            raise RuntimeError("Pipeline finished without producing a report.")
        return last_report
