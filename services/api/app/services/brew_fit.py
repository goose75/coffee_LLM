"""
brew_fit.py — Brew suitability scoring for coffee.

Six brew methods scored on a 0–100 scale using structured coffee attributes.
Scores are derived from known coffee science — not arbitrary weights.

Methods scored:
  espresso      — high extraction, concentrated, needs sweetness/body to balance
  filter        — V60 / Kalita / Chemex — rewards clarity, delicacy, floral/fruit
  aeropress     — forgiving, works across body levels, favours complexity
  immersion     — French press / Clever — rewards body, tolerates rougher textures
  milk_drinks   — flat white / latte — needs body and sweetness to cut through milk
  cold_brew     — slow cold extraction — rewards sweetness, low acid, full body

Each method score is a weighted sum of:
  - roast contribution
  - process contribution
  - altitude contribution
  - flavour note signals
  - origin tendency
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Method metadata ───────────────────────────────────────────────────────────

@dataclass
class BrewMethod:
    key: str
    label: str
    icon: str
    description: str   # one-line what it is
    ideal_profile: str # what kind of coffee thrives here


BREW_METHODS = [
    BrewMethod("espresso",    "Espresso",     "☕", "High-pressure extraction, concentrated",    "Full body, sweetness, roast caramel"),
    BrewMethod("filter",      "Filter / V60", "🫗", "Pour-over, gravity-fed, high clarity",       "Bright acidity, floral, fruit-forward"),
    BrewMethod("aeropress",   "AeroPress",    "🔧", "Immersion + pressure, versatile",            "Complex flavours, medium body"),
    BrewMethod("immersion",   "French Press", "🧊", "Full immersion, unfiltered, heavy body",     "Earthy, full body, lower acidity"),
    BrewMethod("milk_drinks", "Milk Drinks",  "🥛", "Flat white, latte, needs body",              "Dark-ish roast, sweetness, chocolate"),
    BrewMethod("cold_brew",   "Cold Brew",    "🧊", "12–24h cold extraction, smooth and sweet",  "Naturally sweet, low acid, full body"),
]


# ── Scoring tables ────────────────────────────────────────────────────────────

# Roast level → method affinity (0-40 points)
ROAST_SCORES: dict[str, dict[str, int]] = {
    "light": {
        "espresso": 10, "filter": 38, "aeropress": 30,
        "immersion": 15, "milk_drinks": 5,  "cold_brew": 20,
    },
    "medium_light": {
        "espresso": 20, "filter": 32, "aeropress": 34,
        "immersion": 22, "milk_drinks": 15, "cold_brew": 25,
    },
    "medium": {
        "espresso": 32, "filter": 24, "aeropress": 35,
        "immersion": 28, "milk_drinks": 28, "cold_brew": 30,
    },
    "medium_dark": {
        "espresso": 38, "filter": 14, "aeropress": 28,
        "immersion": 35, "milk_drinks": 36, "cold_brew": 34,
    },
    "dark": {
        "espresso": 40, "filter": 6,  "aeropress": 22,
        "immersion": 38, "milk_drinks": 40, "cold_brew": 36,
    },
}

# Process → method affinity (0-25 points)
PROCESS_SCORES: dict[str, dict[str, int]] = {
    "washed": {
        "espresso": 16, "filter": 25, "aeropress": 20,
        "immersion": 14, "milk_drinks": 12, "cold_brew": 16,
    },
    "natural": {
        "espresso": 22, "filter": 16, "aeropress": 22,
        "immersion": 22, "milk_drinks": 20, "cold_brew": 22,
    },
    "honey": {
        "espresso": 20, "filter": 18, "aeropress": 22,
        "immersion": 18, "milk_drinks": 20, "cold_brew": 20,
    },
    "anaerobic": {
        "espresso": 18, "filter": 14, "aeropress": 25,
        "immersion": 16, "milk_drinks": 14, "cold_brew": 18,
    },
    "wet_hulled": {
        "espresso": 20, "filter": 10, "aeropress": 18,
        "immersion": 25, "milk_drinks": 22, "cold_brew": 20,
    },
    "carbonic_maceration": {
        "espresso": 16, "filter": 12, "aeropress": 22,
        "immersion": 14, "milk_drinks": 12, "cold_brew": 16,
    },
}

# Flavour note signals → method boosts (additive, capped at 20 points total)
FLAVOUR_SIGNALS: dict[str, dict[str, int]] = {
    # Floral → filter
    "floral": {"filter": 8, "aeropress": 4},
    "jasmine": {"filter": 8, "aeropress": 4},
    "rose": {"filter": 7, "aeropress": 3},
    "elderflower": {"filter": 7},
    # Citrus → filter/aeropress
    "citrus": {"filter": 6, "aeropress": 4},
    "lemon": {"filter": 6, "aeropress": 4},
    "bergamot": {"filter": 7, "aeropress": 4},
    "grapefruit": {"filter": 5, "aeropress": 3},
    # Berry/fruit → filter/aeropress/espresso
    "berry": {"filter": 5, "aeropress": 5, "espresso": 3},
    "cherry": {"filter": 4, "aeropress": 5, "espresso": 4},
    "blueberry": {"filter": 5, "aeropress": 5},
    "raspberry": {"filter": 5, "aeropress": 4},
    "strawberry": {"filter": 4, "aeropress": 4},
    "blackcurrant": {"filter": 5, "aeropress": 4, "espresso": 3},
    "peach": {"filter": 5, "aeropress": 4},
    "apricot": {"filter": 4, "aeropress": 4},
    "mango": {"filter": 3, "aeropress": 5, "cold_brew": 4},
    "tropical": {"filter": 4, "aeropress": 5, "cold_brew": 4},
    # Chocolate/sweet → espresso/milk/immersion/cold brew
    "chocolate": {"espresso": 7, "milk_drinks": 8, "immersion": 5, "cold_brew": 6},
    "dark chocolate": {"espresso": 8, "milk_drinks": 9, "immersion": 5},
    "milk chocolate": {"espresso": 6, "milk_drinks": 8, "cold_brew": 5},
    "cocoa": {"espresso": 7, "milk_drinks": 7, "cold_brew": 5},
    "caramel": {"espresso": 6, "milk_drinks": 7, "cold_brew": 7},
    "toffee": {"espresso": 5, "milk_drinks": 7, "cold_brew": 6},
    "maple syrup": {"espresso": 4, "cold_brew": 8},
    "honey": {"espresso": 4, "filter": 3, "cold_brew": 6},
    "vanilla": {"milk_drinks": 6, "cold_brew": 7},
    # Nutty → espresso/milk/immersion
    "nutty": {"espresso": 5, "milk_drinks": 6, "immersion": 5},
    "almond": {"espresso": 5, "milk_drinks": 5, "cold_brew": 4},
    "hazelnut": {"espresso": 6, "milk_drinks": 7, "cold_brew": 4},
    # Earthy/wine → immersion/espresso
    "earthy": {"immersion": 7, "espresso": 4},
    "tobacco": {"immersion": 6, "espresso": 4},
    "wine": {"espresso": 5, "aeropress": 4},
    "fermented": {"aeropress": 6, "espresso": 4},
    # Tea-like → filter
    "tea": {"filter": 8, "aeropress": 5},
    "tea-like": {"filter": 8, "aeropress": 5},
    "green tea": {"filter": 7},
    # Spice → espresso/aeropress
    "spice": {"espresso": 5, "aeropress": 5},
    "cinnamon": {"espresso": 4, "milk_drinks": 4},
}

# Origin tendency boosts (0-10 points)
ORIGIN_SCORES: dict[str, dict[str, int]] = {
    "Ethiopia": {"filter": 8, "aeropress": 5},
    "Kenya": {"filter": 7, "aeropress": 5, "espresso": 3},
    "Colombia": {"filter": 5, "espresso": 5, "aeropress": 5},
    "Brazil": {"espresso": 8, "milk_drinks": 7, "cold_brew": 6, "immersion": 5},
    "Guatemala": {"espresso": 5, "filter": 4, "aeropress": 5},
    "Rwanda": {"filter": 7, "aeropress": 5},
    "Panama": {"filter": 8, "aeropress": 6},
    "Indonesia": {"immersion": 8, "espresso": 5, "cold_brew": 6},
    "India": {"espresso": 5, "milk_drinks": 6, "immersion": 5},
    "Yemen": {"espresso": 6, "aeropress": 6, "immersion": 5},
    "Honduras": {"filter": 4, "espresso": 5, "aeropress": 4},
    "Peru": {"filter": 5, "aeropress": 4},
    "Burundi": {"filter": 7, "aeropress": 5},
    "Tanzania": {"filter": 6, "espresso": 4, "aeropress": 5},
}

# Altitude boost (high altitude → filter/aeropress)
def _altitude_boost(alt_min: int | None, alt_max: int | None) -> dict[str, int]:
    avg = None
    if alt_min and alt_max:
        avg = (alt_min + alt_max) / 2
    elif alt_min:
        avg = alt_min
    elif alt_max:
        avg = alt_max
    if avg is None:
        return {}
    if avg >= 1800:
        return {"filter": 8, "aeropress": 5}
    elif avg >= 1500:
        return {"filter": 5, "aeropress": 3}
    elif avg >= 1200:
        return {"filter": 2}
    return {}


# ── Main scoring function ─────────────────────────────────────────────────────

@dataclass
class BrewScore:
    method: str
    label: str
    icon: str
    score: int              # 0-100
    tier: str               # "excellent" | "good" | "works" | "possible" | "avoid"
    reasons: list[str]      # grounded explanations
    short_reason: str       # single sentence


def score_brew_fit(
    roast_level: str | None,
    process: str | None,
    flavour_notes: list[str],
    origin_country: str | None,
    altitude_min: int | None,
    altitude_max: int | None,
    espresso_flag: bool = False,
    filter_flag: bool = False,
) -> list[BrewScore]:
    """
    Score all 6 brew methods for a coffee. Returns sorted list highest→lowest.
    """
    method_map = {m.key: m for m in BREW_METHODS}
    scores: dict[str, int] = {m.key: 0 for m in BREW_METHODS}
    reasons: dict[str, list[str]] = {m.key: [] for m in BREW_METHODS}

    roast = (roast_level or "medium").lower().replace(" ", "_")
    proc = (process or "washed").lower().replace(" ", "_").replace("-", "_")
    notes_lower = [n.lower() for n in (flavour_notes or [])]
    origin = origin_country or ""

    # 1. Roast contribution (max 40)
    roast_contrib = ROAST_SCORES.get(roast, ROAST_SCORES["medium"])
    for method, pts in roast_contrib.items():
        scores[method] += pts
        if pts >= 30:
            roast_label = roast.replace("_", " ")
            reasons[method].append(f"{roast_label} roast suits this method")

    # 2. Process contribution (max 25)
    proc_contrib = PROCESS_SCORES.get(proc, PROCESS_SCORES["washed"])
    for method, pts in proc_contrib.items():
        scores[method] += pts
        if pts >= 20:
            reasons[method].append(f"{proc} process adds character here")

    # 3. Flavour note signals (capped at 20 per method)
    flavour_added: dict[str, int] = {m.key: 0 for m in BREW_METHODS}
    matched_notes: dict[str, list[str]] = {m.key: [] for m in BREW_METHODS}

    for note in notes_lower:
        for signal_key, boosts in FLAVOUR_SIGNALS.items():
            if signal_key in note or note in signal_key:
                for method, pts in boosts.items():
                    if flavour_added[method] < 20:
                        add = min(pts, 20 - flavour_added[method])
                        scores[method] += add
                        flavour_added[method] += add
                        matched_notes[method].append(note)

    for method, notes in matched_notes.items():
        if notes:
            unique = list(dict.fromkeys(notes))[:3]
            reasons[method].append(f"{', '.join(unique)} notes work well here")

    # 4. Origin tendency (max 10)
    origin_contrib = ORIGIN_SCORES.get(origin, {})
    for method, pts in origin_contrib.items():
        scores[method] += pts
        if pts >= 7:
            reasons[method].append(f"{origin} coffees often excel here")

    # 5. Altitude (max 8)
    alt_contrib = _altitude_boost(altitude_min, altitude_max)
    for method, pts in alt_contrib.items():
        scores[method] += pts
        if pts >= 5 and altitude_min:
            reasons[method].append(f"high altitude ({altitude_min}m+) adds clarity")

    # Normalise to 0-100
    max_possible = 40 + 25 + 20 + 10 + 8  # = 103, close enough
    result: list[BrewScore] = []
    for m in BREW_METHODS:
        raw = scores[m.key]
        normalised = min(100, round(raw / max_possible * 100))

        # 6. Flags applied after normalisation — ensure minimum floor
        if m.key == "espresso" and espresso_flag:
            normalised = max(normalised, 55)
        if m.key == "filter" and filter_flag:
            normalised = max(normalised, 55)
        tier = _tier(normalised)
        short = _short_reason(m.key, tier, roast, proc, origin, notes_lower)
        result.append(BrewScore(
            method=m.key,
            label=m.label,
            icon=m.icon,
            score=normalised,
            tier=tier,
            reasons=list(dict.fromkeys(reasons[m.key]))[:3],
            short_reason=short,
        ))

    result.sort(key=lambda x: -x.score)
    return result


def _tier(score: int) -> str:
    if score >= 75: return "excellent"
    if score >= 58: return "good"
    if score >= 42: return "works"
    if score >= 25: return "possible"
    return "avoid"


def _short_reason(method: str, tier: str, roast: str, process: str,
                   origin: str, notes: list[str]) -> str:
    """Generate a single grounded sentence for each method."""
    roast_label = roast.replace("_", " ")

    if tier == "avoid":
        avoid_reasons = {
            "espresso": f"light roast with high acidity can taste sharp and thin under pressure",
            "filter": f"dark roast loses delicate aromatics that filter brewing rewards",
            "immersion": f"light roast can taste thin and underdeveloped in full immersion",
            "milk_drinks": f"delicate floral notes will be overwhelmed by milk",
            "cold_brew": f"high acidity can become harsh over long cold extraction",
            "aeropress": f"may work but won\'t show its best here",
        }
        return avoid_reasons.get(method, "not recommended for this coffee")

    has_floral = any(n in notes for n in ["jasmine", "floral", "rose", "elderflower"])
    has_chocolate = any(n in notes for n in ["chocolate", "cocoa", "caramel", "toffee"])
    has_fruit = any(n in notes for n in ["berry", "cherry", "citrus", "peach", "mango"])
    has_tea = any(n in notes for n in ["tea", "tea-like", "green tea"])

    if method == "filter":
        if has_floral: return f"floral notes and {roast_label} roast shine in a clean pour-over"
        if has_tea: return f"tea-like character is best expressed through a clean filter brew"
        if has_fruit: return f"fruity clarity comes through beautifully in filter brewing"
        return f"{roast_label} roast with {process} process brews a clean, expressive filter cup"

    if method == "espresso":
        if has_chocolate: return f"chocolate and sweetness pull together under espresso pressure"
        if has_fruit: return f"expect a fruit-forward, brighter-than-usual espresso shot"
        return f"{roast_label} roast{(' from ' + origin) if origin else ''} produces a well-structured espresso"

    if method == "aeropress":
        return f"AeroPress versatility lets you tune the extraction to highlight the best of this coffee"

    if method == "milk_drinks":
        if has_chocolate: return f"chocolate and body cut through milk cleanly for a rounded flat white"
        return f"works in milk drinks — the sweetness holds its own"

    if method == "immersion":
        return f"full immersion amplifies body and rounds out the texture"

    if method == "cold_brew":
        if has_chocolate: return f"chocolate sweetness concentrates beautifully over cold extraction"
        return f"smooth and sweet over ice — worth trying cold"

    return f"suitable for this brew method"
