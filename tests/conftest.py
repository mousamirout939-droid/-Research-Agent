"""
Shared pytest fixtures.

Every test in this suite runs fully offline: the MockLLM and a small set
of hand-built Source objects stand in for the network. No test should
ever require ANTHROPIC_API_KEY, TAVILY_API_KEY, or a live connection --
that's what keeps CI fast, free, and deterministic.
"""
from __future__ import annotations

import pytest

from agent.llm import MockLLM
from agent.models import Source


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM()


@pytest.fixture
def sample_sources() -> list[Source]:
    return [
        Source(
            id=1, url="https://example.com/a", title="Example Source A",
            domain="example.com",
            content="The technology has grown 40% year over year according to industry tracking.",
            fetched_ok=True,
        ),
        Source(
            id=2, url="https://example.org/b", title="Example Source B",
            domain="example.org",
            content="Several independent analysts have raised concerns about scalability limits.",
            fetched_ok=True,
        ),
        Source(
            id=3, url="https://example.net/c", title="Example Source C",
            domain="example.net",
            content="", snippet="A short snippet with no full page content retrieved.",
            fetched_ok=False,
        ),
    ]


@pytest.fixture(autouse=True)
def isolate_cache():
    """
    Disable disk caching for the duration of every test.

    `agent.cache.search_cache` / `page_cache` are module-level singletons
    constructed once at import time, so redirecting their directory per
    test is fragile. Disabling the cache outright is simpler and means
    tests never touch (or depend on) the real cache/ directory on disk.
    """
    from agent.cache import page_cache, search_cache

    search_cache.enabled = False
    page_cache.enabled = False
    yield
    search_cache.enabled = True
    page_cache.enabled = True
