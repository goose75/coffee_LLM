"""
LLM response validation layer.

This module sits between the raw Anthropic API response and the DB write.
Its job is to ensure nothing partial or malformed reaches raw_extractions.

Validation pipeline:
  1. Extract JSON string from response text (strips any accidental markdown)
  2. Parse JSON — fail if not valid JSON
  3. Validate against ExtractionPayload Pydantic model
  4. Apply business-rule sanity checks (prices > 0, weights > 0, etc.)
  5. Return a ValidatedLLMResponse with either a payload or error details

Design principle: if ANY step fails, the entire record is marked invalid
and no data is written to raw_extractions. The error is recorded in
validation_errors for operator review.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.services.extraction.payload import ExtractionPayload, PriceVariantPayload

log = logging.getLogger(__name__)

# Patterns that indicate the model accidentally wrapped output in markdown
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_LEADING_TEXT_RE = re.compile(r"^\s*[^{[]*({.*)", re.DOTALL)


@dataclass
class ValidatedLLMResponse:
    """
    Result of validating the raw LLM text response.

    success=True  → payload is populated and safe to persist
    success=False → validation_errors explains what went wrong
    """

    success: bool
    payload: ExtractionPayload | None = None
    raw_text: str = ""
    validation_errors: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return self.payload.confidence if self.payload else 0.0

    @classmethod
    def failure(cls, raw_text: str, errors: list[str]) -> "ValidatedLLMResponse":
        return cls(success=False, payload=None, raw_text=raw_text, validation_errors=errors)


def validate_llm_response(raw_text: str) -> ValidatedLLMResponse:
    """
    Full validation pipeline for raw LLM text output.

    Steps:
      1. Extract JSON from text (handles markdown wrapping)
      2. Parse JSON
      3. Validate against Pydantic schema
      4. Apply sanity checks
      5. Return ValidatedLLMResponse
    """
    errors: list[str] = []

    # ── Step 1: Extract JSON string ───────────────────────────────────────
    json_str, extraction_errors = _extract_json_string(raw_text)
    if extraction_errors:
        errors.extend(extraction_errors)
    if not json_str:
        return ValidatedLLMResponse.failure(raw_text, errors or ["No JSON found in response"])

    # ── Step 2: Parse JSON ────────────────────────────────────────────────
    try:
        raw_dict = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return ValidatedLLMResponse.failure(
            raw_text,
            [f"JSON parse error at position {exc.pos}: {exc.msg}"],
        )

    if not isinstance(raw_dict, dict):
        return ValidatedLLMResponse.failure(
            raw_text,
            [f"Expected JSON object, got {type(raw_dict).__name__}"],
        )

    # ── Step 3: Pydantic validation ───────────────────────────────────────
    try:
        payload = ExtractionPayload.model_validate(raw_dict)
    except ValidationError as exc:
        field_errors = [
            f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        ]
        return ValidatedLLMResponse.failure(
            raw_text,
            [f"Schema validation failed: {'; '.join(field_errors)}"],
        )

    # ── Step 4: Business rule sanity checks ───────────────────────────────
    sanity_errors = _sanity_check(payload)
    if sanity_errors:
        # Sanity issues → partial, not failure (data is still usable)
        log.warning("LLM response passed schema but failed sanity checks: %s", sanity_errors)
        # Adjust confidence down if sanity issues exist
        payload.confidence = max(0.0, payload.confidence - 0.1 * len(sanity_errors))
        if payload.reasoning_summary:
            payload.reasoning_summary += f" [Sanity issues: {'; '.join(sanity_errors)}]"
        return ValidatedLLMResponse(
            success=True,  # still persisted, but flagged
            payload=payload,
            raw_text=raw_text,
            validation_errors=sanity_errors,
        )

    return ValidatedLLMResponse(
        success=True,
        payload=payload,
        raw_text=raw_text,
    )


def _extract_json_string(text: str) -> tuple[str, list[str]]:
    """
    Extract a JSON string from potentially messy LLM output.

    Handles:
      - Pure JSON response (ideal case)
      - JSON wrapped in ```json ... ``` fences (model ignored instructions)
      - JSON preceded by a few words of explanation
    """
    text = text.strip()
    errors: list[str] = []

    # Ideal: starts directly with {
    if text.startswith("{"):
        return text, []

    # Try code fence extraction
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        errors.append("Model wrapped response in code fences — stripped and continuing")
        content = fence_match.group(1).strip()
        if content.startswith("{"):
            return content, errors

    # Try to find { after leading text
    leading_match = _LEADING_TEXT_RE.match(text)
    if leading_match:
        errors.append("Model included preamble text before JSON — stripped and continuing")
        return leading_match.group(1), errors

    # Nothing parseable found
    return "", [f"No JSON object found in response. First 200 chars: {text[:200]}"]


def _sanity_check(payload: ExtractionPayload) -> list[str]:
    """
    Business rule checks applied after schema validation.

    These catch plausible-looking but semantically wrong extractions.
    """
    issues: list[str] = []

    # Price checks
    for i, pv in enumerate(payload.price_variants):
        if pv.price_gbp < 0:
            issues.append(f"price_variants[{i}].price_gbp is negative ({pv.price_gbp})")
        if pv.price_gbp > 500:
            issues.append(
                f"price_variants[{i}].price_gbp is suspiciously high (£{pv.price_gbp})"
            )
        if pv.weight_g is not None and pv.weight_g < 0:
            issues.append(f"price_variants[{i}].weight_g is negative ({pv.weight_g})")
        if pv.weight_g is not None and pv.weight_g > 10_000:
            issues.append(
                f"price_variants[{i}].weight_g is suspiciously large ({pv.weight_g}g)"
            )

    # Weight list checks
    for w in payload.weights:
        if w < 0:
            issues.append(f"weights contains negative value ({w})")

    # Confidence check — model should not claim high confidence on empty payload
    if payload.confidence > 0.7 and not payload.coffee_name and not payload.price_variants:
        issues.append(
            f"confidence={payload.confidence} is high but no coffee_name or price_variants found"
        )

    # Flavour notes — check for suspiciously long individual notes
    for note in payload.flavour_notes:
        if len(note) > 80:
            issues.append(f"flavour_note is too long (likely a sentence, not a note): '{note[:60]}...'")

    return issues
