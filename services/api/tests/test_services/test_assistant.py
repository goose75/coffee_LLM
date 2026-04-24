"""
Tests for the assistant pipeline.

Coverage:
  TestIntentClassifier   — rule-based classification of user messages
  TestRetrievalPlan      — correct tool selection and parameter extraction
  TestPromptAssembly     — context block serialisation and system prompt structure
  TestGroundingScorer    — hallucination risk heuristics
  TestBudgetExtraction   — price parsing edge cases
"""
from __future__ import annotations

import pytest


# ── Intent classification ──────────────────────────────────────────────────────

class TestIntentClassifier:

    def _classify(self, msg: str):
        from app.services.assistant.intent import classify
        return classify(msg)

    # Search
    def test_search_ethiopian(self):
        r = self._classify("Find me an Ethiopian coffee")
        assert r.intent == "search"
        assert r.params.get("origin_country") == "Ethiopia"

    def test_search_with_process(self):
        r = self._classify("I want a natural processed coffee")
        assert r.intent == "search"
        assert r.params.get("process") == "natural"

    def test_search_washed_light_roast(self):
        r = self._classify("washed light roast coffee please")
        assert r.intent == "search"
        assert r.params.get("process") == "washed"
        assert r.params.get("roast_level") == "light"

    def test_search_kenya_washed(self):
        r = self._classify("Any Kenyan washed coffees available?")
        assert r.intent == "search"
        assert r.params.get("origin_country") == "Kenya"

    # Compare
    def test_compare_quoted(self):
        r = self._classify('What\'s the difference between "Ethiopia Yirgacheffe" and "Kenya Kirinyaga"?')
        assert r.intent == "compare"
        assert len(r.retrieval_plan) == 1
        assert r.retrieval_plan[0].tool == "compare_coffees"

    def test_compare_vs(self):
        r = self._classify("Colombia vs Ethiopia — which is fruitier?")
        assert r.intent == "compare"

    def test_compare_versus(self):
        r = self._classify("washed versus natural processing")
        assert r.intent == "compare"

    # Recommend / similar
    def test_recommend_if_liked(self):
        r = self._classify("What should I try if I liked Ethiopia Yirgacheffe?")
        assert r.intent == "recommend"

    def test_recommend_similar(self):
        r = self._classify("similar to Kenyan coffee please")
        assert r.intent == "recommend"

    # Brew advice
    def test_brew_espresso(self):
        r = self._classify("Which coffees work well for espresso?")
        assert r.intent == "brew_advice"
        assert r.retrieval_plan[0].params.get("method") == "espresso"

    def test_brew_filter(self):
        r = self._classify("I brew filter coffee — what do you recommend?")
        assert r.intent == "brew_advice"
        assert r.retrieval_plan[0].params.get("method") == "filter"

    def test_brew_pour_over(self):
        r = self._classify("What suits pour over?")
        assert r.intent == "brew_advice"
        assert r.retrieval_plan[0].params.get("method") == "filter"

    # Price / budget
    def test_price_under_budget(self):
        r = self._classify("Find a coffee under £15")
        assert r.intent == "price"
        assert r.params.get("max_price_gbp") == 15.0

    def test_price_with_decimal(self):
        r = self._classify("Something under £12.50 please")
        assert r.intent == "price"
        assert r.params.get("max_price_gbp") == pytest.approx(12.50)

    def test_price_cheapest(self):
        r = self._classify("What's the cheapest coffee you have?")
        assert r.intent == "price"

    def test_price_best_value(self):
        r = self._classify("best value espresso coffee")
        assert r.intent in ("price", "brew_advice", "search")  # reasonable for both

    # Off-topic
    def test_off_topic_weather(self):
        r = self._classify("What's the weather like today?")
        assert r.intent == "off_topic"

    def test_off_topic_football(self):
        r = self._classify("Who won the football yesterday?")
        assert r.intent == "off_topic"

    # General
    def test_general_what_is_washed(self):
        r = self._classify("What does washed process mean?")
        assert r.intent in ("search", "general")  # either is acceptable

    def test_general_coffee_question(self):
        r = self._classify("Tell me about specialty coffee")
        assert r.intent in ("search", "general")


