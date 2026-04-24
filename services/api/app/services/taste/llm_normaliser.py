"""
LLM-assisted flavour normaliser.

Called for raw notes that the rule-based normaliser could not match.
Uses claude-sonnet with a structured JSON prompt and validates the response
before persisting. Stores the full LLM response in llm_audit for review.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.services.taste.prompts.v1 import PROMPT_VERSION, SYSTEM_PROMPT, build_messages
from app.services.taste.taxonomy import TAXONOMY_BY_SLUG

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2048


@dataclass
class LLMTagResult:
    raw_note: str
    slug: str | None
    confidence: float
    reasoning: str
    prompt_version: str = PROMPT_VERSION


async def normalise_notes_llm(
    raw_notes: list[str],
    api_key: str,
) -> list[LLMTagResult]:
    """
    Send unmatched notes to Claude for taxonomy mapping.
    Returns one LLMTagResult per input note.
    Falls back to null-slug entries if the API call fails.
    """
    if not raw_notes:
        return []

    if not api_key:
        log.warning("No ANTHROPIC_API_KEY — skipping LLM taste normalisation")
        return [LLMTagResult(raw_note=n, slug=None, confidence=0.0, reasoning="LLM unavailable") for n in raw_notes]

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=build_messages(raw_notes),
        )
        raw_text = response.content[0].text.strip()
    except Exception as exc:
        log.error("LLM taste normalisation failed: %s", exc)
        return [LLMTagResult(raw_note=n, slug=None, confidence=0.0, reasoning=f"LLM error: {exc}") for n in raw_notes]

    # Parse and validate
    try:
        # Strip any accidental markdown fences
        text = raw_text
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        mappings: list[dict] = parsed.get("mappings", [])
    except (json.JSONDecodeError, KeyError) as exc:
        log.error("LLM taste response not parseable: %s — raw: %s", exc, raw_text[:300])
        return [LLMTagResult(raw_note=n, slug=None, confidence=0.0, reasoning="Parse error") for n in raw_notes]

    # Build a result per raw note; handle missing entries gracefully
    note_to_result: dict[str, LLMTagResult] = {}
    for m in mappings:
        raw = m.get("raw_note", "")
        slug = m.get("slug") or None
        conf = float(m.get("confidence", 0.0))

        # Validate slug exists in taxonomy
        if slug and slug not in TAXONOMY_BY_SLUG:
            log.warning("LLM returned unknown slug '%s' for '%s'", slug, raw)
            slug = None
            conf = 0.0

        note_to_result[raw] = LLMTagResult(
            raw_note=raw,
            slug=slug,
            confidence=min(1.0, max(0.0, conf)),
            reasoning=str(m.get("reasoning", "")),
        )

    # Ensure every input note has a result
    results = []
    for note in raw_notes:
        if note in note_to_result:
            results.append(note_to_result[note])
        else:
            results.append(LLMTagResult(raw_note=note, slug=None, confidence=0.0, reasoning="Note not returned by LLM"))

    return results
