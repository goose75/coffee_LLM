"""
Intent classifier for the assistant pipeline.

Runs before any LLM call. Uses rule-based pattern matching first (cheap, instant),
with a structured fallback classification if the message is ambiguous.

Intent types:
  search          — "find me a coffee that..." / "what coffees do you have from..."
  compare         — "what's the difference between X and Y"
  recommend       — "what should I try if I liked X"
  brew_advice     — "which coffees work for espresso / filter / aeropress"
  price           — "what's the cheapest X" / "under £15"
  general         — coffee education with no specific catalogue intent
  off_topic       — not about coffee at all

Returns an IntentResult dataclass with:
  - intent: the classified intent
  - params: extracted parameters (origin, budget, brew method, etc.)
  - retrieval_plan: which tool(s) to call and with what args
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RetrievalCall:
    tool: str
    params: dict


@dataclass
class IntentResult:
    intent: str
    confidence: float
    params: dict = field(default_factory=dict)
    retrieval_plan: list[RetrievalCall] = field(default_factory=list)
    needs_llm_classification: bool = False


# ── Pattern tables ─────────────────────────────────────────────────────────────

_COMPARE_PATTERNS = [
    r"\bdifference\b", r"\bcompare\b", r"\bvs\.?\b", r"\bversus\b",
    r"\bbetter\b.{0,20}\bor\b", r"\bwhich.{0,10}(is|would)\b",
]

_RECOMMEND_PATTERNS = [
    r"\bif i liked\b", r"\bsimilar to\b", r"\blike\b.{0,20}\btry\b",
    r"\bwhat (else|next|should i try)\b", r"\brecommend\b", r"\bsuggestion\b",
]

_BREW_PATTERNS = [
    r"\bespresso\b", r"\bfilter\b", r"\baeropress\b", r"\bpour.?over\b",
    r"\bcafetiere\b", r"\bfrench press\b", r"\bmoka\b", r"\bcold brew\b",
    r"\bsuits?\b", r"\bworks? (for|with|as)\b", r"\bbrew method\b",
]

_PRICE_PATTERNS = [
    r"£\d+", r"\bunder\b.{0,10}£", r"\bbudget\b", r"\bcheapest\b",
    r"\bbest value\b", r"\baffordable\b", r"\bprice\b",
]

_ORIGIN_WORDS = {
    "ethiopia": "Ethiopia", "ethiopian": "Ethiopia",
    "kenya": "Kenya", "kenyan": "Kenya",
    "colombia": "Colombia", "colombian": "Colombia",
    "brazil": "Brazil", "brazilian": "Brazil",
    "guatemala": "Guatemala", "guatemalan": "Guatemala",
    "rwanda": "Rwanda", "rwandan": "Rwanda",
    "panama": "Panama", "burundi": "Burundi",
    "indonesia": "Indonesia", "peru": "Peru",
    "costa rica": "Costa Rica", "honduras": "Honduras",
    "el salvador": "El Salvador", "nicaragua": "Nicaragua",
    "bolivia": "Bolivia",
}

_PROCESS_WORDS = {
    "washed": "washed", "natural": "natural", "honey": "honey",
    "anaerobic": "anaerobic", "wet hulled": "wet_hulled",
    "carbonic": "carbonic_maceration",
}

_ROAST_WORDS = {
    "light": "light", "medium light": "medium_light", "medium": "medium",
    "medium dark": "medium_dark", "dark": "dark",
}

_BREW_METHOD_MAP = {
    "espresso": "espresso",
    "filter": "filter",
    "pour over": "filter",
    "v60": "filter",
    "aeropress": "filter",
    "cafetiere": "filter",
    "french press": "filter",
    "moka": "espresso",
}


def _extract_budget(text: str) -> float | None:
    m = re.search(r"£(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(pounds?|gbp)", text, re.I)
    if m:
        return float(m.group(1))
    return None


def _extract_origin(text: str) -> str | None:
    lower = text.lower()
    for word, country in _ORIGIN_WORDS.items():
        if word in lower:
            return country
    return None


def _extract_process(text: str) -> str | None:
    lower = text.lower()
    for raw, norm in _PROCESS_WORDS.items():
        if raw in lower:
            return norm
    return None


def _extract_roast(text: str) -> str | None:
    lower = text.lower()
    # Check two-word before one-word to avoid "medium" matching "medium light"
    if "medium light" in lower or "medium-light" in lower:
        return "medium_light"
    if "medium dark" in lower or "medium-dark" in lower:
        return "medium_dark"
    for raw, norm in _ROAST_WORDS.items():
        if raw in lower:
            return norm
    return None


def _extract_brew_method(text: str) -> str | None:
    lower = text.lower()
    for raw, method in _BREW_METHOD_MAP.items():
        if raw in lower:
            return method
    return None


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def classify(message: str) -> IntentResult:
    """
    Classify a user message into an intent and build a retrieval plan.
    Pure Python — no I/O, no async, no LLM.
    """
    text = message.strip()
    lower = text.lower()

    budget = _extract_budget(text)
    origin = _extract_origin(text)
    process = _extract_process(text)
    roast = _extract_roast(text)
    brew_method = _extract_brew_method(text)

    espresso_suitable = True if brew_method == "espresso" else None
    filter_suitable = True if brew_method == "filter" else None

    # ── Off-topic guard ────────────────────────────────────────────────────────
    off_topic_signals = [
        r"\b(weather|stock market|football|recipe|travel|hotel|flight)\b",
        r"\b(politics|news|sport|sports|movie|music|book)\b",
        r"\bworld cup\b", r"\bolympics?\b", r"\belection\b",
        r"\bpremier league\b", r"\b(nba|nfl|mlb)\b",
    ]
    if _matches_any(lower, off_topic_signals) and "coffee" not in lower:
        return IntentResult(intent="off_topic", confidence=0.9)

    # ── Compare ────────────────────────────────────────────────────────────────
    if _matches_any(lower, _COMPARE_PATTERNS):
        # Try to extract two coffee names from the message
        # Look for quoted strings or capitalised phrases
        names = re.findall(r'"([^"]+)"', text)
        if len(names) < 2:
            # Fall back to "X and Y" pattern
            m = re.search(r"between\s+(.+?)\s+and\s+(.+?)(?:\?|$)", text, re.I)
            if m:
                names = [m.group(1).strip(), m.group(2).strip()]

        if len(names) >= 2:
            return IntentResult(
                intent="compare",
                confidence=0.9,
                params={"name_a": names[0], "name_b": names[1]},
                retrieval_plan=[RetrievalCall(
                    tool="compare_coffees",
                    params={"name_a": names[0], "name_b": names[1]},
                )],
            )
        # Ambiguous compare — need both names
        return IntentResult(
            intent="compare",
            confidence=0.7,
            needs_llm_classification=True,
            params={"query": text},
            retrieval_plan=[RetrievalCall(
                tool="search_coffees",
                params={"query": text, "limit": 4},
            )],
        )

    # ── Explicit brew method beats a generic "recommend" trigger.
    #    e.g. "I brew filter coffee — what do you recommend?" → brew_advice,
    #    but "filter coffee under £14" still routes to price below.
    if brew_method and not budget and not _matches_any(lower, _PRICE_PATTERNS):
        return IntentResult(
            intent="brew_advice",
            confidence=0.85,
            params={"method": brew_method},
            retrieval_plan=[RetrievalCall(
                tool="find_by_brew_method",
                params={"method": brew_method, "limit": 5},
            )],
        )

    # ── Recommend / similar ────────────────────────────────────────────────────
    if _matches_any(lower, _RECOMMEND_PATTERNS):
        # Look for a coffee name after "liked" or "similar to"
        m = re.search(r"(?:liked|similar to|like)\s+([A-Z][^.,?!]{4,60})", text)
        name = m.group(1).strip() if m else None
        return IntentResult(
            intent="recommend",
            confidence=0.85 if name else 0.6,
            params={"seed_name": name, "query": text},
            retrieval_plan=[RetrievalCall(
                tool="search_coffees" if not name else "get_coffee_detail",
                params={"name_query": name} if name else {"query": text, "limit": 6},
            )],
        )

    # ── Price / budget ─────────────────────────────────────────────────────────
    if budget or _matches_any(lower, _PRICE_PATTERNS):
        params: dict = {
            "max_price_gbp": budget or 25.0,
            "weight_g": 250,
        }
        if espresso_suitable is not None:
            params["espresso_suitable"] = espresso_suitable
        if filter_suitable is not None:
            params["filter_suitable"] = filter_suitable
        return IntentResult(
            intent="price",
            confidence=0.9,
            params=params,
            retrieval_plan=[RetrievalCall(tool="find_by_price_range", params=params)],
        )

    # ── Brew method advice ─────────────────────────────────────────────────────
    if brew_method or _matches_any(lower, _BREW_PATTERNS):
        method = brew_method or ("espresso" if "espresso" in lower else "filter")
        return IntentResult(
            intent="brew_advice",
            confidence=0.85,
            params={"method": method},
            retrieval_plan=[RetrievalCall(
                tool="find_by_brew_method",
                params={"method": method, "limit": 5},
            )],
        )

    # ── General search with filters ────────────────────────────────────────────
    if any([origin, process, roast, "coffee" in lower, "bean" in lower]):
        search_params: dict = {"query": text, "limit": 6}
        if origin:
            search_params["origin_country"] = origin
        if process:
            search_params["process"] = process
        if roast:
            search_params["roast_level"] = roast
        if espresso_suitable is not None:
            search_params["espresso_suitable"] = espresso_suitable
        if filter_suitable is not None:
            search_params["filter_suitable"] = filter_suitable

        return IntentResult(
            intent="search",
            confidence=0.75,
            params=search_params,
            retrieval_plan=[RetrievalCall(tool="search_coffees", params=search_params)],
        )

    # ── General coffee education ───────────────────────────────────────────────
    return IntentResult(
        intent="general",
        confidence=0.5,
        params={"query": text},
        retrieval_plan=[RetrievalCall(
            tool="search_coffees",
            params={"query": text, "limit": 3},
        )],
    )