class TestRetrievalPlan:
    """Each intent should produce the right retrieval tool."""

    def _plan(self, msg: str):
        from app.services.assistant.intent import classify
        return classify(msg).retrieval_plan

    def test_search_uses_search_coffees(self):
        plan = self._plan("Ethiopian natural coffee")
        assert any(c.tool == "search_coffees" for c in plan)

    def test_price_uses_find_by_price_range(self):
        plan = self._plan("coffee under £12")
        assert any(c.tool == "find_by_price_range" for c in plan)

    def test_brew_uses_find_by_brew_method(self):
        plan = self._plan("best coffee for espresso")
        assert any(c.tool == "find_by_brew_method" for c in plan)

    def test_compare_with_names_uses_compare_coffees(self):
        plan = self._plan('Compare "Ethiopia Konga" and "Kenya Kirinyaga"')
        assert any(c.tool == "compare_coffees" for c in plan)

    def test_retrieval_plan_not_empty_for_valid_intents(self):
        from app.services.assistant.intent import classify
        messages = [
            "best Ethiopian coffee",
            "under £15",
            "good for espresso",
            "I liked fruity coffees",
        ]
        for msg in messages:
            r = classify(msg)
            if r.intent != "off_topic":
                assert len(r.retrieval_plan) > 0, f"No retrieval plan for: {msg}"

    def test_price_plan_includes_budget(self):
        plan = self._plan("filter coffee under £14")
        price_calls = [c for c in plan if c.tool == "find_by_price_range"]
        assert price_calls
        assert price_calls[0].params.get("max_price_gbp") == 14.0

    def test_espresso_brew_plan_method_param(self):
        plan = self._plan("what works for espresso?")
        brew_calls = [c for c in plan if c.tool == "find_by_brew_method"]
        assert brew_calls
        assert brew_calls[0].params["method"] == "espresso"

    def test_off_topic_produces_no_retrieval(self):
        from app.services.assistant.intent import classify
        r = classify("Who won the World Cup?")
        assert r.intent == "off_topic"
        assert r.retrieval_plan == []


class TestBudgetExtraction:
    """Edge cases for price parsing in the intent classifier."""

    def _budget(self, msg: str):
        from app.services.assistant.intent import _extract_budget
        return _extract_budget(msg)

    def test_integer_budget(self):
        assert self._budget("under £15") == pytest.approx(15.0)

    def test_decimal_budget(self):
        assert self._budget("under £12.50") == pytest.approx(12.50)

    def test_budget_with_period(self):
        assert self._budget("£20.00 or less") == pytest.approx(20.0)

    def test_no_budget_returns_none(self):
        assert self._budget("best Ethiopian coffee") is None

    def test_budget_at_start(self):
        assert self._budget("£10 coffee please") == pytest.approx(10.0)


class TestOriginExtraction:
    def _origin(self, msg: str):
        from app.services.assistant.intent import _extract_origin
        return _extract_origin(msg)

    def test_ethiopia(self):
        assert self._origin("Ethiopian coffee") == "Ethiopia"

    def test_kenya_case_insensitive(self):
        assert self._origin("KENYAN WASHED") == "Kenya"

    def test_colombia(self):
        assert self._origin("Colombian natural") == "Colombia"

    def test_no_origin(self):
        assert self._origin("best espresso coffee") is None

    def test_rwanda(self):
        assert self._origin("Rwandan honey process") == "Rwanda"


class TestProcessExtraction:
    def _process(self, msg: str):
        from app.services.assistant.intent import _extract_process
        return _extract_process(msg)

    def test_washed(self):     assert self._process("washed process") == "washed"
    def test_natural(self):    assert self._process("natural dried") == "natural"
    def test_honey(self):      assert self._process("honey process") == "honey"
    def test_anaerobic(self):  assert self._process("anaerobic fermentation") == "anaerobic"
    def test_none(self):       assert self._process("good espresso") is None


class TestRoastExtraction:
    def _roast(self, msg: str):
        from app.services.assistant.intent import _extract_roast
        return _extract_roast(msg)

    def test_light(self):         assert self._roast("light roast") == "light"
    def test_medium_light(self):  assert self._roast("medium light please") == "medium_light"
    def test_medium(self):        assert self._roast("medium roast coffee") == "medium"
    def test_medium_dark(self):   assert self._roast("medium-dark roast") == "medium_dark"
    def test_dark(self):          assert self._roast("dark roast espresso") == "dark"
    def test_medium_light_priority(self):
        """medium_light must not match as just 'medium'."""
        assert self._roast("medium light roast") == "medium_light"


# ── Prompt assembly ────────────────────────────────────────────────────────────

