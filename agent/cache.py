"""
A deliberately simple disk-backed cache.

Why not just use `requests_cache` or `diskcache`? Because the only things
we ever cache are (a) search results and (b) extracted page text, both of
which are plain JSON-serializable Python objects, and a one-file-per-key
cache is trivial to inspect, `.gitignore`, and clear by hand during a
demo. No extra moving parts, no SQLite locks to debug at 2am.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from agent.config import settings

logger = logging.getLogger(__name__)


class DiskCache:
    def __init__(self, namespace: str, root: Optional[Path] = None, ttl_seconds: Optional[int] = None):
        from agent.config import CACHE_DIR  # local import keeps config.py import-order safe

        self.dir = (root or CACHE_DIR) / namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
        self.enabled = settings.cache_enabled

    @staticmethod
    def _key_to_filename(key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _path(self, key: str) -> Path:
        return self.dir / self._key_to_filename(key)

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if self.ttl and (time.time() - payload.get("_cached_at", 0)) > self.ttl:
            return None
        logger.debug("cache hit: %s", key)
        return payload.get("value")

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self._path(key)
        payload = {"_cached_at": time.time(), "_key": key, "value": value}
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.warning("failed to write cache entry %s: %s", key, exc)

    def clear(self) -> int:
        count = 0
        for f in self.dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count


search_cache = DiskCache("search")
page_cache = DiskCache("pages")
