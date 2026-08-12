"""
Planner: turns a raw user query into a `ResearchPlan`.

This is intentionally the dumbest-possible-correct module: load a prompt
template from disk, fill in one parameter, ask the LLM for JSON, validate
it into Pydantic models. All the actual "intelligence" lives in the prompt
(see prompts/planner_prompt.txt) and the model -- which is exactly the
point of keeping prompts out of code: you can sharpen planning behavior by
editing a text file, no redeploy required.
"""
from __future__ import annotations

import logging

from agent.config import PROMPTS_DIR, settings
from agent.llm import BaseLLM
from agent.models import ResearchPlan, SubQuestion

logger = logging.getLogger(__name__)


class Planner:
    def __init__(self, llm: BaseLLM, model: str | None = None):
        self.llm = llm
        self.model = model or settings.planner_model
        self._prompt_template = (PROMPTS_DIR / "planner_prompt.txt").read_text(encoding="utf-8")

    def plan(self, query: str, max_sub_questions: int | None = None) -> ResearchPlan:
        max_sub_questions = max_sub_questions or settings.max_sub_questions
        system = self._prompt_template.format(max_sub_questions=max_sub_questions)
        user = f'User query: "{query}"\n\nProduce the JSON plan now.'

        logger.info("Planning research for query: %r", query)
        data = self.llm.complete_json(system, user, model=self.model, max_tokens=2048)

        sub_questions = [
            SubQuestion(
                question=sq.get("question", "").strip(),
                search_queries=[q.strip() for q in sq.get("search_queries", []) if q.strip()],
                rationale=sq.get("rationale", "").strip(),
            )
            for sq in data.get("sub_questions", [])
            if sq.get("question")
        ][:max_sub_questions]

        if not sub_questions:
            logger.warning("Planner returned no usable sub-questions; falling back to the raw query.")
            sub_questions = [SubQuestion(question=query, search_queries=[query], rationale="Fallback: direct search.")]

        return ResearchPlan(
            original_query=query,
            clarified_goal=data.get("clarified_goal", query).strip(),
            sub_questions=sub_questions,
        )
