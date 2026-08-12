"""
Eval harness: run the agent against `eval/test_queries.json` and report the
numbers that actually matter for a research agent -- not "did it run" but
"can you trust what it wrote."

Usage:
    python -m eval.run_eval                  # real LLM + search (needs API keys)
    python -m eval.run_eval --mock            # fully offline, deterministic
    python -m eval.run_eval --provider tavily --limit 3

Metrics per query:
    faithfulness_score   fraction of claims the verifier marked "supported"
    citation_coverage    fraction of distinct sources gathered that the
                          final draft actually cited (signal for whether
                          research breadth is being wasted)
    sub_questions        how many sub-questions the planner produced
    sources              how many unique sources were gathered
    revisions            how many writer revision passes were needed
    elapsed_seconds      wall-clock time for the full pipeline

Outputs:
    eval/results/<timestamp>.json   raw per-query results (for diffing runs)
    eval/results.md                 latest human-readable summary (checked
                                     in so the README can point at it)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.config import EVAL_DIR  # noqa: E402
from agent.orchestrator import ResearchAgent  # noqa: E402


def load_queries(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_single(agent: ResearchAgent, item: dict, max_sub_questions: int, max_revisions: int) -> dict:
    start = time.time()
    try:
        report = agent.run(item["query"], max_sub_questions=max_sub_questions, max_revisions=max_revisions)
    except Exception as exc:  # noqa: BLE001 - a failing query should show up as a row, not crash the whole eval
        return {
            "id": item["id"], "category": item.get("category", ""), "query": item["query"],
            "ok": False, "error": str(exc), "elapsed_seconds": round(time.time() - start, 2),
        }

    cited = set(report.draft.sources_used)
    citation_coverage = round(len(cited) / len(report.sources), 4) if report.sources else 0.0

    return {
        "id": item["id"],
        "category": item.get("category", ""),
        "query": item["query"],
        "ok": True,
        "faithfulness_score": report.verification.faithfulness_score,
        "claims_total": report.verification.total,
        "claims_supported": report.verification.supported,
        "sub_questions": len(report.plan.sub_questions),
        "sources": len(report.sources),
        "sources_cited": len(cited),
        "citation_coverage": citation_coverage,
        "revisions": report.revisions,
        "elapsed_seconds": report.elapsed_seconds,
    }


def summarize(results: list[dict]) -> dict:
    ok_results = [r for r in results if r.get("ok")]
    if not ok_results:
        return {"queries": len(results), "succeeded": 0}
    return {
        "queries": len(results),
        "succeeded": len(ok_results),
        "avg_faithfulness": round(statistics.mean(r["faithfulness_score"] for r in ok_results), 4),
        "min_faithfulness": round(min(r["faithfulness_score"] for r in ok_results), 4),
        "avg_citation_coverage": round(statistics.mean(r["citation_coverage"] for r in ok_results), 4),
        "avg_sources": round(statistics.mean(r["sources"] for r in ok_results), 1),
        "avg_revisions": round(statistics.mean(r["revisions"] for r in ok_results), 2),
        "avg_elapsed_seconds": round(statistics.mean(r["elapsed_seconds"] for r in ok_results), 2),
    }


def render_markdown(results: list[dict], summary: dict, mock: bool, provider: str) -> str:
    rows = []
    for r in results:
        if not r.get("ok"):
            rows.append([r["id"], r["category"], "FAILED", "-", "-", "-", "-", r["elapsed_seconds"]])
            continue
        rows.append([
            r["id"], r["category"],
            f"{r['faithfulness_score']:.0%}",
            f"{r['claims_supported']}/{r['claims_total']}",
            r["sources"],
            f"{r['citation_coverage']:.0%}",
            r["revisions"],
            f"{r['elapsed_seconds']:.1f}s",
        ])
    table = tabulate(
        rows,
        headers=["query", "category", "faithfulness", "claims", "sources", "citation coverage", "revisions", "time"],
        tablefmt="github",
    )
    mode = "MOCK (offline, deterministic)" if mock else f"LIVE (search_provider={provider})"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"# Eval results\n\n"
        f"Run: {timestamp} · Mode: **{mode}** · Queries: {summary.get('queries', 0)} "
        f"({summary.get('succeeded', 0)} succeeded)\n\n"
        f"## Summary\n\n"
        f"| metric | value |\n|---|---|\n"
        f"| avg faithfulness score | {summary.get('avg_faithfulness', 0):.0%} |\n"
        f"| min faithfulness score | {summary.get('min_faithfulness', 0):.0%} |\n"
        f"| avg citation coverage | {summary.get('avg_citation_coverage', 0):.0%} |\n"
        f"| avg sources gathered | {summary.get('avg_sources', 0)} |\n"
        f"| avg revision passes | {summary.get('avg_revisions', 0)} |\n"
        f"| avg wall-clock time | {summary.get('avg_elapsed_seconds', 0)}s |\n\n"
        f"## Per-query\n\n{table}\n\n"
        f"*Faithfulness score = fraction of claims the verifier marked \"supported\" against the "
        f"sources actually retrieved. Citation coverage = fraction of gathered sources the final "
        f"draft cited at least once.*\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the research agent against benchmark queries.")
    parser.add_argument("--mock", action="store_true", help="Run fully offline with the deterministic mock LLM/search.")
    parser.add_argument("--provider", default="auto", choices=["auto", "tavily", "duckduckgo", "mock"])
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N queries.")
    parser.add_argument("--max-sub-questions", type=int, default=3)
    parser.add_argument("--max-revisions", type=int, default=1)
    parser.add_argument("--queries", default=str(EVAL_DIR / "test_queries.json"))
    args = parser.parse_args()

    if args.mock:
        import agent.config as config_module
        object.__setattr__(config_module.settings, "search_provider", "mock")

    queries = load_queries(Path(args.queries))
    if args.limit:
        queries = queries[: args.limit]

    agent = ResearchAgent(mock=args.mock)

    results = []
    for i, item in enumerate(queries, start=1):
        print(f"[{i}/{len(queries)}] {item['id']}: {item['query'][:70]}...")
        result = run_single(agent, item, args.max_sub_questions, args.max_revisions)
        status = "OK" if result.get("ok") else "FAILED"
        print(f"    -> {status} ({result.get('elapsed_seconds', 0)}s)")
        results.append(result)

    summary = summarize(results)

    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (results_dir / f"{run_id}.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8"
    )

    markdown = render_markdown(results, summary, args.mock, args.provider)
    (EVAL_DIR / "results.md").write_text(markdown, encoding="utf-8")

    print("\n" + markdown)
    print(f"Saved raw results to eval/results/{run_id}.json and summary to eval/results.md")


if __name__ == "__main__":
    main()
