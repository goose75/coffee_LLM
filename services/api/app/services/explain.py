"""
explain.py — Grounded LLM explanation service.

Generates short, data-traceable explanations for five surfaces:
  coffee_profile    — what kind of drinker this coffee suits
  coffee_compare    — how two or three coffees differ
  origin_character  — what makes this origin distinctive
  roaster_style     — what this roaster tends to specialise in
  search_match      — why this coffee matches a query

Architecture:
  - Each explanation type has a strict prompt template.
  - Data is serialised from structured fields only — no free text.
  - Every claim in the output must be traceable to an input field.
  - Results are cached in-memory for 1 hour (keyed by input hash).
  - Falls back to a rules-based summary if the API key is absent or call fails.
  - Maximum output: 2 sentences per explanation.

Grounding rules baked into every prompt:
  - Only mention facts present in the structured_data block.
  - Do not mention prices unless price data is provided.
  - Do not invent tasting notes not present in the flavour_notes list.
  - Write in plain British English — no marketing language.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

log = logging.getLogger("app.services.explain")

# ── In-memory cache ────────────────────────────────────────────────────────────
# Simple TTL cache — keys are SHA256 of (explanation_type, data_json)
# Survives within a worker process; cleared on restart.

_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _cache_key(explanation_type: str, data: dict) -> str:
    payload = json.dumps({"type": explanation_type, "data": data}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _cache_get(key: str) -> str | None:
    entry = _CACHE.get(key)
    if entry and time.time() - entry[1] < _CACHE_TTL_SECONDS:
        return entry[0]
    return None


def _cache_set(key, value: str) -> None:
    _CACHE[key] = (value, time.time())


# ── Prompt templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You write short, grounded explanations for a UK specialty coffee platform.

Rules — non-negotiable:
1. Only mention facts present in the <data> block. Do not invent anything.
2. Never mention prices unless price data is in <data>.
3. Never mention tasting notes not in the flavour_notes list.
4. Write in plain British English. No marketing language or lifestyle fluff.
5. Maximum 2 sentences. Be specific, not vague.
6. If data is insufficient to make a useful claim, write: "Tasting notes are being added."
"""

TEMPLATES: dict[str, str] = {

    "coffee_profile": """<data>
{data_json}
</data>

Write 1–2 sentences describing what kind of coffee drinker would enjoy this coffee.
Base your answer only on: origin_country, process, roast_level, flavour_notes, altitude_masl_min.
Do not use words like "perfect" or "ideal". Be specific and concrete.""",

    "coffee_compare": """<data>
{data_json}
</data>

Write 1–2 sentences comparing these coffees. Focus on the most meaningful difference.
Base your answer only on: process, roast_level, origin_country, flavour_notes.
Do not repeat the coffee names more than once each. Be direct.""",

    "origin_character": """<data>
{data_json}
</data>

Write 1–2 sentences describing what makes coffees from this origin distinctive.
Base your answer only on: country, dominant_process, top_flavour_families, altitude_range.
Do not generalise beyond what the data shows. Start with the origin name.""",

    "roaster_style": """<data>
{data_json}
</data>

Write 1–2 sentences describing this roaster's coffee style.
Base your answer only on: name, dominant_process, dominant_roast, top_flavour_families, top_origins.
Do not mention specific coffee names. Be specific about what they tend toward.""",

    "search_match": """<data>
{data_json}
</data>

Write 1 sentence explaining why this coffee matches the user's query.
Base your answer only on: query, flavour_notes, process, roast_level, origin_country.
Start with a specific attribute from the coffee data, not the query.""",
}


# ── Rules-based fallbacks ─────────────────────────────────────────────────────

