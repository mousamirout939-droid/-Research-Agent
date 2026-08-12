# Eval results

Run: 2026-06-23 05:33 UTC · Mode: **MOCK (offline, deterministic)** · Queries: 8 (8 succeeded)

## Summary

| metric | value |
|---|---|
| avg faithfulness score | 80% |
| min faithfulness score | 80% |
| avg citation coverage | 17% |
| avg sources gathered | 24 |
| avg revision passes | 1 |
| avg wall-clock time | 0.0s |

## Per-query

| query                      | category   | faithfulness   | claims   |   sources | citation coverage   |   revisions | time   |
|----------------------------|------------|----------------|----------|-----------|---------------------|-------------|--------|
| rag-vs-longcontext         | technology | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| smr-progress               | energy     | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| glp1-cardio-risk           | health     | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| agent-memory-architectures | technology | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| carbon-capture-economics   | climate    | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| remote-work-productivity   | economics  | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| solid-state-batteries      | technology | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |
| fusion-energy-timeline     | energy     | 80%            | 4/5      |        24 | 17%                 |           1 | 0.0s   |

*Faithfulness score = fraction of claims the verifier marked "supported" against the sources actually retrieved. Citation coverage = fraction of gathered sources the final draft cited at least once.*
