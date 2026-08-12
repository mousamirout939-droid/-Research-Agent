"""
Researcher: executes a `ResearchPlan` by running web searches for every
sub-question and fetching full page text for the most promising results,
producing a flat, de-duplicated, numbered list of `Source` objects that
the writer and verifier will both work from.

Numbering sources once, here, and never again, is what lets citation
markers like [3] stay stable and meaningful all the way through the
write -> verify -> revise loop.
"""
from __future__ import annotations

import logging
from typing import List

from agent.config import settings
from agent.models import ResearchPlan, Source
from agent.search import domain_of, fetch_pages_concurrently, web_search

logger = logging.getLogger(__name__)


class Researcher:
    def __init__(self, max_results_per_query: int | None = None, fetch_full_pages: bool = True):
        self.max_results_per_query = max_results_per_query or settings.max_results_per_query
        self.fetch_full_pages = fetch_full_pages

    def gather(self, plan: ResearchPlan) -> List[Source]:
        seen_urls: dict[str, Source] = {}
        next_id = 1

        for sub_q in plan.sub_questions:
            for query in sub_q.search_queries or [sub_q.question]:
                raw_results = web_search(query, max_results=self.max_results_per_query)
                for item in raw_results:
                    url = item.get("url", "").strip()
                    if not url or url in seen_urls:
                        continue
                    source = Source(
                        id=next_id,
                        url=url,
                        title=item.get("title", "") or domain_of(url),
                        snippet=item.get("snippet", ""),
                        content=item.get("content", "") or "",
                        sub_question_id=sub_q.id,
                        domain=domain_of(url),
                        published_date=item.get("published_date"),
                        fetched_ok=bool(item.get("content")),
                    )
                    seen_urls[url] = source
                    next_id += 1

        sources = list(seen_urls.values())
        if self.fetch_full_pages:
            self._enrich_with_full_text(sources)

        logger.info("Gathered %d unique sources across %d sub-questions.", len(sources), len(plan.sub_questions))
        return sources

    def _enrich_with_full_text(self, sources: List[Source]) -> None:
        """For sources where the search API didn't already give us full content, fetch the page."""
        to_fetch = [s for s in sources if len(s.content) < 400]
        if not to_fetch:
            return
        pages = fetch_pages_concurrently([s.url for s in to_fetch], max_chars=settings.max_page_chars)
        by_url = {p["url"]: p for p in pages}
        for source in to_fetch:
            page = by_url.get(source.url)
            if not page:
                continue
            if page.get("ok") and len(page.get("content", "")) > len(source.content):
                source.content = page["content"]
                source.fetched_ok = True
            if not source.title and page.get("title"):
                source.title = page["title"]
