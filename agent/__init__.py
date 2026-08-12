"""
research-agent core package.

Public API:

    from agent import ResearchAgent
    report = ResearchAgent().run("What is retrieval-augmented generation?")
    print(report.markdown_with_footnotes())

See agent/orchestrator.py for the full plan -> research -> write -> verify
loop, and README.md for architecture and setup.
"""
from agent.models import (
    ClaimCheck,
    ClaimStatus,
    Draft,
    ResearchPlan,
    ResearchReport,
    Source,
    SubQuestion,
    VerificationResult,
)
from agent.orchestrator import ProgressEvent, ResearchAgent

__all__ = [
    "ResearchAgent",
    "ProgressEvent",
    "ResearchPlan",
    "SubQuestion",
    "Source",
    "Draft",
    "ClaimCheck",
    "ClaimStatus",
    "VerificationResult",
    "ResearchReport",
]

__version__ = "1.0.0"
