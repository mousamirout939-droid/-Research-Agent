from __future__ import annotations

from agent.models import ResearchPlan
from agent.planner import Planner


def test_plan_returns_research_plan(mock_llm):
    planner = Planner(mock_llm)
    plan = planner.plan("How is fusion energy progressing?", max_sub_questions=4)

    assert isinstance(plan, ResearchPlan)
    assert plan.original_query == "How is fusion energy progressing?"
    assert plan.clarified_goal
    assert 1 <= len(plan.sub_questions) <= 4


def test_plan_respects_max_sub_questions_cap(mock_llm):
    planner = Planner(mock_llm)
    plan = planner.plan("Tell me about quantum computing", max_sub_questions=2)
    assert len(plan.sub_questions) <= 2


def test_plan_sub_questions_have_search_queries(mock_llm):
    planner = Planner(mock_llm)
    plan = planner.plan("What's new in battery technology?")
    for sq in plan.sub_questions:
        assert sq.question
        assert isinstance(sq.search_queries, list)


def test_plan_falls_back_gracefully_on_garbage_llm_output():
    class GarbageLLM:
        def complete(self, system, user, *, model, max_tokens=4096, temperature=0.2):
            return "not json at all, just rambling text"

        def complete_json(self, *args, **kwargs):
            # Simulate the repair attempt also failing, as BaseLLM.complete_json would raise.
            from agent.llm import LLMError
            raise LLMError("could not parse")

    planner = Planner(GarbageLLM())
    try:
        planner.plan("some query")
        assert False, "expected LLMError to propagate"
    except Exception as exc:  # noqa: BLE001
        assert "json" in str(exc).lower() or "parse" in str(exc).lower()
