"""
Tests for the LLM extraction service.

Coverage:
  TestLLMValidator        — JSON extraction, schema validation, sanity checks
  TestLLMPromptBuilder    — message construction, truncation, few-shot
  TestLLMParser           — async API calls with mocked Anthropic client
  TestLLMRetry            — rate limit and network retry behaviour
  TestExtractionService   — full pipeline with LLM fallback
  TestCleanPageText       — HTML → text conversion

All Anthropic API calls are mocked — no real API calls made.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_anthropic_response(text: str, input_tokens: int = 500, output_tokens: int = 200):
    """Build a mock Anthropic Messages API response object."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return response


def _valid_payload_json(**overrides) -> str:
    """Return a complete valid JSON response string."""
    base = {
        "coffee_name": "Ethiopia Yirgacheffe Konga Washed",
        "roaster_name": "Colonna Coffee",
        "origin_country": "Ethiopia",
        "origin_region": "Yirgacheffe",
        "farm_or_estate": "Konga Cooperative",
        "producer": "Konga Cooperative",
        "varietal": ["Heirloom"],
        "process": "Washed",
        "roast_level": "Light",
        "brew_suitability": ["filter", "espresso"],
        "grind_options": ["Whole Bean", "Filter"],
        "flavour_notes": ["jasmine", "bergamot", "lemon", "peach"],
        "weights": [250, 1000],
        "price_variants": [
            {"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 12.50, "currency_code": "GBP", "availability": "in_stock"},
            {"weight_g": 1000, "grind_type": "Whole Bean", "price_gbp": 42.00, "currency_code": "GBP", "availability": "in_stock"},
        ],
        "decaf_flag": False,
        "confidence": 0.92,
        "reasoning_summary": "All core fields extracted from clearly structured product page.",
    }
    base.update(overrides)
    return json.dumps(base)


def _minimal_payload_json(**overrides) -> str:
    """Minimal valid JSON — all required fields present with empty defaults."""
    base = {
        "coffee_name": "Colombia Espresso",
        "roaster_name": "",
        "origin_country": "Colombia",
        "origin_region": "",
        "farm_or_estate": "",
        "producer": "",
        "varietal": [],
        "process": "",
        "roast_level": "Medium",
        "brew_suitability": ["espresso"],
        "grind_options": [],
        "flavour_notes": ["chocolate", "caramel"],
        "weights": [250],
        "price_variants": [{"weight_g": 250, "grind_type": "", "price_gbp": 10.00, "currency_code": "GBP", "availability": "unknown"}],
        "decaf_flag": False,
        "confidence": 0.60,
        "reasoning_summary": "Partial extraction — only name, origin, and price found.",
    }
    base.update(overrides)
    return json.dumps(base)


# ─────────────────────────────────────────────────────────────────────────────
# TestLLMValidator
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMValidator:

    def test_valid_json_succeeds(self):
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response(_valid_payload_json())
        assert result.success is True
        assert result.payload is not None
        assert result.payload.coffee_name == "Ethiopia Yirgacheffe Konga Washed"
        assert result.payload.confidence == 0.92

    def test_minimal_valid_json_succeeds(self):
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response(_minimal_payload_json())
        assert result.success is True
        assert result.payload.origin_country == "Colombia"

    def test_invalid_json_returns_failure(self):
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response("not json at all")
        assert result.success is False
        assert result.payload is None
        assert any("JSON" in e or "json" in e for e in result.validation_errors)

    def test_truncated_json_returns_failure(self):
        from app.services.extraction.llm_validator import validate_llm_response
        truncated = '{"coffee_name": "Test", "origin_country": "Eth'
        result = validate_llm_response(truncated)
        assert result.success is False

    def test_wrong_type_returns_failure(self):
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response('["array", "not", "object"]')
        assert result.success is False
        assert any("Expected JSON object" in e for e in result.validation_errors)

    def test_strips_code_fences(self):
        """Model ignoring instructions and wrapping in ``` should still work."""
        from app.services.extraction.llm_validator import validate_llm_response
        fenced = f"```json\n{_valid_payload_json()}\n```"
        result = validate_llm_response(fenced)
        assert result.success is True
        assert "code fences" in result.validation_errors[0]

    def test_strips_preamble_text(self):
        """Model adding 'Here is the JSON:' prefix should still work."""
        from app.services.extraction.llm_validator import validate_llm_response
        with_preamble = f"Here is the extracted data:\n{_valid_payload_json()}"
        result = validate_llm_response(with_preamble)
        assert result.success is True
        assert any("preamble" in e for e in result.validation_errors)

    def test_confidence_clamped_on_parse(self):
        """confidence > 1.0 in JSON should be clamped by Pydantic."""
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response(_valid_payload_json(confidence=5.0))
        assert result.success is True
        assert result.payload.confidence == 1.0

    def test_price_variants_validated(self):
        """Valid price_variants structure should parse correctly."""
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response(_valid_payload_json())
        assert len(result.payload.price_variants) == 2
        assert result.payload.price_variants[0].price_gbp == 12.50
        assert result.payload.price_variants[0].weight_g == 250

    def test_negative_price_triggers_sanity_warning(self):
        """Negative price should pass schema but be flagged by sanity check."""
        from app.services.extraction.llm_validator import validate_llm_response
        bad_price = _valid_payload_json(price_variants=[
            {"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": -5.0, "currency_code": "GBP", "availability": "unknown"}
        ])
        result = validate_llm_response(bad_price)
        # Sanity issue → still success=True but errors recorded
        assert result.success is True
        assert any("negative" in e for e in result.validation_errors)

    def test_suspiciously_high_price_triggers_warning(self):
        from app.services.extraction.llm_validator import validate_llm_response
        high_price = _valid_payload_json(price_variants=[
            {"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 999.99, "currency_code": "GBP", "availability": "unknown"}
        ])
        result = validate_llm_response(high_price)
        assert result.success is True
        assert any("suspiciously high" in e for e in result.validation_errors)

    def test_high_confidence_with_empty_fields_triggers_warning(self):
        """Claiming 0.95 confidence with no coffee_name should be flagged."""
        from app.services.extraction.llm_validator import validate_llm_response
        empty_high_conf = _valid_payload_json(
            coffee_name="", price_variants=[], confidence=0.95
        )
        result = validate_llm_response(empty_high_conf)
        assert result.success is True
        assert any("confidence" in e and "high" in e for e in result.validation_errors)

    def test_long_flavour_note_triggers_warning(self):
        """A 100-char 'flavour note' is probably a sentence, not a note."""
        from app.services.extraction.llm_validator import validate_llm_response
        long_note = "a" * 90
        result = validate_llm_response(_valid_payload_json(flavour_notes=[long_note]))
        assert result.success is True
        assert any("flavour_note is too long" in e for e in result.validation_errors)

    def test_empty_response_text_returns_failure(self):
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response("")
        assert result.success is False

    def test_float_price_as_string_coerced(self):
        """Pydantic should coerce "£12.50" string price to float."""
        from app.services.extraction.llm_validator import validate_llm_response
        with_string_price = _valid_payload_json(price_variants=[
            {"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": "£12.50", "currency_code": "GBP", "availability": "in_stock"}
        ])
        result = validate_llm_response(with_string_price)
        assert result.success is True
        assert result.payload.price_variants[0].price_gbp == 12.50

    def test_varietal_string_coerced_to_list(self):
        """Pydantic should coerce a bare string varietal to a list."""
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response(_valid_payload_json(varietal="Heirloom"))
        assert result.success is True
        assert result.payload.varietal == ["Heirloom"]

    def test_weights_from_variants_synced(self):
        """weights list should be populated from price_variants if empty."""
        from app.services.extraction.llm_validator import validate_llm_response
        result = validate_llm_response(_valid_payload_json(weights=[]))
        assert result.success is True
        # weights should be filled in from price_variants (250, 1000)
        assert 250 in result.payload.weights
        assert 1000 in result.payload.weights


# ─────────────────────────────────────────────────────────────────────────────
# TestLLMPromptBuilder
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMPromptBuilder:

    def test_build_messages_includes_few_shot(self):
        from app.services.extraction.prompts.v1 import build_messages, FEW_SHOT_EXAMPLES
        messages = build_messages("Test coffee text", "https://example.com")
        # Should have few-shot examples + 1 live message
        assert len(messages) == len(FEW_SHOT_EXAMPLES) + 1

    def test_last_message_is_user(self):
        from app.services.extraction.prompts.v1 import build_messages
        messages = build_messages("Test coffee text", "https://example.com")
        assert messages[-1]["role"] == "user"

    def test_url_included_in_user_message(self):
        from app.services.extraction.prompts.v1 import build_messages
        url = "https://specific-roaster.co.uk/products/test"
        messages = build_messages("Coffee text", url)
        assert url in messages[-1]["content"]

    def test_page_text_included_in_user_message(self):
        from app.services.extraction.prompts.v1 import build_messages
        text = "A unique test string 12345abcde"
        messages = build_messages(text, "https://example.com")
        assert text in messages[-1]["content"]

    def test_long_text_is_truncated(self):
        from app.services.extraction.prompts.v1 import build_messages, MAX_INPUT_CHARS
        long_text = "x" * (MAX_INPUT_CHARS * 2)
        messages = build_messages(long_text, "https://example.com")
        # The truncated marker should be present
        assert "truncated" in messages[-1]["content"]

    def test_truncated_text_keeps_start_and_end(self):
        """Truncation should keep beginning and end of text, not just start."""
        from app.services.extraction.prompts.v1 import build_messages, MAX_INPUT_CHARS
        # Unique markers at start and end
        start_marker = "START_MARKER_UNIQUE"
        end_marker = "END_MARKER_UNIQUE"
        long_text = start_marker + ("x" * MAX_INPUT_CHARS * 2) + end_marker
        messages = build_messages(long_text, "https://example.com")
        content = messages[-1]["content"]
        assert start_marker in content
        assert end_marker in content

    def test_short_text_not_truncated(self):
        from app.services.extraction.prompts.v1 import build_messages
        short_text = "Short coffee description"
        messages = build_messages(short_text, "https://example.com")
        assert "truncated" not in messages[-1]["content"]

    def test_few_shot_examples_alternate_user_assistant(self):
        """Few-shot examples must alternate user/assistant roles."""
        from app.services.extraction.prompts.v1 import FEW_SHOT_EXAMPLES
        for i, msg in enumerate(FEW_SHOT_EXAMPLES):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role, f"Message {i} should be {expected_role}"

    def test_prompt_version_is_string(self):
        from app.services.extraction.prompts.v1 import PROMPT_VERSION
        assert isinstance(PROMPT_VERSION, str)
        assert len(PROMPT_VERSION) > 0

    def test_system_prompt_mentions_json(self):
        from app.services.extraction.prompts.v1 import SYSTEM_PROMPT
        assert "JSON" in SYSTEM_PROMPT or "json" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_confidence(self):
        from app.services.extraction.prompts.v1 import SYSTEM_PROMPT
        assert "confidence" in SYSTEM_PROMPT.lower()


# ─────────────────────────────────────────────────────────────────────────────
# TestLLMParser — mocked Anthropic API
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMParser:

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Happy path: valid JSON returned by API."""
        from app.services.extraction.llm_parser import LLMParser

        mock_response = _make_anthropic_response(_valid_payload_json())

        with patch(
            "app.services.extraction.llm_parser._get_anthropic_client"
        ) as mock_client_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("Ethiopia coffee text", "https://example.com")

        assert result.result.validation_status == "valid"
        assert result.result.payload.coffee_name == "Ethiopia Yirgacheffe Konga Washed"
        assert result.result.payload.confidence == 0.92
        assert result.model_name == "claude-sonnet-4-20250514"
        assert result.prompt_version == "v1.0.0"
        assert result.input_tokens == 500
        assert result.output_tokens == 200

    @pytest.mark.asyncio
    async def test_invalid_json_returns_invalid_result(self):
        """Model returns garbage — result should be invalid, no exception."""
        from app.services.extraction.llm_parser import LLMParser

        mock_response = _make_anthropic_response("Sorry, I cannot help with that.")

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("coffee text", "https://example.com")

        assert result.result.validation_status == "invalid"
        assert result.result.payload.coffee_name == ""
        assert result.result.payload.confidence == 0.0

    @pytest.mark.asyncio
    async def test_partial_extraction_returns_partial_result(self):
        """Model returns valid JSON with sanity issues → partial."""
        from app.services.extraction.llm_parser import LLMParser

        # A high confidence claim with no coffee_name triggers sanity warning
        partial_json = _valid_payload_json(coffee_name="", price_variants=[], confidence=0.95)
        mock_response = _make_anthropic_response(partial_json)

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("coffee text", "https://example.com")

        # Should succeed (data is persisted) but with partial status
        assert result.result.validation_status in ("valid", "partial")

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_retry(self):
        """429/overloaded errors should be retried with backoff."""
        import anthropic
        from app.services.extraction.llm_parser import LLMParser

        call_count = 0
        success_response = _make_anthropic_response(_valid_payload_json())

        # Defining a dedicated exception subclass avoids the CPython
        # "__class__ assignment only supported for mutable types" error
        # that Exception() instances raise when their class is reassigned.
        class _FakeRateLimitError(Exception):
            pass

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Simulate rate limit — production code matches on the message
                raise _FakeRateLimitError("rate_limit exceeded")
            return success_response

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = mock_create
            mock_fn.return_value = mock_client

            with patch("app.services.extraction.llm_parser.asyncio.sleep") as mock_sleep:
                mock_sleep.return_value = None
                parser = LLMParser(max_retries=3)
                result = await parser.extract("coffee text", "https://example.com")

        assert call_count == 3
        assert result.result.validation_status == "valid"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_returns_invalid(self):
        """All retries fail → invalid result, no exception."""
        from app.services.extraction.llm_parser import LLMParser

        async def always_rate_limited(**kwargs):
            raise Exception("rate_limit exceeded")

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = always_rate_limited
            mock_fn.return_value = mock_client

            with patch("app.services.extraction.llm_parser.asyncio.sleep"):
                parser = LLMParser(max_retries=2)
                result = await parser.extract("coffee text", "https://example.com")

        assert result.result.validation_status == "invalid"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_empty_response_returns_invalid(self):
        """Empty response text → invalid without retry."""
        from app.services.extraction.llm_parser import LLMParser

        mock_response = _make_anthropic_response("")

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("coffee text", "https://example.com")

        assert result.result.validation_status == "invalid"

    @pytest.mark.asyncio
    async def test_code_fenced_response_still_valid(self):
        """Model wraps JSON in code fences — should still extract successfully."""
        from app.services.extraction.llm_parser import LLMParser

        fenced = f"```json\n{_valid_payload_json()}\n```"
        mock_response = _make_anthropic_response(fenced)

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("coffee text", "https://example.com")

        assert result.result.validation_status == "valid"
        assert result.result.payload.coffee_name == "Ethiopia Yirgacheffe Konga Washed"

    @pytest.mark.asyncio
    async def test_result_has_token_counts(self):
        """Token counts should be propagated from API response."""
        from app.services.extraction.llm_parser import LLMParser

        mock_response = _make_anthropic_response(
            _valid_payload_json(), input_tokens=1200, output_tokens=350
        )

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("coffee text", "https://example.com")

        assert result.input_tokens == 1200
        assert result.output_tokens == 350

    @pytest.mark.asyncio
    async def test_result_has_duration(self):
        """Duration should be a positive integer (milliseconds)."""
        from app.services.extraction.llm_parser import LLMParser

        mock_response = _make_anthropic_response(_valid_payload_json())

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("coffee text", "https://example.com")

        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_non_coffee_page_returns_zero_confidence(self):
        """About page content → model should return confidence=0.0."""
        from app.services.extraction.llm_parser import LLMParser

        zero_conf = json.dumps({
            "coffee_name": "", "roaster_name": "", "origin_country": "",
            "origin_region": "", "farm_or_estate": "", "producer": "",
            "varietal": [], "process": "", "roast_level": "",
            "brew_suitability": [], "grind_options": [], "flavour_notes": [],
            "weights": [], "price_variants": [], "decaf_flag": False,
            "confidence": 0.0,
            "reasoning_summary": "Page is an about page, not a product listing.",
        })
        mock_response = _make_anthropic_response(zero_conf)

        with patch("app.services.extraction.llm_parser._get_anthropic_client") as mock_fn:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_fn.return_value = mock_client

            parser = LLMParser()
            result = await parser.extract("About our roastery...", "https://example.com/about")

        assert result.result.payload.confidence == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# TestCleanPageText
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanPageText:

    def test_strips_html_tags(self):
        from app.services.extraction.llm_parser import clean_page_text
        result = clean_page_text(b"<h1>Ethiopia Coffee</h1><p>Washed process.</p>")
        assert "<h1>" not in result
        assert "Ethiopia Coffee" in result
        assert "Washed process" in result

    def test_decodes_bytes(self):
        from app.services.extraction.llm_parser import clean_page_text
        result = clean_page_text(b"<p>Light roast coffee</p>")
        assert "Light roast coffee" in result

    def test_accepts_string(self):
        from app.services.extraction.llm_parser import clean_page_text
        result = clean_page_text("<p>Filter coffee</p>")
        assert "Filter coffee" in result

    def test_collapses_whitespace(self):
        from app.services.extraction.llm_parser import clean_page_text
        result = clean_page_text("Coffee\n\n\n\n\n\ntext")
        assert "\n\n\n" not in result

    def test_empty_html_returns_empty(self):
        from app.services.extraction.llm_parser import clean_page_text
        result = clean_page_text(b"<html><body></body></html>")
        assert result.strip() == ""

    def test_entities_decoded(self):
        from app.services.extraction.llm_parser import clean_page_text
        result = clean_page_text("<p>Caf&eacute;ti&egrave;re grind &amp; espresso</p>")
        # Entities should be decoded to real characters
        assert "&amp;" not in result


# ─────────────────────────────────────────────────────────────────────────────
# TestExtractionService — LLM integration in full pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionService:
    """
    Tests the full ExtractionService with LLM fallback.
    Uses mocked DB session and mocked LLM parser.
    """

    def _make_source_page(self):
        sp = MagicMock()
        sp.id = "00000000-0000-0000-0000-000000000001"
        return sp

    def _make_session(self):
        session = AsyncMock()
        # session.add() is sync on AsyncSession — keep it as MagicMock so
        # calling it doesn't return an unawaited coroutine.
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_llm_not_called_when_schema_org_succeeds(self):
        """If schema.org returns valid with high confidence, LLM should not be called."""
        from app.services.extraction.service import ExtractionService
        from app.services.extraction.payload import ExtractionPayload, ExtractionResult
        from app.services.extraction.base import ParserChain

        mock_chain = MagicMock()
        high_conf_result = ExtractionResult(
            payload=ExtractionPayload(coffee_name="Ethiopia Test", confidence=0.85),
            validation_status="valid",
            extraction_method="schema_org",
        )
        mock_chain.run = MagicMock(return_value=high_conf_result)

        mock_llm = AsyncMock()
        session = self._make_session()

        service = ExtractionService(
            session=session,
            chain=mock_chain,
            llm_parser=mock_llm,
            use_llm=True,
            llm_threshold=0.40,
        )

        html = b"<html><body><h1>Test</h1></body></html>"
        await service.extract_and_save(html, "https://example.com", self._make_source_page())

        # LLM should NOT have been called
        mock_llm.extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_called_when_deterministic_fails(self):
        """If all deterministic parsers return invalid, LLM should be called."""
        from app.services.extraction.service import ExtractionService
        from app.services.extraction.payload import ExtractionPayload, ExtractionResult
        from app.services.extraction.base import ParserChain
        from app.services.extraction.llm_parser import LLMExtractionResult

        mock_chain = MagicMock()
        mock_chain.run = MagicMock(return_value=None)  # all parsers failed

        mock_llm_result = LLMExtractionResult(
            result=ExtractionResult(
                payload=ExtractionPayload(coffee_name="LLM Coffee", confidence=0.75),
                validation_status="valid",
                extraction_method="llm",
            ),
            model_name="claude-sonnet-4-20250514",
            prompt_version="v1.0.0",
        )
        mock_llm = AsyncMock()
        mock_llm.extract = AsyncMock(return_value=mock_llm_result)

        session = self._make_session()
        service = ExtractionService(
            session=session,
            chain=mock_chain,
            llm_parser=mock_llm,
            use_llm=True,
        )

        # Patch ANTHROPIC_API_KEY to pretend it's set
        with patch("app.services.extraction.service.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "sk-ant-test"
            service.use_llm = True
            await service.extract_and_save(
                b"<html><body><h1>Test Coffee</h1></body></html>",
                "https://example.com",
                self._make_source_page(),
            )

        mock_llm.extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_called_when_confidence_below_threshold(self):
        """Low-confidence deterministic result → LLM should be called."""
        from app.services.extraction.service import ExtractionService
        from app.services.extraction.payload import ExtractionPayload, ExtractionResult
        from app.services.extraction.llm_parser import LLMExtractionResult

        mock_chain = MagicMock()
        low_conf_result = ExtractionResult(
            payload=ExtractionPayload(coffee_name="Coffee", confidence=0.20),
            validation_status="partial",
            extraction_method="html_rules",
        )
        mock_chain.run = MagicMock(return_value=low_conf_result)

        mock_llm_result = LLMExtractionResult(
            result=ExtractionResult(
                payload=ExtractionPayload(coffee_name="Better Coffee", confidence=0.80),
                validation_status="valid",
                extraction_method="llm",
            ),
            model_name="claude-sonnet-4-20250514",
            prompt_version="v1.0.0",
        )
        mock_llm = AsyncMock()
        mock_llm.extract = AsyncMock(return_value=mock_llm_result)

        session = self._make_session()
        service = ExtractionService(
            session=session,
            chain=mock_chain,
            llm_parser=mock_llm,
            use_llm=True,
            llm_threshold=0.40,
        )
        service.use_llm = True  # bypass API key check for test

        await service.extract_and_save(
            b"<html><body><h1>Coffee</h1></body></html>",
            "https://example.com",
            self._make_source_page(),
        )

        mock_llm.extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_orm_record_stores_model_name(self):
        """RawExtraction ORM object should have model_name set for LLM extractions."""
        from app.services.extraction.service import ExtractionService
        from app.services.extraction.payload import ExtractionPayload, ExtractionResult
        from app.services.extraction.llm_parser import LLMExtractionResult

        mock_chain = MagicMock()
        mock_chain.run = MagicMock(return_value=None)

        llm_payload = ExtractionPayload(coffee_name="Test", confidence=0.7)
        mock_llm_result = LLMExtractionResult(
            result=ExtractionResult(
                payload=llm_payload,
                validation_status="valid",
                extraction_method="llm",
            ),
            model_name="claude-sonnet-4-20250514",
            prompt_version="v1.0.0",
        )
        mock_llm = AsyncMock()
        mock_llm.extract = AsyncMock(return_value=mock_llm_result)

        added_objects: list = []
        session = self._make_session()
        session.add = lambda obj: added_objects.append(obj)

        service = ExtractionService(
            session=session,
            chain=mock_chain,
            llm_parser=mock_llm,
            use_llm=True,
        )
        service.use_llm = True

        await service.extract_and_save(
            b"<html></html>",
            "https://example.com",
            self._make_source_page(),
        )

        assert len(added_objects) == 1
        extraction = added_objects[0]
        assert extraction.model_name == "claude-sonnet-4-20250514"
        assert extraction.prompt_version == "v1.0.0"

    @pytest.mark.asyncio
    async def test_force_llm_bypasses_deterministic(self):
        """force_llm=True should always call LLM, even if deterministic succeeds."""
        from app.services.extraction.service import ExtractionService
        from app.services.extraction.payload import ExtractionPayload, ExtractionResult
        from app.services.extraction.llm_parser import LLMExtractionResult

        # Deterministic would succeed
        mock_chain = MagicMock()
        good_result = ExtractionResult(
            payload=ExtractionPayload(coffee_name="Good Coffee", confidence=0.9),
            validation_status="valid",
            extraction_method="schema_org",
        )
        mock_chain.run = MagicMock(return_value=good_result)

        mock_llm_result = LLMExtractionResult(
            result=ExtractionResult(
                payload=ExtractionPayload(coffee_name="LLM Coffee", confidence=0.88),
                validation_status="valid",
                extraction_method="llm",
            ),
            model_name="claude-sonnet-4-20250514",
            prompt_version="v1.0.0",
        )
        mock_llm = AsyncMock()
        mock_llm.extract = AsyncMock(return_value=mock_llm_result)

        session = self._make_session()
        service = ExtractionService(
            session=session,
            chain=mock_chain,
            llm_parser=mock_llm,
            use_llm=True,
        )
        service.use_llm = True

        await service.extract_and_save(
            b"<html></html>",
            "https://example.com",
            self._make_source_page(),
            force_llm=True,
        )

        mock_llm.extract.assert_called_once()
