"""
Embedding generator for canonical beans and bean listings.

Embeddings are 1536-dimensional vectors (text-embedding-3-small compatible)
used for approximate nearest-neighbour search via pgvector.

Text construction:
  The embedding text is a structured concatenation of the most semantically
  meaningful fields: name + origin + process + varietal + flavour notes.
  This ensures similar coffees cluster together even with different nomenclature.

  e.g. "Ethiopia Yirgacheffe Konga Washed. Origin: Ethiopia, Yirgacheffe.
        Process: Washed. Varietal: Heirloom. Notes: jasmine, lemon, bergamot."

Generation:
  Uses the Anthropic-compatible OpenAI client with text-embedding-3-small.
  Falls back to a zero vector if the API is unavailable (dev mode).
  Embeddings are stored in canonical_beans.embedding_vector.

Caching:
  Generated once per canonical bean. Re-generated only when key descriptive
  fields change (canonical_name, origin, process, varietal, flavour_notes).
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_EMBEDDING_DIM = 1536


def build_embedding_text(obj: Any) -> str:
    """
    Build the text string used to generate an embedding.
    Works with both ORM objects and plain dicts.
    """

    def _get(field: str) -> str:
        if isinstance(obj, dict):
            v = obj.get(field, "")
        else:
            v = getattr(obj, field, "") or ""
        return str(v).strip() if v else ""

    def _getlist(field: str) -> list[str]:
        if isinstance(obj, dict):
            v = obj.get(field, [])
        else:
            v = getattr(obj, field, []) or []
        return [str(i) for i in v if i]

    parts: list[str] = []

    name = _get("canonical_name") or _get("raw_title")
    if name:
        parts.append(name)

    country = _get("origin_country")
    region = _get("origin_region")
    if country or region:
        origin_parts = [x for x in [country, region] if x]
        parts.append(f"Origin: {', '.join(origin_parts)}.")

    farm = _get("farm_or_estate") or _get("washing_station")
    if farm:
        parts.append(f"Farm: {farm}.")

    process = _get("process")
    if process:
        parts.append(f"Process: {process}.")

    roast = _get("roast_level")
    if roast:
        parts.append(f"Roast: {roast}.")

    varietals = _getlist("varietal")
    if varietals:
        parts.append(f"Varietal: {', '.join(varietals)}.")

    flavour_notes = _getlist("flavour_notes")
    if flavour_notes:
        parts.append(f"Notes: {', '.join(flavour_notes[:8])}.")

    description = _get("raw_description")
    if description:
        parts.append(description[:300])

    return " ".join(parts)


async def generate_embedding(text: str, api_key: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    Call the OpenAI embeddings API and return a 1536-dim vector.
    Returns a zero vector on failure (so matching degrades gracefully).
    """
    if not text.strip():
        return [0.0] * _EMBEDDING_DIM

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.embeddings.create(
            model=model,
            input=text[:8000],  # token limit safety
        )
        return response.data[0].embedding
    except ImportError:
        log.warning("openai package not installed — using zero embedding")
        return [0.0] * _EMBEDDING_DIM
    except Exception as exc:
        log.error("Embedding generation failed: %s", exc)
        return [0.0] * _EMBEDDING_DIM


async def generate_bean_embedding(
    canonical_bean: Any,
    api_key: str,
    model: str = "text-embedding-3-small",
) -> list[float]:
    """Generate embedding for a canonical bean from its key fields."""
    text = build_embedding_text(canonical_bean)
    return await generate_embedding(text, api_key=api_key, model=model)


async def generate_listing_embedding(
    listing: Any,
    api_key: str,
    model: str = "text-embedding-3-small",
) -> list[float]:
    """Generate embedding for a bean listing from its raw fields."""
    text = build_embedding_text(listing)
    return await generate_embedding(text, api_key=api_key, model=model)
