"""
Ollama extraction parser using local Mistral model.

This provides a cost-free alternative to the Anthropic LLM fallback.
Ollama runs locally on port 11434 and is called via HTTP API.

Architecture:
  OllamaParser is async, similar to LLMParser.
  It accepts cleaned page text and returns an ExtractionResult.
  Confidence is calibrated lower than LLM (Mistral 7B < Claude Opus).

Retry policy:
  - Connection refused: skip (Ollama not running) or retry once
  - Timeout: return invalid (local inference shouldn't timeout)
  - Invalid JSON from model: return invalid
  - No rate limiting (local API)

Cost: FREE (runs on user's machine)
Speed: 10-30 seconds per extraction (depends on hardware)
Quality: 70-80% of Anthropic quality (Mistral 7B vs Claude Opus)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

from app.services.extraction.llm_validator import (
    ValidatedLLMResponse,
    validate_llm_response,
)
from app.services.extraction.payload import ExtractionPayload, ExtractionResult
from app.services.extraction.prompts import v1

log = logging.getLogger(__name__)

# ── API constants ─────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "mistral"
OLLAMA_TIMEOUT_S = 120.0  # 2 minutes max (local inference can be slow)
MAX_RETRIES = 1  # Only retry on connection error, not on timeouts


@dataclass
class OllamaExtractionResult:
    """Extended result for Ollama extraction with timing and metadata."""

    result: ExtractionResult
    model_name: str = OLLAMA_MODEL
    prompt_version: str = "v1.0.0"
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    raw_response_text: str = ""
    attempts: int = 1


class OllamaParser:
    """
    Async extraction using local Ollama Mistral model.

    Usage:
        parser = OllamaParser()
        ollama_result = await parser.extract(page_text, url)
        extraction_result = ollama_result.result

    Returns OllamaExtractionResult which wraps ExtractionResult.
    """

    def __init__(self, prompt_version: str = "v1.0.0") -> None:
        self.model = OLLAMA_MODEL
        self.base_url = OLLAMA_BASE_URL
        self.prompt_version = prompt_version
        self.timeout = OLLAMA_TIMEOUT_S

    async def extract(
        self, page_text: str, url: str
    ) -> OllamaExtractionResult:
        """
        Extract structured coffee data using Ollama Mistral model.

        Args:
            page_text: Cleaned HTML text (no tags), max ~4000 words.
            url: Source URL for context and logging.

        Returns:
            OllamaExtractionResult with ExtractionResult + metadata.
        """
        start_time = time.time()
        attempts = 0

        for attempt in range(MAX_RETRIES):
            attempts = attempt + 1
            try:
                log.info(
                    "Ollama extraction attempt %d/%d for %s",
                    attempts,
                    MAX_RETRIES,
                    url,
                )

                prompt_text = self._build_prompt(page_text, url)
                response_text = await self._call_ollama(prompt_text)

                # Parse JSON from response
                validated = validate_llm_response(response_text)
                if validated.is_valid:
                    payload = ExtractionPayload.model_validate(
                        validated.extracted_json
                    )
                    # Slightly lower confidence than LLM (local model is less capable)
                    payload.confidence = max(
                        0.0, min(1.0, payload.confidence * 0.9)
                    )
                    payload.source_url = url
                    log.info(
                        "Ollama extraction succeeded for %s: confidence=%.2f",
                        url,
                        payload.confidence,
                    )
                else:
                    log.warning(
                        "Ollama response validation failed for %s: %s",
                        url,
                        validated.error_message,
                    )

                duration_ms = int((time.time() - start_time) * 1000)
                return OllamaExtractionResult(
                    result=ExtractionResult(
                        validation_status=validated.status,
                        extraction_method="ollama",
                        extracted_payload=payload,
                        validation_errors=validated.errors or [],
                    ),
                    model_name=self.model,
                    prompt_version=self.prompt_version,
                    raw_response_text=response_text,
                    duration_ms=duration_ms,
                    attempts=attempts,
                )

            except ConnectionError as exc:
                # Ollama not running
                log.warning(
                    "Ollama connection failed (attempt %d/%d): %s",
                    attempts,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2.0)  # Wait 2s before retry
                else:
                    # Final failure
                    duration_ms = int((time.time() - start_time) * 1000)
                    return OllamaExtractionResult(
                        result=ExtractionResult.invalid(
                            method="ollama",
                            errors=[
                                "Ollama connection failed: Is it running on localhost:11434?"
                            ],
                        ),
                        duration_ms=duration_ms,
                        attempts=attempts,
                    )

            except asyncio.TimeoutError:
                # Inference timeout - don't retry, just fail
                log.error("Ollama extraction timeout for %s", url)
                duration_ms = int((time.time() - start_time) * 1000)
                return OllamaExtractionResult(
                    result=ExtractionResult.invalid(
                        method="ollama",
                        errors=[
                            f"Ollama inference timeout (>{self.timeout}s)"
                        ],
                    ),
                    duration_ms=duration_ms,
                    attempts=attempts,
                )

            except Exception as exc:
                log.exception("Ollama extraction error for %s", url)
                duration_ms = int((time.time() - start_time) * 1000)
                return OllamaExtractionResult(
                    result=ExtractionResult.invalid(
                        method="ollama",
                        errors=[f"Extraction error: {exc}"],
                    ),
                    duration_ms=duration_ms,
                    attempts=attempts,
                )

        # Should not reach here
        duration_ms = int((time.time() - start_time) * 1000)
        return OllamaExtractionResult(
            result=ExtractionResult.invalid(
                method="ollama", errors=["Unexpected: max retries exceeded"]
            ),
            duration_ms=duration_ms,
            attempts=attempts,
        )

    def _build_prompt(self, page_text: str, url: str) -> str:
        """Build extraction prompt for Ollama."""
        # Use v1 prompt structure (simpler, more compatible with Mistral)
        system_prompt = v1.SYSTEM_PROMPT
        few_shot = v1.FEW_SHOT_EXAMPLES

        prompt = f"""{system_prompt}

{few_shot}

--- BEGIN PRODUCT PAGE ---
URL: {url}
Text:
{page_text}
--- END PRODUCT PAGE ---

Extract structured coffee data. Respond with ONLY valid JSON, no other text."""

        return prompt

    async def _call_ollama(self, prompt: str) -> str:
        """
        Call Ollama API with timeout.
        Returns raw response text (expected to be JSON).
        """
        import httpx

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3,  # Low temp for deterministic output
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"Ollama returned status {resp.status_code}"
                    )
                data = resp.json()
                response_text = data.get("response", "")

                if not response_text:
                    raise ValueError("Empty response from Ollama")

                return response_text

        except (httpx.ConnectError, ConnectionError) as exc:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}"
            ) from exc
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(
                f"Ollama inference timeout (>{self.timeout}s)"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Ollama API error: {exc}") from exc