def _fallback_coffee_profile(data: dict) -> str:
    notes = data.get("flavour_notes", [])
    process = data.get("process", "")
    roast = (data.get("roast_level", "") or "").replace("_", " ")
    origin = data.get("origin_country", "")
    parts = []
    if notes:
        parts.append(f"Expect {', '.join(notes[:3]).lower()} notes")
    if process == "washed" and roast in ("light", "medium light"):
        parts.append("suits those who prefer clarity and brightness")
    elif process == "natural":
        parts.append("suits those who enjoy fruit-forward, fuller-bodied cups")
    elif roast in ("dark", "medium dark"):
        parts.append("suits those who prefer body and intensity over delicacy")
    if origin:
        parts.append(f"from {origin}")
    sentences = [p[0].upper() + p[1:] if p else p for p in parts[:2]]
    return ". ".join(sentences) + "." if sentences else "Tasting notes are being added."


def _fallback_coffee_compare(data: dict) -> str:
    coffees = data.get("coffees", [])
    if len(coffees) < 2:
        return ""
    a, b = coffees[0], coffees[1]
    a_name = a.get("canonical_name", "Coffee A").split(",")[0]
    b_name = b.get("canonical_name", "Coffee B").split(",")[0]
    a_roast = (a.get("roast_level") or "").replace("_", " ")
    b_roast = (b.get("roast_level") or "").replace("_", " ")
    a_proc = a.get("process", "")
    b_proc = b.get("process", "")
    if a_roast and b_roast and a_roast != b_roast:
        return f"{a_name} is {a_roast} roasted while {b_name} is {b_roast}, giving them different intensity."
    if a_proc and b_proc and a_proc != b_proc:
        return f"{a_name} uses {a_proc} processing while {b_name} is {b_proc}, which shapes their body and sweetness differently."
    return f"{a_name} and {b_name} share a similar profile but differ in origin character."


def _fallback_origin(data: dict) -> str:
    country = data.get("country", "This origin")
    families = data.get("top_flavour_families", [])
    process = data.get("dominant_process", "")
    alt = data.get("altitude_range", "")
    parts = [country]
    if families:
        parts.append(f"coffees tend toward {', '.join(f.lower() for f in families[:2])} character")
    if process:
        parts.append(f"often processed {process}")
    return " ".join(parts[:2]) + "." if len(parts) > 1 else "Origin data is being built."


def _fallback_roaster(data: dict) -> str:
    name = data.get("name", "This roaster")
    process = data.get("dominant_process", "")
    roast = (data.get("dominant_roast", "") or "").replace("_", " ")
    families = data.get("top_flavour_families", [])
    parts = [name]
    if process and roast:
        parts.append(f"tends toward {process}-process, {roast}-roasted coffees")
    elif process:
        parts.append(f"specialises in {process}-process coffees")
    if families:
        parts.append(f"with {families[0].lower()} character")
    return " ".join(parts) + "." if len(parts) > 1 else "Roaster profile is being built."


def _fallback_search_match(data: dict) -> str:
    notes = data.get("flavour_notes", [])
    process = data.get("process", "")
    origin = data.get("origin_country", "")
    if notes:
        return f"Matches on {', '.join(notes[:2]).lower()} notes{f', {process} processed' if process else ''}."
    if origin:
        return f"Origin match — {origin}{f', {process} process' if process else ''}."
    return "Matches your search criteria."


_FALLBACKS = {
    "coffee_profile": _fallback_coffee_profile,
    "coffee_compare": _fallback_coffee_compare,
    "origin_character": _fallback_origin,
    "roaster_style": _fallback_roaster,
    "search_match": _fallback_search_match,
}


# ── Main explain function ─────────────────────────────────────────────────────

async def explain(
    explanation_type: str,
    data: dict,
    api_key: str = "",
) -> str:
    """
    Generate a short grounded explanation.

    Returns a string (1-2 sentences).
    Never raises — falls back to rules-based summary on any error.
    """
    if explanation_type not in TEMPLATES:
        return ""

    # Check cache
    key = _cache_key(explanation_type, data)
    cached = _cache_get(key)
    if cached:
        log.debug("explain cache hit: type=%s key=%s", explanation_type, key)
        return cached

    # Try LLM if API key available
    if api_key:
        try:
            result = await _call_llm(explanation_type, data, api_key)
            _cache_set(key, result)
            return result
        except Exception as e:
            log.warning("explain LLM failed type=%s: %s — using fallback", explanation_type, e)

    # Rules fallback
    fallback_fn = _FALLBACKS.get(explanation_type)
    result = fallback_fn(data) if fallback_fn else ""
    if result:
        _cache_set(key, result)
    return result


