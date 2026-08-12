"""
Thin wrapper around the Anthropic SDK.

Centralizing this gives us three things for free across the whole agent:
  1. one retry/back-off policy for transient API errors,
  2. one place to swap models per-role (planner / writer / verifier),
  3. a `complete_json` helper that asks the model for strict JSON and
     repairs/re-asks once if parsing fails, instead of every caller
     hand-rolling its own `json.loads(...)` try/except.

A `MockLLM` is provided alongside the real client so the planner, writer
and verifier can be unit-tested -- and the whole pipeline can run end to
end in `--mock` mode -- without hitting the network or spending a cent.
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Optional

from agent.config import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the LLM backend fails after exhausting retries."""


class BaseLLM(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, *, model: str, max_tokens: int = 4096,
                 temperature: float = 0.2) -> str:
        ...

    def complete_json(self, system: str, user: str, *, model: str, max_tokens: int = 4096,
                       temperature: float = 0.1) -> dict:
        """Ask for JSON, parse it, and make exactly one repair attempt on failure."""
        raw = self.complete(system, user, model=model, max_tokens=max_tokens, temperature=temperature)
        parsed = _try_parse_json(raw)
        if parsed is not None:
            return parsed

        logger.warning("LLM did not return valid JSON on first attempt; requesting a fix.")
        repair_prompt = (
            "Your previous reply could not be parsed as JSON. Return ONLY valid JSON, "
            "with no markdown code fences and no commentary. Here is what you sent:\n\n"
            f"{raw}\n\nRespond again with corrected, valid JSON only."
        )
        raw2 = self.complete(system, repair_prompt, model=model, max_tokens=max_tokens, temperature=0.0)
        parsed2 = _try_parse_json(raw2)
        if parsed2 is not None:
            return parsed2
        raise LLMError(f"Model failed to produce valid JSON after a repair attempt. Raw output: {raw2[:500]}")


def _try_parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences if the model added them anyway.
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost {...} or [...] block.
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start = text.find(open_c)
            end = text.rfind(close_c)
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        return None


class AnthropicLLM(BaseLLM):
    """Production backend: calls the real Anthropic Messages API."""

    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or settings.anthropic_api_key
        if not api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file, "
                "or run the app/eval with --mock to use the offline mock LLM."
            )
        import anthropic  # imported lazily so `--mock` mode never needs the package configured

        self._client = anthropic.Anthropic(api_key=api_key, timeout=settings.llm_timeout_seconds)

    def complete(self, system: str, user: str, *, model: str, max_tokens: int = 4096,
                 temperature: float = 0.2) -> str:
        import anthropic

        last_exc: Optional[Exception] = None
        for attempt in range(1, settings.llm_max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(block.text for block in response.content if block.type == "text")
            except anthropic.RateLimitError as exc:
                last_exc = exc
                wait = min(2 ** attempt, 30)
                logger.warning("Rate limited (attempt %d/%d); sleeping %ss", attempt, settings.llm_max_retries, wait)
                time.sleep(wait)
            except anthropic.APIStatusError as exc:
                last_exc = exc
                if exc.status_code and exc.status_code < 500:
                    raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
                time.sleep(min(2 ** attempt, 15))
            except anthropic.APIConnectionError as exc:
                last_exc = exc
                time.sleep(min(2 ** attempt, 15))
        raise LLMError(f"LLM call failed after {settings.llm_max_retries} attempts: {last_exc}")


class MockLLM(BaseLLM):
    """
    Deterministic, offline stand-in for the real model.

    Used by unit tests, the `--mock` eval mode, and local development
    without an API key. It produces structurally valid output (correct
    JSON shapes, plausible markdown with citations) so the rest of the
    pipeline can be exercised honestly.
    """

    def complete(self, system: str, user: str, *, model: str, max_tokens: int = 4096,
                 temperature: float = 0.2) -> str:
        # Route on which module's system prompt this is -- each prompt file
        # names its own role explicitly ("You are the PLANNER module...").
        sys_lower = system.lower()
        if "planner module" in sys_lower:
            return self._mock_plan(user)
        if "verifier module" in sys_lower:
            return self._mock_verification(user)
        return self._mock_report(user)

    # -- mock generators ---------------------------------------------------
    def _mock_plan(self, user: str) -> str:
        topic = _extract_topic(user)
        sub_qs = [
            {
                "question": f"What is the current state of {topic}?",
                "search_queries": [f"{topic} overview 2026", f"{topic} latest developments"],
                "rationale": "Establish baseline understanding before going deeper.",
            },
            {
                "question": f"What are the main risks or criticisms of {topic}?",
                "search_queries": [f"{topic} criticism", f"{topic} risks challenges"],
                "rationale": "Avoid a one-sided report.",
            },
            {
                "question": f"What do credible recent sources say about the future of {topic}?",
                "search_queries": [f"{topic} future outlook", f"{topic} forecast experts"],
                "rationale": "Cover forward-looking perspective.",
            },
        ]
        return json.dumps({"clarified_goal": f"Produce a balanced research brief on {topic}.",
                            "sub_questions": sub_qs})

    def _mock_report(self, user: str) -> str:
        topic = _extract_topic(user)
        return (
            f"## {topic.title()}: Research Brief\n\n"
            f"### Overview\n"
            f"{topic.title()} has seen significant attention recently [1]. "
            f"Multiple independent sources confirm steady development in this area [2][3].\n\n"
            f"### Key Considerations\n"
            f"However, several sources raise concerns that should temper enthusiasm [4]. "
            f"On balance, the evidence suggests measured optimism is warranted [1][3].\n\n"
            f"### Outlook\n"
            f"Looking ahead, analysts expect continued change in this space [3].\n"
        )

    def _mock_verification(self, user: str) -> str:
        # Pull "claim text" lines heuristically out of the writer's draft if present.
        claims = re.findall(r"([A-Z][^.\n\[]{20,160}?)\s*((?:\[\d+\])+)", user)
        results = []
        for i, (text, cite_block) in enumerate(claims[:6]):
            cited = [int(n) for n in re.findall(r"\[(\d+)\]", cite_block)]
            status = "supported" if i % 4 != 3 else "partially_supported"
            results.append({
                "claim": text.strip(),
                "cited_sources": cited,
                "status": status,
                "explanation": "Mock verifier: heuristic check against provided source snippets.",
            })
        if not results:
            results = [{
                "claim": "General report content",
                "cited_sources": [1],
                "status": "supported",
                "explanation": "Mock verifier fallback.",
            }]
        return json.dumps({"claims": results, "revision_notes": ""})


def _extract_topic(user_text: str) -> str:
    match = re.search(r'(?:query|topic|question|goal)\s*[:\-]\s*"?(.+?)"?\s*(?:\n|$)', user_text, re.IGNORECASE)
    if match:
        topic = match.group(1).strip().rstrip("?.")
        topic = re.sub(r"^produce a balanced research brief on\s+", "", topic, flags=re.IGNORECASE)
        return topic or "this topic"
    first_line = user_text.strip().splitlines()[0] if user_text.strip() else "this topic"
    return first_line[:80] or "this topic"


def get_llm(mock: bool = False) -> BaseLLM:
    if mock or not settings.has_llm_key:
        if not mock:
            logger.warning("No ANTHROPIC_API_KEY found -- falling back to MockLLM.")
        return MockLLM()
    return AnthropicLLM()
