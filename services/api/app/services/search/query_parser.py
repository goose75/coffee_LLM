"""
query_parser.py — Natural language coffee query parser.

Two-layer architecture:
  1. LLM layer  — calls Claude via the Anthropic API for best interpretation
  2. Rules layer — pure Python regex/keyword fallback, always available

The output is a ParsedQuery dataclass that maps cleanly to the /coffees API params.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger("app.services.search.query_parser")

# ── Output schema ─────────────────────────────────────────────────────────────

@dataclass
class ParsedQuery:
    """Structured interpretation of a natural-language coffee query."""

    # Flavour preferences — list of taxonomy labels or free-text notes
    flavour_notes: list[str] = field(default_factory=list)

    # Structured filters
    roast_level: str | None = None        # "light" | "medium" | "dark"
    process: str | None = None            # "washed" | "natural" | "honey" | "anaerobic"
    origin_country: str | None = None
    origin_region: str | None = None
    max_price: float | None = None
    min_price: float | None = None

    # Brew method → maps to espresso_suitable / filter_suitable flags
    espresso_suitable: bool | None = None
    filter_suitable: bool | None = None

    # Body / style signals — used for ranking boost, not hard filters
    body_signal: str | None = None        # "light" | "medium" | "full" | "syrupy"
    acidity_signal: str | None = None     # "bright" | "low" | "juicy" | "clean"
    adventurousness: str | None = None    # "adventurous" | "familiar"

    # Decaf
    decaf: bool | None = None

    # Human-readable summary of what was understood
    summary: str = ""

    # Source of interpretation
    source: str = "rules"                 # "llm" | "rules" | "fallback"

    # Raw original query (for logging)
    raw_query: str = ""


# ── Rules-based parser ────────────────────────────────────────────────────────

# Roast level signals
_ROAST_MAP: dict[str, str] = {
    "light": "light", "light roast": "light", "lightly roasted": "light",
    "bright": "light", "filter roast": "light",
    "medium": "medium", "medium roast": "medium", "balanced": "medium",
    "dark": "dark", "dark roast": "dark", "darkly roasted": "dark",
    "bold": "dark", "strong": "dark", "full roast": "dark",
    "espresso roast": "dark",
}

# Process signals
_PROCESS_MAP: dict[str, str] = {
    "washed": "washed", "wet process": "washed", "wet-processed": "washed",
    "natural": "natural", "dry process": "natural", "dry-processed": "natural",
    "sun-dried": "natural", "sundried": "natural",
    "honey": "honey", "honey process": "honey", "honey-processed": "honey",
    "anaerobic": "anaerobic", "anaerobic fermentation": "anaerobic",
    "carbonic": "carbonic_maceration", "carbonic maceration": "carbonic_maceration",
    "wet hulled": "wet_hulled", "giling basah": "wet_hulled",
}

# Brew method signals
_BREW_MAP: dict[str, tuple[bool | None, bool | None]] = {
    # (espresso_suitable, filter_suitable)
    "espresso": (True, None),
    "filter": (None, True),
    "v60": (None, True), "v-60": (None, True),
    "pour over": (None, True), "pourover": (None, True),
    "chemex": (None, True),
    "aeropress": (None, True),
    "cafetiere": (None, True), "french press": (None, True),
    "moka pot": (True, None),
    "cold brew": (None, True),
    "flat white": (True, None),
    "latte": (True, None),
    "cappuccino": (True, None),
    "americano": (True, None),
}

# Body signals
_BODY_MAP: dict[str, str] = {
    "syrupy": "full", "syrup": "full", "thick": "full", "heavy": "full",
    "full body": "full", "full-bodied": "full", "rich": "full",
    "juicy": "medium", "round": "medium",
    "clean": "light", "delicate": "light", "light body": "light",
    "silky": "light", "tea-like": "light", "tea like": "light",
}

# Acidity signals
_ACIDITY_MAP: dict[str, str] = {
    "bright": "bright", "lively": "bright", "vibrant": "bright",
    "crisp": "bright", "zingy": "bright",
    "juicy": "juicy", "fruity acid": "juicy",
    "low acid": "low", "smooth": "low", "mellow": "low",
    "clean": "clean", "clarity": "clean", "high clarity": "clean",
}

# Origin keywords
_ORIGINS: dict[str, str] = {
    "ethiopia": "Ethiopia", "ethiopian": "Ethiopia",
    "kenya": "Kenya", "kenyan": "Kenya",
    "colombia": "Colombia", "colombian": "Colombia",
    "brazil": "Brazil", "brazilian": "Brazil",
    "guatemala": "Guatemala",
    "rwanda": "Rwanda",
    "panama": "Panama", "panamanian": "Panama",
    "costa rica": "Costa Rica",
    "honduras": "Honduras",
    "peru": "Peru", "peruvian": "Peru",
    "burundi": "Burundi",
    "uganda": "Uganda",
    "indonesia": "Indonesia", "indonesian": "Indonesia",
    "india": "India", "indian": "India",
    "yemen": "Yemen", "yemeni": "Yemen",
    "mexico": "Mexico", "mexican": "Mexico",
    "nicaragua": "Nicaragua",
    "tanzania": "Tanzania",
    "el salvador": "El Salvador",
}

# Common flavour notes to extract
_FLAVOUR_KEYWORDS: list[str] = [
    "chocolate", "dark chocolate", "milk chocolate",
    "caramel", "toffee", "butterscotch", "fudge",
    "nutty", "almond", "hazelnut", "walnut", "pecan",
    "fruity", "fruit",
    "citrus", "lemon", "lime", "orange", "grapefruit", "bergamot",
    "berry", "cherry", "strawberry", "raspberry", "blueberry", "blackcurrant",
    "tropical", "mango", "pineapple", "passionfruit",
    "stone fruit", "peach", "apricot", "plum",
    "floral", "jasmine", "rose", "elderflower",
    "tea", "tea-like", "green tea",
    "wine", "winey", "fermented",
    "honey", "maple", "vanilla",
    "spice", "cinnamon", "cardamom",
    "earthy", "tobacco", "cedar",
    "clean", "sweet",
]

def _extract_price(text: str) -> tuple[float | None, float | None]:
    """Extract price constraints from text. Returns (min_price, max_price)."""
    min_price = None
    max_price = None

    # "under £12", "less than £15", "below £10"
    m = re.search(r'(?:under|below|less than|max|maximum|no more than)\s*[£$]?\s*(\d+(?:\.\d+)?)', text, re.I)
    if m:
        max_price = float(m.group(1))

    # "over £10", "more than £8", "at least £12"
    m = re.search(r'(?:over|above|more than|at least|min|minimum)\s*[£$]?\s*(\d+(?:\.\d+)?)', text, re.I)
    if m:
        min_price = float(m.group(1))

    # "around £12", "about £10"
    m = re.search(r'(?:around|about|roughly|approximately)\s*[£$]?\s*(\d+(?:\.\d+)?)', text, re.I)
    if m:
        val = float(m.group(1))
        min_price = max(0, val - 2)
        max_price = val + 2

    # "£12" standalone
    if max_price is None and min_price is None:
        m = re.search(r'[£$](\d+(?:\.\d+)?)', text)
        if m:
            max_price = float(m.group(1))

    return min_price, max_price


def _build_summary(pq: ParsedQuery) -> str:
    """Generate a human-readable summary of the parsed query."""
    parts = []

    if pq.roast_level:
        parts.append(f"{pq.roast_level} roast")
    if pq.process:
        parts.append(f"{pq.process} process")
    if pq.origin_country:
        parts.append(f"from {pq.origin_country}")
        if pq.origin_region:
            parts.append(f"({pq.origin_region})")
    if pq.espresso_suitable and not pq.filter_suitable:
        parts.append("for espresso")
    elif pq.filter_suitable and not pq.espresso_suitable:
        parts.append("for filter")
    if pq.max_price:
        parts.append(f"under £{pq.max_price:.0f}")
    if pq.min_price:
        parts.append(f"over £{pq.min_price:.0f}")
    if pq.decaf:
        parts.append("decaf")
    if pq.flavour_notes:
        notes_str = ", ".join(pq.flavour_notes[:4])
        parts.append(f"with {notes_str} notes")
    if pq.body_signal:
        parts.append(f"{pq.body_signal}-bodied")
    if pq.acidity_signal:
        parts.append(f"{pq.acidity_signal} acidity")

    if not parts:
        return "Showing all coffees"
    return "Looking for: " + " · ".join(parts)


def parse_rules(query: str) -> ParsedQuery:
    """
    Pure rules-based parser. Fast, offline, no API calls.
    Suitable as a fallback or for simple queries.
    """
    text = query.lower().strip()
    pq = ParsedQuery(raw_query=query, source="rules")

    # Roast — check negation patterns first
    if re.search(r'not\\s+too\\s+dark', text) and re.search(r'not\\s+too\\s+light', text):
        pq.roast_level = "medium"
    else:
        for kw, val in sorted(_ROAST_MAP.items(), key=lambda x: -len(x[0])):
            if kw in text:
                pq.roast_level = val
                break

    # Process
    for kw, val in sorted(_PROCESS_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text:
            pq.process = val
            break

    # Brew method
    for kw, (esp, filt) in sorted(_BREW_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text:
            pq.espresso_suitable = esp
            pq.filter_suitable = filt
            break

    # Body
    for kw, val in sorted(_BODY_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text:
            pq.body_signal = val
            break

    # Acidity
    for kw, val in sorted(_ACIDITY_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text:
            pq.acidity_signal = val
            break

    # Origin
    for kw, val in sorted(_ORIGINS.items(), key=lambda x: -len(x[0])):
        if kw in text:
            pq.origin_country = val
            break

    # Price
    pq.min_price, pq.max_price = _extract_price(text)

    # Decaf
    if "decaf" in text or "caffeine free" in text or "caffeine-free" in text or "decaffeinated" in text:
        pq.decaf = True

    # Adventurousness
    if any(w in text for w in ["adventurous", "unusual", "exotic", "rare", "unique", "experimental"]):
        pq.adventurousness = "adventurous"
    elif any(w in text for w in ["familiar", "classic", "traditional", "everyday", "easy"]):
        pq.adventurousness = "familiar"

    # Flavour notes — extract any matching keywords
    found_notes: list[str] = []
    for kw in sorted(_FLAVOUR_KEYWORDS, key=len, reverse=True):
        if kw in text and kw not in found_notes:
            found_notes.append(kw)
    pq.flavour_notes = found_notes[:8]

    pq.summary = _build_summary(pq)
    return pq


# ── LLM parser ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a coffee query interpreter for a UK specialty coffee platform.
Convert the user's natural language coffee query into structured JSON.

Rules:
- Only extract what is explicitly or clearly implied in the query
- Never invent constraints not present in the query
- Use null for any field that isn't mentioned
- flavour_notes should be simple English descriptors, not jargon
- roast_level must be one of: "light", "medium", "dark", or null
- process must be one of: "washed", "natural", "honey", "anaerobic", or null
- brew_method maps to: "espresso" | "filter" | null
- max_price and min_price are numbers in GBP (£)
- summary should be a single elegant sentence describing what was understood

Respond ONLY with valid JSON matching this schema exactly:
{
  "flavour_notes": ["string"],
  "roast_level": "light" | "medium" | "dark" | null,
  "process": "washed" | "natural" | "honey" | "anaerobic" | null,
  "origin_country": "string" | null,
  "origin_region": "string" | null,
  "max_price": number | null,
  "min_price": number | null,
  "brew_method": "espresso" | "filter" | null,
  "body_signal": "light" | "medium" | "full" | "syrupy" | null,
  "acidity_signal": "bright" | "juicy" | "low" | "clean" | null,
  "decaf": true | false | null,
  "adventurousness": "adventurous" | "familiar" | null,
  "summary": "string"
}"""