async def _call_llm(explanation_type: str, data: dict, api_key: str) -> str:
    """Call Claude Haiku with the appropriate prompt template."""
    import anthropic

    template = TEMPLATES[explanation_type]
    data_json = json.dumps(data, indent=2, default=str)
    user_message = template.format(data_json=data_json)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = response.content[0].text.strip()

    # Sanity check — reject if suspiciously long (prompt injection / hallucination)
    if len(text) > 400:
        log.warning("explain LLM output too long (%d chars), using fallback", len(text))
        raise ValueError("Output too long")

    log.info("explain LLM ok type=%s chars=%d", explanation_type, len(text))
    return text


# ── Data builders — serialise structured fields for each surface ──────────────

def build_coffee_profile_data(coffee: dict) -> dict:
    """Extract only the fields needed for a coffee_profile explanation."""
    return {
        "canonical_name": coffee.get("canonical_name", ""),
        "origin_country": coffee.get("origin_country"),
        "origin_region": coffee.get("origin_region"),
        "process": coffee.get("process"),
        "roast_level": coffee.get("roast_level"),
        "flavour_notes": (coffee.get("flavour_notes") or [])[:6],
        "altitude_masl_min": coffee.get("altitude_masl_min"),
        "espresso_suitable": coffee.get("espresso_suitable_flag", False),
        "filter_suitable": coffee.get("filter_suitable_flag", False),
        "varietal": (coffee.get("varietal") or [])[:2],
    }


def build_compare_data(coffees: list[dict]) -> dict:
    """Extract only the fields needed for a coffee_compare explanation."""
    return {
        "coffees": [
            {
                "canonical_name": c.get("canonical_name", ""),
                "origin_country": c.get("origin_country"),
                "process": c.get("process"),
                "roast_level": c.get("roast_level"),
                "flavour_notes": (c.get("flavour_notes") or [])[:4],
            }
            for c in coffees[:3]
        ]
    }


def build_origin_data(origin: dict) -> dict:
    """Extract only the fields needed for an origin_character explanation."""
    return {
        "country": origin.get("country", ""),
        "coffee_count": origin.get("coffee_count", 0),
        "dominant_process": (origin.get("processes") or [{"process": None}])[0].get("process"),
        "top_flavour_families": [
            f.get("label", "") for f in (origin.get("flavour_families") or [])[:3]
        ],
        "altitude_range": (
            f"{origin.get('altitude_min')}–{origin.get('altitude_max')}m"
            if origin.get("altitude_min") and origin.get("altitude_max")
            else None
        ),
    }


def build_roaster_data(fp: dict) -> dict:
    """Extract only the fields needed for a roaster_style explanation."""
    processes = fp.get("processes") or []
    roasts = fp.get("roast_levels") or []
    families = fp.get("flavour_families") or []
    origins = fp.get("origins") or []
    return {
        "name": fp.get("name", ""),
        "coffee_count": fp.get("coffee_count", 0),
        "dominant_process": processes[0].get("process") if processes else None,
        "dominant_roast": roasts[0].get("roast_level") if roasts else None,
        "top_flavour_families": [f.get("label", "") for f in families[:3]],
        "top_origins": [o.get("country", "") for o in origins[:3]],
    }


def build_search_match_data(query: str, coffee: dict) -> dict:
    """Extract only the fields needed for a search_match explanation."""
    return {
        "query": query[:100],
        "canonical_name": coffee.get("canonical_name", ""),
        "origin_country": coffee.get("origin_country"),
        "process": coffee.get("process"),
        "roast_level": coffee.get("roast_level"),
        "flavour_notes": (coffee.get("flavour_notes") or [])[:4],
    }
