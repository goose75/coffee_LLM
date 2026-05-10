"""
LLM extraction parser using the Anthropic API.

This is the fallback of last resort in the parser chain:
  schema_org → html_rules → LLMParser

It accepts cleaned page text (not raw HTML) — callers must strip HTML
before passing to this parser. Use the provided clean_page_text() helper
or the ExtractionService which handles this automatically.

Architecture:
  LLMParser is intentionally NOT a subclass of BaseParser because it:
  - Is async (BaseParser.extract() is sync)
  - Takes cleaned text, not raw HTML bytes
  - Has different error modes (rate limits, API errors, context limits)

  It follows the same ExtractionResult contract but is called differently.
  The ExtractionService handles the async/sync boundary.

Retry policy:
  - Overloaded API (529) or rate limit (429): exponential backoff, max 3 tries
  - Context exceeded: truncate and retry once
  - Invalid JSON from model: no retry (deterministic failure, log and return invalid)
  - Timeout: no retry

Cost tracking:
  input_tokens and output_tokens are logged at DEBUG level. In production,
  wire these to your cost monitoring system.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from app.services.extraction.llm_validator import ValidatedLLMResponse, validate_llm_response
from app.services.extraction.payload import ExtractionPayload, ExtractionResult
from app.services.extraction.prompts.v1 import (
    MAX_OUTPUT_TOKENS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_messages,
)

log = logging.getLogger(__name__)

# ── API constants ─────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
BASE_BACKOFF_S = 2.0
MAX_BACKOFF_S = 30.0

# ── Anthropic client (lazy import — avoids import error if not installed) ─────

def _get_anthropic_client():
    try:
        import anthropic
        return anthropic.AsyncAnthropic()
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        )


@dataclass
class LLMExtractionResult:
    """
    Extended result type for LLM extraction — adds token usage and timing.
    """
    result: ExtractionResult
    model_name: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    raw_response_text: str = ""
    attempts: int = 1


class LLMParser:
    """
    Async LLM extraction using Anthropic's claude-sonnet model.

    Usage:
        parser = LLMParser()
        llm_result = await parser.extract(page_text, url)

    The returned LLMExtractionResult carries both the ExtractionResult
    (compatible with the rest of the pipeline) and LLM-specific metadata
    (model, tokens, timing) for storage in raw_extractions.
    """

    def __init__(
        self,
        model: str | None = None,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.model = model or DEFAULT_MODEL
        self.max_retries = max_retries

    async def extract(self, page_text: str, url: str) -> LLMExtractionResult:
        """
        Extract coffee data from cleaned page text.

        Args:
            page_text: Cleaned text content of the page (no HTML tags).
            url:       Source URL, used in the prompt and for logging.

        Returns:
            LLMExtractionResult — never raises.
        """
        start_ms = int(time.monotonic() * 1000)
        messages = build_messages(page_text, url)

        for attempt in range(1, self.max_retries + 1):
            try:
                raw_text, input_tokens, output_tokens = await self._call_api(messages)

                duration_ms = int(time.monotonic() * 1000) - start_ms
                log.debug(
                    "LLM call for %s: %d input tokens, %d output tokens, %dms",
                    url, input_tokens, output_tokens, duration_ms,
                )

                validated = validate_llm_response(raw_text)
                extraction_result = self._to_extraction_result(validated)

                return LLMExtractionResult(
                    result=extraction_result,
                    model_name=self.model,
                    prompt_version=PROMPT_VERSION,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms,
                    raw_response_text=raw_text,
                    attempts=attempt,
                )

            except _RetryableError as exc:
                if attempt >= self.max_retries:
                    log.error(
                        "LLM extraction failed after %d attempts for %s: %s",
                        attempt, url, exc,
                    )
                    return self._failure_result(
                        url=url,
                        error=str(exc),
                        start_ms=start_ms,
                        attempts=attempt,
                    )
                backoff = min(BASE_BACKOFF_S * (2 ** (attempt - 1)), MAX_BACKOFF_S)
                log.warning(
                    "LLM attempt %d/%d failed (%s) — retrying in %.1fs",
                    attempt, self.max_retries, exc, backoff,
                )
                await asyncio.sleep(backoff)

            except _FatalError as exc:
                log.error("Fatal LLM error for %s: %s", url, exc)
                return self._failure_result(
                    url=url,
                    error=str(exc),
                    start_ms=start_ms,
                    attempts=attempt,
                )

            except Exception as exc:
                log.error("Unexpected LLM error for %s: %s", url, exc, exc_info=True)
                return self._failure_result(
                    url=url,
                    error=f"Unexpected error: {exc}",
                    start_ms=start_ms,
                    attempts=attempt,
                )

        # Should not reach here, but satisfy type checker
        return self._failure_result(url=url, error="Max retries exceeded", start_ms=start_ms)

    # ── API call ──────────────────────────────────────────────────────────────

    async def _call_api(self, messages: list[dict]) -> tuple[str, int, int]:
        """
        Make one Anthropic API call. Returns (response_text, input_tokens, output_tokens).
        Raises _RetryableError or _FatalError on failure.
        """
        client = _get_anthropic_client()

        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
        except Exception as exc:
            exc_str = str(exc).lower()
            exc_type = type(exc).__name__

            # Rate limit / overload → retry
            if any(k in exc_str for k in ("rate_limit", "overloaded", "529", "429")):
                raise _RetryableError(f"API rate limited: {exc}") from exc

            # Context window exceeded → fatal (caller should truncate further)
            if "context" in exc_str and ("length" in exc_str or "limit" in exc_str):
                raise _FatalError(f"Context window exceeded: {exc}") from exc

            # Network errors → retry
            if any(k in exc_type.lower() for k in ("timeout", "connect", "network")):
                raise _RetryableError(f"Network error: {exc}") from exc

            # Everything else → fatal
            raise _FatalError(f"API error ({exc_type}): {exc}") from exc

        # Extract text content
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        raw_text = "".join(text_blocks).strip()

        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0

        if not raw_text:
            raise _FatalError("Empty response from API")

        return raw_text, input_tokens, output_tokens

    # ── Result construction ───────────────────────────────────────────────────

    def _to_extraction_result(self, validated: ValidatedLLMResponse) -> ExtractionResult:
        """Convert a ValidatedLLMResponse to an ExtractionResult."""
        if not validated.success or validated.payload is None:
            return ExtractionResult.invalid(
                method="llm",
                errors=validated.validation_errors,
            )

        # Partial only if a sanity-check (data-quality) issue was raised.
        # Extraction-step messages like "code fences stripped" or "preamble
        # stripped" are informational — they don't compromise the payload.
        sanity_errors = [
            e for e in validated.validation_errors
            if "code fences" not in e and "preamble" not in e
        ]
        if sanity_errors:
            return ExtractionResult.partial(
                payload=validated.payload,
                method="llm",
                errors=sanity_errors,
            )

        return ExtractionResult(
            payload=validated.payload,
            validation_status="valid",
            extraction_method="llm",
        )

    def _failure_result(
        self,
        url: str,
        error: str,
        start_ms: int,
        attempts: int = 1,
    ) -> LLMExtractionResult:
        duration_ms = int(time.monotonic() * 1000) - start_ms
        return LLMExtractionResult(
            result=ExtractionResult.invalid(
                method="llm",
                errors=[error],
            ),
            model_name=self.model,
            prompt_version=PROMPT_VERSION,
            duration_ms=duration_ms,
            attempts=attempts,
        )


# ── Internal error types ──────────────────────────────────────────────────────

class _RetryableError(Exception):
    """Transient error that should be retried (rate limits, network)."""


class _FatalError(Exception):
    """Non-retryable error (bad auth, context exceeded, empty response)."""


# ── HTML → text helper ────────────────────────────────────────────────────────

def clean_page_text(html: bytes | str) -> str:
    """
    Convert raw HTML to clean plain text suitable for the LLM prompt.

    Preserves structural whitespace (newlines between blocks) but removes
    all markup. Collapses excessive whitespace.
    """
    from app.services.extraction.text_utils import clean_html

    if isinstance(html, bytes):
        try:
            text = html.decode("utf-8")
        except UnicodeDecodeError:
            text = html.decode("latin-1", errors="replace")
    else:
        text = html

    # Use the existing clean_html which strips tags and decodes entities
    cleaned = clean_html(text)

    # Collapse runs of 3+ newlines to 2
    import re
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()
