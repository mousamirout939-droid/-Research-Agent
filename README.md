# Research Agent

An autonomous research agent that takes a single question, plans how to
investigate it, searches the web, drafts a cited report, and then
**fact-checks its own draft against the sources it actually retrieved**
before handing it back to you — revising itself automatically when a
claim doesn't hold up.

```
plan → research → write → verify → revise (loop) → done
```

Dark-themed Gradio UI included. Runs fully offline in a deterministic
mock mode with zero API keys, or against the real Anthropic API + a real
search provider for production use.

![status](https://img.shields.io/badge/build-passing-34D1A6) ![python](https://img.shields.io/badge/python-3.11%2B-blue) ![license](https://img.shields.io/badge/license-MIT-F2B84B)

---

## Why a verifier loop?

Most "research agent" demos stop at the writer: search, summarize, done.
The problem is that LLM writers confidently invent specifics — a
percentage, a date, a name — that the sources never said. This project
treats that as the central risk to engineer against, not an
afterthought:

1. **Planner** decomposes the question into sub-questions that
   deliberately cover more than one angle (current state, risks/limits,
   outlook) so the report isn't one-sided.
2. **Researcher** runs real web searches per sub-question and fetches
   full page text (not just two-line snippets) so claims can be checked
   against real content.
3. **Writer** drafts a markdown report where *every* factual sentence
   carries an inline citation like `[2][5]`.
4. **Verifier** re-reads the draft against the numbered sources — and
   only those sources, not its own general knowledge — and marks each
   claim `supported` / `partially_supported` / `unsupported` / `uncited`.
5. If the resulting **faithfulness score** is below threshold, the writer
   revises specifically the flagged claims, and the verifier checks
   again (bounded by `MAX_REVISIONS`).

The eval harness (see [Evaluation](#evaluation) below) measures exactly
this faithfulness score across a benchmark set, so "is this agent
trustworthy" has a number attached to it instead of a vibe.

## Screenshot

The UI is a two-column layout: a left "control rail" with the query box,
settings, and a live pipeline stepper styled like manuscript marginalia;
and a right panel with four tabs (**Report**, **Sources**,
**Verification**, **Plan**) that fill in live as the agent works.

Run `python app.py` and open `http://localhost:7860` to see it in dark
mode — the theme (`agent/theme.py` + `static/theme.css`) forces a dark
"ink and highlighter" palette regardless of your OS light/dark setting.

## Quickstart

```bash
git clone <this-repo>
cd research-agent
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:7860`. **No API key required to try it** — leave
`ANTHROPIC_API_KEY` blank in `.env` and tick "Offline demo mode" (it's
ticked by default when no key is present); the app runs the full
pipeline against a deterministic mock LLM and mock search provider so
you can see the UI and the plan→research→write→verify flow immediately.

To run it for real:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...        # optional — falls back to key-free DuckDuckGo search
```

Search works without `TAVILY_API_KEY` too (via DuckDuckGo), so the
minimum to go live is just an Anthropic key.

### Docker

```bash
cp .env.example .env   # fill in your keys
docker compose up --build
```

### Use it as a library

```python
from agent import ResearchAgent

agent = ResearchAgent()  # mock=True for offline mode
report = agent.run("What are the latest advances in solid-state batteries?")

print(report.markdown_with_footnotes())
print(f"faithfulness: {report.verification.faithfulness_score:.0%}")
```

`ResearchAgent.stream(query)` is a generator yielding `ProgressEvent`s
(`planning` → `researching` → `writing` → `verifying` → `revising`* →
`done`) if you want to drive your own UI or CLI instead of `run()`.

## Project layout

```
research-agent/
├── app.py                    # Gradio entry point (the demo UI)
├── agent/
│   ├── config.py             # all settings, sourced from env vars
│   ├── models.py             # typed data: SubQuestion, Source, Draft, VerificationResult...
│   ├── llm.py                 # Anthropic client wrapper + offline MockLLM
│   ├── search.py               # web search (Tavily/DuckDuckGo/mock) + page extraction
│   ├── cache.py                  # disk cache so dev loops don't re-hit paid APIs
│   ├── planner.py                 # query -> ResearchPlan (sub-questions)
│   ├── researcher.py                # ResearchPlan -> list[Source]
│   ├── writer.py                     # plan + sources -> cited Draft (+ revise())
│   ├── verifier.py                     # Draft + sources -> VerificationResult
│   ├── orchestrator.py                  # the plan->research->write->verify->revise loop
│   ├── render.py                         # data -> HTML for the Gradio panels
│   └── theme.py                           # dark Gradio theme ("Night Margin")
├── prompts/                  # planner / writer / verifier prompts, out of code on purpose
├── static/theme.css           # supporting CSS for the dark UI
├── eval/
│   ├── test_queries.json      # benchmark questions across multiple domains
│   ├── run_eval.py             # scores the agent on faithfulness + citation coverage
│   └── results.md               # latest checked-in benchmark run (offline/mock mode)
├── tests/                     # pytest suite, 100% offline via MockLLM
├── notebooks/exploration.ipynb # scratchpad for iterating on prompts before editing .py
├── Dockerfile / docker-compose.yml
└── .github/workflows/ci.yml   # tests + mock eval on every push
```

## Configuration

Everything is an environment variable, read once in `agent/config.py`
(see `.env.example` for the full list with defaults). The highlights:

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for real (non-mock) runs |
| `PLANNER_MODEL` / `WRITER_MODEL` | `claude-sonnet-4-6` | Reasoning-heavy stages |
| `VERIFIER_MODEL` | `claude-haiku-4-5-20251001` | Fact-checking is cheaper/faster |
| `TAVILY_API_KEY` | — | Optional; falls back to DuckDuckGo if unset |
| `SEARCH_PROVIDER` | `auto` | `auto` \| `tavily` \| `duckduckgo` \| `mock` |
| `MAX_SUB_QUESTIONS` | `5` | Planner breadth |
| `MAX_REVISIONS` | `2` | Verifier-triggered rewrite passes, bounded |
| `FAITHFULNESS_THRESHOLD` | `0.85` | Below this, the writer revises |
| `CACHE_ENABLED` | `true` | Disk-cache search results & fetched pages |

## Evaluation

```bash
python -m eval.run_eval --mock          # fully offline, deterministic, CI-friendly
python -m eval.run_eval                 # live LLM + search, needs API keys
python -m eval.run_eval --limit 3 --provider tavily
```

This runs every query in `eval/test_queries.json` through the full
pipeline and reports, per query and averaged:

- **faithfulness score** — fraction of claims the verifier marked
  `supported` against the sources actually retrieved (the headline
  trust metric)
- **citation coverage** — fraction of gathered sources the final draft
  actually cited (catches wasted research breadth)
- sub-questions, sources gathered, revision passes, wall-clock time

Results are written to `eval/results/<timestamp>.json` (raw, for
diffing runs over time) and `eval/results.md` (latest summary, checked
in). The committed `eval/results.md` was generated with `--mock` so it
reproduces byte-for-byte in CI with no API keys — run without `--mock`
locally to see real, topic-varying numbers from the live model.

## Testing

```bash
pytest -v
```

34 tests, fully offline via `MockLLM` and the `mock` search provider —
no network, no API keys, runs in seconds. Covers the planner's JSON
parsing/fallback behavior, the verifier's status normalization, citation
extraction, the disk cache (including TTL expiry), the full orchestrator
loop and stage sequencing, and HTML-escaping in the render layer.

## Design notes

- **Prompts live in `prompts/*.txt`, not in code.** Sharpening planner or
  verifier behavior is a text edit, not a redeploy — see
  `notebooks/exploration.ipynb` for an iteration workflow.
- **The agent never crashes on a flaky search/fetch.** `web_search` and
  `fetch_page` catch their own exceptions and degrade (to the mock
  provider, or an empty/partial result) rather than taking down the
  whole pipeline — a slow or blocked page should cost you one source,
  not the whole report.
- **Citation IDs are assigned once**, by the researcher, and never
  renumbered — so `[7]` means the same source through the entire
  write → verify → revise loop.
- **The verifier checks against retrieved text, not its own knowledge.**
  This is the whole point: a claim that happens to be true but isn't
  backed by anything in the sources you actually gathered is marked
  unsupported, because the report should only assert what your evidence
  shows.

## Security & deployment notes

This is a reference implementation, not a hardened multi-tenant service.
Before exposing it beyond local/demo use:
- Put it behind auth (`auth=` on `demo.launch()`, or a reverse proxy).
- Rate-limit / queue (Gradio's `.queue()` is already enabled, but add
  per-user limits for a public deployment).
- The writer's markdown is rendered as HTML; if you let untrusted users
  influence the model's output beyond a normal research query, add an
  HTML sanitizer (e.g. `bleach`) in `agent/render.py` before shipping
  publicly.

## License

MIT — see [LICENSE](LICENSE).
