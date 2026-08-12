from __future__ import annotations

from agent.cache import DiskCache
from agent.search import _search_mock, domain_of, web_search


def test_search_mock_returns_requested_count():
    results = _search_mock("test topic", max_results=3)
    assert len(results) == 3
    for r in results:
        assert r["url"].startswith("https://")
        assert r["title"]
        assert len(r["content"]) > 400  # enough to skip the page-fetch enrichment step


def test_web_search_with_mock_provider():
    results = web_search("artificial intelligence", max_results=2, provider="mock")
    assert len(results) == 2


def test_domain_of_strips_www():
    assert domain_of("https://www.example.com/page?x=1") == "example.com"
    assert domain_of("https://blog.example.org/post") == "blog.example.org"
    assert domain_of("not a url") == ""


def test_disk_cache_roundtrip(tmp_path):
    cache = DiskCache("test_ns", root=tmp_path, ttl_seconds=3600)
    assert cache.get("missing-key") is None

    cache.set("greeting", {"hello": "world"})
    assert cache.get("greeting") == {"hello": "world"}


def test_disk_cache_respects_disabled_flag(tmp_path):
    cache = DiskCache("test_ns2", root=tmp_path, ttl_seconds=3600)
    cache.enabled = False
    cache.set("key", "value")
    assert cache.get("key") is None  # disabled cache never reads or writes


def test_disk_cache_expires_after_ttl(tmp_path, monkeypatch):
    import time as time_module

    cache = DiskCache("test_ns3", root=tmp_path, ttl_seconds=1)
    cache.set("key", "value")
    assert cache.get("key") == "value"

    real_time = time_module.time
    monkeypatch.setattr(time_module, "time", lambda: real_time() + 10)
    assert cache.get("key") is None


def test_disk_cache_clear_removes_entries(tmp_path):
    cache = DiskCache("test_ns4", root=tmp_path)
    cache.set("a", 1)
    cache.set("b", 2)
    removed = cache.clear()
    assert removed == 2
    assert cache.get("a") is None
