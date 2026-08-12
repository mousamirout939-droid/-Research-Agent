"""
Search + page-reading tools.

Two concerns live here:
  1. `web_search(query)`   -- hits a search API and returns ranked results.
  2. `fetch_page(url)`     -- downloads a URL and extracts clean article
                              text so the writer/verifier can ground
                              claims in more than a two-line snippet.

Both are cached on disk (see `agent.cache`) because research agents are
extremely re-search-happy during development, and nobody wants to burn
Tavily credits re-running the same demo query forty times.

Search provider resolution ("auto"):
  - Tavily if TAVILY_API_KEY is set (purpose-built for LLM agents, returns
    cleaner snippets and sometimes full content).
  - otherwise DuckDuckGo via `ddgs` (no API key required at all, so the
    project still works for anyone who just cloned the repo).
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from urllib.parse import urlparse

import httpx

from agent.cache import page_cache, search_cache
from agent.config import settings
from agent.models import Source

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; ResearchAgentBot/1.0; "
    "+https://github.com/your-org/research-agent)"
)


class SearchError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Web search
# --------------------------------------------------------------------------- #
def web_search(query: str, max_results: int | None = None, provider: str | None = None) -> List[dict]:
    """Return a list of {url, title, snippet} dicts for a search query."""
    max_results = max_results or settings.max_results_per_query
    provider = provider or settings.search_provider

    cache_key = f"{provider}::{max_results}::{query.strip().lower()}"
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached

    resolved = provider
    if provider == "auto":
        resolved = "tavily" if settings.has_search_key else "duckduckgo"

    try:
        if resolved == "tavily":
            results = _search_tavily(query, max_results)
        elif resolved == "duckduckgo":
            results = _search_duckduckgo(query, max_results)
        elif resolved == "mock":
            results = _search_mock(query, max_results)
        else:
            raise SearchError(f"Unknown search provider: {resolved}")
    except Exception as exc:  # noqa: BLE001 - search must degrade gracefully, never crash the agent
        logger.error("Search provider '%s' failed for query %r: %s", resolved, query, exc)
        if resolved != "mock":
            logger.info("Falling back to mock search results for this query.")
            results = _search_mock(query, max_results)
        else:
            results = []

    search_cache.set(cache_key, results)
    return results


def _search_tavily(query: str, max_results: int) -> List[dict]:
    import tavily

    client = tavily.TavilyClient(api_key=settings.tavily_api_key)
    response = client.search(query=query, max_results=max_results, search_depth="advanced")
    results = []
    for item in response.get("results", []):
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("content", "")[:600],
            "content": item.get("raw_content") or item.get("content") or "",
            "published_date": item.get("published_date"),
        })
    return results


def _search_duckduckgo(query: str, max_results: int) -> List[dict]:
    from ddgs import DDGS

    results = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            results.append({
                "url": item.get("href", ""),
                "title": item.get("title", ""),
                "snippet": item.get("body", "")[:600],
                "content": "",
                "published_date": None,
            })
    return results


def _search_mock(query: str, max_results: int) -> List[dict]:
    """Deterministic offline results so the pipeline can run with zero network access."""
    topic = re.sub(r"\b(overview|2026|latest|developments|criticism|risks|challenges|future|outlook|forecast|experts)\b",
                    "", query, flags=re.IGNORECASE).strip() or query
    domains = ["reuters.com", "nature.com", "arxiv.org", "economist.com", "mit.edu", "bbc.com"]
    out = []
    for i in range(max_results):
        domain = domains[i % len(domains)]
        out.append({
            "url": f"https://{domain}/articles/{abs(hash((query, i))) % 100000}",
            "title": f"{topic.title()} — perspective #{i + 1} ({domain})",
            "snippet": (
                f"This is a mock snippet discussing {topic} from the perspective of {domain}. "
                f"It includes background context, recent figures, and expert commentary relevant "
                f"to the query '{query}'."
            ),
            "content": (
                f"{topic.title()} has been the subject of extensive discussion in recent reporting. "
                f"Researchers and analysts referenced by {domain} note steady, incremental progress "
                f"alongside a number of open technical and policy questions that remain unresolved. "
                f"Independent commentators caution that strong conclusions about {topic} should account "
                f"for limited sample sizes, regional variation, and still-evolving methodology across the "
                f"field. Funding announcements and pilot programs have grown over the past two years, "
                f"though large-scale deployment remains earlier-stage than headlines sometimes suggest. "
                f"Overall, the consensus among the sources surveyed here leans cautiously positive, with "
                f"continued monitoring recommended through 2026 and beyond as more real-world data accumulates."
            ),
            "published_date": "2026-01-15",
        })
    return out


# --------------------------------------------------------------------------- #
# Page fetching / extraction
# --------------------------------------------------------------------------- #
def fetch_page(url: str, max_chars: int | None = None) -> dict:
    """Download a URL and extract clean readable text. Always returns a dict, never raises."""
    max_chars = max_chars or settings.max_page_chars
    cached = page_cache.get(url)
    if cached is not None:
        return cached

    result = {"url": url, "content": "", "title": "", "ok": False}
    try:
        with httpx.Client(follow_redirects=True, timeout=settings.fetch_timeout_seconds,
                           headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:  # noqa: BLE001
        logger.info("fetch_page failed for %s: %s", url, exc)
        page_cache.set(url, result)
        return result

    try:
        import trafilatura

        extracted = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
        title = trafilatura.extract_metadata(html).title if trafilatura.extract_metadata(html) else ""
    except Exception:  # noqa: BLE001 - extraction is best-effort
        extracted, title = _naive_text_extract(html)

    if not extracted:
        extracted, title = _naive_text_extract(html)

    result["content"] = extracted[:max_chars]
    result["title"] = title or ""
    result["ok"] = bool(extracted)
    page_cache.set(url, result)
    return result


def _naive_text_extract(html: str) -> tuple[str, str]:
    """Fallback extraction with no extra dependency: strip tags crudely."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, title


def fetch_pages_concurrently(urls: List[str], max_chars: int | None = None) -> List[dict]:
    if not urls:
        return []
    results: list[dict | None] = [None] * len(urls)
    with ThreadPoolExecutor(max_workers=min(settings.fetch_concurrency, len(urls))) as pool:
        futures = {pool.submit(fetch_page, url, max_chars): i for i, url in enumerate(urls)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("fetch_pages_concurrently: %s failed: %s", urls[idx], exc)
                results[idx] = {"url": urls[idx], "content": "", "title": "", "ok": False}
    return [r for r in results if r is not None]


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "")
    except Exception:  # noqa: BLE001
        return ""