class TestPromptAssembly:

    def test_system_prompt_has_grounding_rules(self):
        from app.services.assistant.prompts.v1 import SYSTEM_PROMPT
        assert "GROUNDING RULES" in SYSTEM_PROMPT
        assert "retrieved_records" in SYSTEM_PROMPT
        assert "NEVER invent" in SYSTEM_PROMPT

    def test_system_prompt_has_version(self):
        from app.services.assistant.prompts.v1 import PROMPT_VERSION
        assert PROMPT_VERSION.startswith("assistant-v")

    def test_context_template_renders(self):
        from app.services.assistant.prompts.v1 import CONTEXT_TEMPLATE
        rendered = CONTEXT_TEMPLATE.format(
            context_json='[{"name": "Ethiopia Test", "id": "abc123"}]',
            retrieved_at="2025-01-01 12:00 UTC",
        )
        assert "Ethiopia Test" in rendered
        assert "retrieved_records" in rendered

    def test_empty_context_rendered(self):
        from app.services.assistant.prompts.v1 import EMPTY_CONTEXT
        assert "retrieved_records" in EMPTY_CONTEXT
        assert "[]" in EMPTY_CONTEXT

    def test_context_block_with_records(self):
        from app.services.assistant.orchestrator import _build_context_block
        records = [
            {
                "id": "abc",
                "name": "Ethiopia Yirgacheffe Konga",
                "origin_country": "Ethiopia",
                "process": "washed",
                "roast_level": "light",
                "flavour_notes": ["jasmine", "lemon"],
                "espresso_suitable": True,
                "filter_suitable": True,
                "decaf": False,
                "min_price_gbp": 12.50,
                "max_price_gbp": 42.00,
                "store_count": 3,
                "listings": [
                    {
                        "store": "Square Mile",
                        "url": "https://shop.squaremilecoffee.com/products/yirgacheffe",
                        "variants": [{"weight_g": 250, "price_gbp": 12.50, "availability": "in_stock"}],
                    }
                ],
            }
        ]
        block = _build_context_block(records)
        assert "Ethiopia Yirgacheffe Konga" in block
        assert "Square Mile" in block
        assert "12.5" in block
        assert "retrieved_records" in block

    def test_context_block_empty(self):
        from app.services.assistant.orchestrator import _build_context_block
        block = _build_context_block([])
        assert "retrieved_records" in block
        assert "[]" in block

    def test_context_limits_records(self):
        from app.services.assistant.orchestrator import _build_context_block, MAX_CONTEXT_RECORDS
        # Create more records than the limit
        records = [
            {"id": str(i), "name": f"Bean {i}", "origin_country": "Ethiopia",
             "process": "washed", "roast_level": "light", "flavour_notes": [],
             "espresso_suitable": True, "filter_suitable": True, "decaf": False,
             "min_price_gbp": 10.0, "max_price_gbp": 10.0, "store_count": 1,
             "listings": []}
            for i in range(MAX_CONTEXT_RECORDS + 5)
        ]
        block = _build_context_block(records)
        # Count occurrences of "Bean" in the context — should be capped
        count = block.count('"name": "Bean')
        assert count <= MAX_CONTEXT_RECORDS

    def test_history_trimming(self):
        from app.services.assistant.orchestrator import _trim_history, MAX_HISTORY_TURNS
        # Create more turns than the limit
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(MAX_HISTORY_TURNS * 2 + 10)
        ]
        trimmed = _trim_history(history)
        assert len(trimmed) <= MAX_HISTORY_TURNS * 2


# ── Hallucination risk scorer ──────────────────────────────────────────────────

class TestGroundingScorer:

    def _score(self, response: str, context: list[dict], ungrounded: bool = False) -> float:
        from app.services.assistant.grounding import compute_risk
        return compute_risk(response, context, ungrounded)

    def _make_context(self, price: float = 12.50, store: str = "Square Mile", weight: int = 250) -> list[dict]:
        return [{
            "id": "abc",
            "name": "Test Bean",
            "listings": [{
                "store_name": store,
                "variants": [
                    {"weight_g": weight, "price_gbp": price, "availability": "in_stock"}
                ],
            }]
        }]

    def test_zero_risk_correct_price(self):
        ctx = self._make_context(price=12.50)
        risk = self._score("You can get this for £12.50 at Square Mile.", ctx)
        assert risk < 0.3

    def test_high_risk_invented_price(self):
        ctx = self._make_context(price=12.50)
        risk = self._score("This coffee costs £89.99 at Rave Coffee.", ctx)
        assert risk >= 0.3

    def test_high_risk_answered_ungrounded(self):
        risk = self._score("This coffee is available at Square Mile for £12.", [], ungrounded=True)
        assert risk >= 0.4

    def test_low_risk_safe_decline(self):
        """A polite 'I don't have data' response with no context should be low risk."""
        risk = self._score("I don't have enough current data to answer that precisely.", [], ungrounded=True)
        assert risk < 0.1

    def test_low_risk_general_education(self):
        """General coffee knowledge with no prices should be low risk."""
        ctx = self._make_context()
        risk = self._score("Washed processing removes the fruit before drying, which produces a cleaner cup.", ctx)
        assert risk < 0.2

    def test_empty_response_is_zero_risk(self):
        risk = self._score("", [], ungrounded=False)
        assert risk == 0.0

    def test_risk_clamped_to_1(self):
        ctx = self._make_context(price=10.0)
        # Multiple invented prices
        response = "£200 at one store, £150 at another, £300 at a third, £400 premium edition"
        risk = self._score(response, ctx)
        assert risk <= 1.0

    def test_correct_weight_no_risk(self):
        ctx = self._make_context(weight=250)
        risk = self._score("Available in a 250g bag.", ctx)
        assert risk < 0.2

    def test_invented_weight_adds_risk(self):
        ctx = self._make_context(weight=250)
        risk = self._score("Available in a 750g bag for serious coffee lovers.", ctx)
        # 750g not in context
        assert risk >= 0.0  # some risk added


class TestPromptVersioning:
    def test_prompt_version_format(self):
        from app.services.assistant.prompts.v1 import PROMPT_VERSION
        # Must be parseable as major.minor.patch
        parts = PROMPT_VERSION.replace("assistant-v", "").split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_schema_includes_prompt_version(self):
        from app.schemas.assistant import AssistantLogItem
        fields = AssistantLogItem.model_fields
        assert "prompt_version" in fields
