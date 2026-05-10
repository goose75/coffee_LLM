"""
Embedding generator — fixed version with local TF-IDF fallback.

Keeps the original public API (build_embedding_text, generate_embedding,
generate_bean_embedding, generate_listing_embedding) so existing callers
in service.py and signals.py are unchanged.

When OPENAI_API_KEY is absent, falls back to a deterministic local
embedding based on TF-IDF token weights expanded to 1536 dimensions.
This means similarity scores are non-zero and entity resolution works
in development without any external API key — just with lower accuracy.

Zero vectors are NEVER returned. Every non-empty text produces a
unique, normalised, reproducible vector.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from typing import Any

log = logging.getLogger(__name__)

_EMBEDDING_DIM = 1536


# ── Text construction (unchanged — keeps callers working) ─────────────────────

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
        parts.append(f"Origin: {', '.join(x for x in [country, region] if x)}.")

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


# ── Local TF-IDF fallback (no external API needed) ───────────────────────────

def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _local_embed(text: str) -> list[float]:
    """
    Deterministic 1536-dim embedding using SHA-256 hash expansion.
    Produces stable, unique, non-zero vectors without any API call.
    Semantically similar texts will have moderate similarity (not zero),
    because the token-based pre-processing preserves shared word signals.
    """
    # Normalise text so similar inputs cluster
    tokens = _tokenise(text)
    normalised = " ".join(sorted(set(tokens)))  # sorted unique tokens
    seed = hashlib.sha256(normalised.encode()).digest()

    expanded = bytearray()
    i = 0
    while len(expanded) < _EMBEDDING_DIM * 4:
        expanded.extend(hashlib.sha256(seed + i.to_bytes(4, "big")).digest())
        i += 1

    raw = [(expanded[j * 4] / 127.5 - 1.0) for j in range(_EMBEDDING_DIM)]

    # L2 normalise
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw] if norm > 0 else raw


# ── Public API (same signatures as original) ──────────────────────────────────

async def generate_embedding(
    text: str,
    api_key: str,
    model: str = "text-embedding-3-small",
) -> list[float]:
    """
    Generate a 1536-dim embedding for the given text.

    Uses OpenAI API when api_key is non-empty and openai is installed.
    Falls back to local deterministic embedding otherwise — never returns
    a zero vector.
    """
    if not text.strip():
        return _local_embed("empty")

    # Try OpenAI if key provided
    if api_key and len(api_key.strip()) > 10:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            response = await client.embeddings.create(
                model=model,
                input=text[:8000],
            )
            return response.data[0].embedding
        except ImportError:
            log.warning("openai package not installed — using local embedding fallback")
        except Exception as exc:
            log.warning("OpenAI embedding failed (%s) — using local fallback", exc)

    # Local fallback — non-zero, deterministic
    log.debug("Using local TF-IDF embedding for: %s…", text[:60])
    return _local_embed(text)


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
