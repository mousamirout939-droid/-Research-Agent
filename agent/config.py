"""
Centralized configuration.

Every tunable lives here and is sourced from environment variables (loaded
from a local `.env` file in development). Nothing else in the codebase
should call `os.environ` directly -- that keeps configuration auditable
and makes the agent easy to deploy in any environment (Docker, HF Spaces,
a serverless function, CI, etc).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env once, at import time, without overriding real env vars that are
# already set (so container/host env vars always win over a stray .env file).
load_dotenv(override=False)

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
CACHE_DIR = ROOT_DIR / "cache"
EVAL_DIR = ROOT_DIR / "eval"


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


@dataclass(frozen=True)
class Settings:
    # --- LLM provider -----------------------------------------------------
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    planner_model: str = field(default_factory=lambda: os.getenv("PLANNER_MODEL", "claude-sonnet-4-6"))
    writer_model: str = field(default_factory=lambda: os.getenv("WRITER_MODEL", "claude-sonnet-4-6"))
    verifier_model: str = field(default_factory=lambda: os.getenv("VERIFIER_MODEL", "claude-haiku-4-5-20251001"))
    llm_max_retries: int = field(default_factory=lambda: _get_int("LLM_MAX_RETRIES", 3))
    llm_timeout_seconds: int = field(default_factory=lambda: _get_int("LLM_TIMEOUT_SECONDS", 90))

    # --- Search provider ----------------------------------------------------
    tavily_api_key: Optional[str] = field(default_factory=lambda: os.getenv("TAVILY_API_KEY"))
    search_provider: str = field(default_factory=lambda: os.getenv("SEARCH_PROVIDER", "auto"))  # auto|tavily|duckduckgo|mock
    max_results_per_query: int = field(default_factory=lambda: _get_int("MAX_RESULTS_PER_QUERY", 4))

    # --- Page fetching ------------------------------------------------------
    fetch_timeout_seconds: int = field(default_factory=lambda: _get_int("FETCH_TIMEOUT_SECONDS", 12))
    max_page_chars: int = field(default_factory=lambda: _get_int("MAX_PAGE_CHARS", 8000))
    fetch_concurrency: int = field(default_factory=lambda: _get_int("FETCH_CONCURRENCY", 6))

    # --- Pipeline behaviour ---------------------------------------------------
    max_sub_questions: int = field(default_factory=lambda: _get_int("MAX_SUB_QUESTIONS", 5))
    max_revisions: int = field(default_factory=lambda: _get_int("MAX_REVISIONS", 2))
    faithfulness_threshold: float = field(default_factory=lambda: _get_float("FAITHFULNESS_THRESHOLD", 0.85))

    # --- Caching -------------------------------------------------------------
    cache_enabled: bool = field(default_factory=lambda: _get_bool("CACHE_ENABLED", True))
    cache_ttl_seconds: int = field(default_factory=lambda: _get_int("CACHE_TTL_SECONDS", 60 * 60 * 24 * 7))

    # --- App -------------------------------------------------------------------
    app_title: str = field(default_factory=lambda: os.getenv("APP_TITLE", "Deep Research Agent"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @property
    def has_llm_key(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_search_key(self) -> bool:
        return bool(self.tavily_api_key)


settings = Settings()