USER_PROMPT_TEMPLATE = """Coffee query: {query}"""


async def parse_llm(query: str) -> ParsedQuery:
    """
    LLM-based parser using Claude. Falls back to rules if LLM unavailable.
    """
    import httpx

    pq_rules = parse_rules(query)  # always compute rules as fallback

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": _get_api_key(),
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 400,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": USER_PROMPT_TEMPLATE.format(query=query)}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["content"][0]["text"].strip()

            # Strip markdown code fences if present
            raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
            raw_text = re.sub(r"\n?```$", "", raw_text)

            parsed = json.loads(raw_text)

            pq = ParsedQuery(raw_query=query, source="llm")
            pq.flavour_notes     = parsed.get("flavour_notes") or []
            pq.roast_level       = parsed.get("roast_level")
            pq.process           = parsed.get("process")
            pq.origin_country    = parsed.get("origin_country")
            pq.origin_region     = parsed.get("origin_region")
            pq.max_price         = parsed.get("max_price")
            pq.min_price         = parsed.get("min_price")
            pq.body_signal       = parsed.get("body_signal")
            pq.acidity_signal    = parsed.get("acidity_signal")
            pq.decaf             = parsed.get("decaf")
            pq.adventurousness   = parsed.get("adventurousness")
            pq.summary           = parsed.get("summary") or _build_summary(pq)
            pq.espresso_suitable = True if parsed.get("brew_method") == "espresso" else None
            pq.filter_suitable   = True if parsed.get("brew_method") == "filter" else None

            logger.info("LLM parsed query=%r → %s", query, json.dumps(asdict(pq)))
            return pq

    except Exception as e:
        logger.warning("LLM parse failed for query=%r: %s — using rules fallback", query, e)
        pq_rules.source = "fallback"
        return pq_rules


def _get_api_key() -> str:
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return key


def parse(query: str, use_llm: bool = False) -> ParsedQuery:
    """Synchronous entry point — always uses rules parser."""
    return parse_rules(query)


async def parse_async(query: str) -> ParsedQuery:
    """Async entry point — tries LLM, falls back to rules."""
    if not query.strip():
        return ParsedQuery(raw_query=query, summary="Showing all coffees")
    return await parse_llm(query)
