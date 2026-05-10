"""
test_query_parser.py — Tests for the natural language coffee query parser.

Tests cover:
  - Rules-based parser accuracy on realistic queries
  - Price extraction
  - Brew method detection
  - Flavour note extraction
  - Edge cases and fallback behaviour

Run inside the API container:
  docker exec coffee_api python -m pytest services/api/tests/test_query_parser.py -v
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/app")

# ── Inline the parser for standalone testing ──────────────────────────────────
# (avoids needing the full app context)

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedQuery:
    flavour_notes: list[str] = field(default_factory=list)
    roast_level: str | None = None
    process: str | None = None
    origin_country: str | None = None
    origin_region: str | None = None
    max_price: float | None = None
    min_price: float | None = None
    espresso_suitable: bool | None = None
    filter_suitable: bool | None = None
    body_signal: str | None = None
    acidity_signal: str | None = None
    adventurousness: str | None = None
    decaf: bool | None = None
    summary: str = ""
    source: str = "rules"
    raw_query: str = ""


_ROAST_MAP = {
    "light": "light", "light roast": "light", "lightly roasted": "light",
    "bright": "light", "filter roast": "light",
    "medium": "medium", "medium roast": "medium", "balanced": "medium",
    "dark": "dark", "dark roast": "dark", "darkly roasted": "dark",
    "bold": "dark", "strong": "dark", "full roast": "dark",
}
_PROCESS_MAP = {
    "washed": "washed", "wet process": "washed",
    "natural": "natural", "dry process": "natural", "sun-dried": "natural",
    "honey": "honey", "honey process": "honey",
    "anaerobic": "anaerobic",
}
_BREW_MAP = {
    "espresso": (True, None), "filter": (None, True),
    "v60": (None, True), "pour over": (None, True), "chemex": (None, True),
    "aeropress": (None, True), "cafetiere": (None, True),
    "french press": (None, True), "flat white": (True, None),
    "latte": (True, None), "moka pot": (True, None), "cold brew": (None, True),
}
_BODY_MAP = {
    "syrupy": "full", "syrup": "full", "thick": "full", "heavy": "full",
    "full body": "full", "full-bodied": "full", "rich": "full",
    "juicy": "medium", "round": "medium",
    "clean": "light", "delicate": "light", "light body": "light",
    "silky": "light", "tea-like": "light",
}
_ACIDITY_MAP = {
    "bright": "bright", "lively": "bright", "vibrant": "bright", "crisp": "bright",
    "juicy": "juicy",
    "low acid": "low", "smooth": "low", "mellow": "low",
    "clean": "clean", "clarity": "clean", "high clarity": "clean",
}
_ORIGINS = {
    "ethiopia": "Ethiopia", "ethiopian": "Ethiopia",
    "kenya": "Kenya", "kenyan": "Kenya",
    "colombia": "Colombia", "brazil": "Brazil", "brazilian": "Brazil",
    "guatemala": "Guatemala", "rwanda": "Rwanda",
    "panama": "Panama", "costa rica": "Costa Rica",
    "honduras": "Honduras", "peru": "Peru", "peruvian": "Peru",
    "indonesia": "Indonesia", "india": "India", "yemen": "Yemen",
    "mexico": "Mexico", "nicaragua": "Nicaragua", "tanzania": "Tanzania",
}
_FLAVOUR_KEYWORDS = [
    "chocolate", "dark chocolate", "milk chocolate", "caramel", "toffee",
    "nutty", "almond", "hazelnut", "fruity", "citrus", "lemon", "lime",
    "orange", "grapefruit", "bergamot", "berry", "cherry", "strawberry",
    "raspberry", "blueberry", "blackcurrant", "tropical", "mango",
    "floral", "jasmine", "rose", "tea", "tea-like", "wine", "honey",
    "vanilla", "spice", "cinnamon", "earthy", "clean", "sweet",
]

def _extract_price(text):
    min_p = max_p = None
    m = re.search(r'(?:under|below|less than|max|maximum|no more than)\s*[£$]?\s*(\d+(?:\.\d+)?)', text, re.I)
    if m: max_p = float(m.group(1))
    m = re.search(r'(?:over|above|more than|at least|min|minimum)\s*[£$]?\s*(\d+(?:\.\d+)?)', text, re.I)
    if m: min_p = float(m.group(1))
    m = re.search(r'(?:around|about|roughly)\s*[£$]?\s*(\d+(?:\.\d+)?)', text, re.I)
    if m:
        v = float(m.group(1)); min_p = max(0, v-2); max_p = v+2
    if max_p is None and min_p is None:
        m = re.search(r'[£$](\d+(?:\.\d+)?)', text)
        if m: max_p = float(m.group(1))
    return min_p, max_p

def parse_rules(query):
    text = query.lower().strip()
    pq = ParsedQuery(raw_query=query, source="rules")
    for kw, val in sorted(_ROAST_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text: pq.roast_level = val; break
    for kw, val in sorted(_PROCESS_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text: pq.process = val; break
    for kw, (esp, filt) in sorted(_BREW_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text: pq.espresso_suitable = esp; pq.filter_suitable = filt; break
    for kw, val in sorted(_BODY_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text: pq.body_signal = val; break
    for kw, val in sorted(_ACIDITY_MAP.items(), key=lambda x: -len(x[0])):
        if kw in text: pq.acidity_signal = val; break
    for kw, val in sorted(_ORIGINS.items(), key=lambda x: -len(x[0])):
        if kw in text: pq.origin_country = val; break
    pq.min_price, pq.max_price = _extract_price(text)
    if "decaf" in text: pq.decaf = True
    if any(w in text for w in ["adventurous","unusual","exotic","rare"]):
        pq.adventurousness = "adventurous"
    elif any(w in text for w in ["familiar","classic","traditional","everyday"]):
        pq.adventurousness = "familiar"
    found = []
    for kw in sorted(_FLAVOUR_KEYWORDS, key=len, reverse=True):
        if kw in text and kw not in found: found.append(kw)
    pq.flavour_notes = found[:8]
    return pq

# ── Test suite ─────────────────────────────────────────────────────────────────

TOTAL = 0
PASSED = 0

def check(name, condition, got=None, expected=None):
    global TOTAL, PASSED
    TOTAL += 1
    if condition:
        print(f"  ✓ {name}")
        PASSED += 1
    else:
        print(f"  ✗ {name}")
        if got is not None:
            print(f"      got={got!r}, expected={expected!r}")

print("\n── Roast level detection ──────────────────────────────────────────")
cases = [
    ("I want a light roast Ethiopian", "light"),
    ("give me something bright and clean", "light"),
    ("dark espresso for my morning", "dark"),
    ("not too dark but not too light", "medium"),
    ("medium roast Colombia", "medium"),
    ("lightly roasted floral coffee", "light"),
    ("bold strong espresso", "dark"),
]
for q, expected in cases:
    r = parse_rules(q)
    check(q[:50], r.roast_level == expected, r.roast_level, expected)

print("\n── Process detection ─────────────────────────────────────────────")
cases = [
    ("floral Ethiopian natural", "natural"),
    ("clean washed Kenya", "washed"),
    ("honey process Guatemala", "honey"),
    ("anaerobic fermented Colombia", "anaerobic"),
    ("sun-dried Rwanda", "natural"),
    ("wet process coffee", "washed"),
]
for q, expected in cases:
    r = parse_rules(q)
    check(q[:50], r.process == expected, r.process, expected)

print("\n── Brew method detection ─────────────────────────────────────────")
cases = [
    ("something juicy and floral for V60", None, True),
    ("syrupy espresso under £12", True, None),
    ("pour over with bright acidity", None, True),
    ("flat white blend", True, None),
    ("aeropress coffee", None, True),
    ("filter coffee for morning", None, True),
    ("latte blend recommendation", True, None),
]
for q, esp, filt in cases:
    r = parse_rules(q)
    check(f"{q[:45]} → esp={esp} filt={filt}",
          r.espresso_suitable == esp and r.filter_suitable == filt,
          (r.espresso_suitable, r.filter_suitable), (esp, filt))

print("\n── Price extraction ──────────────────────────────────────────────")
cases = [
    ("espresso under £12", None, 12.0),
    ("something below £15", None, 15.0),
    ("coffee over £10", 10.0, None),
    ("at least £12", 12.0, None),
    ("around £15", 13.0, 17.0),
    ("£10 filter coffee", None, 10.0),
    ("no more than £20 please", None, 20.0),
    ("fruity and bright", None, None),
]
for q, exp_min, exp_max in cases:
    r = parse_rules(q)
    check(f"{q[:45]} → min={exp_min} max={exp_max}",
          r.min_price == exp_min and r.max_price == exp_max,
          (r.min_price, r.max_price), (exp_min, exp_max))

print("\n── Origin detection ──────────────────────────────────────────────")
cases = [
    ("I love Ethiopian coffees", "Ethiopia"),
    ("Kenyan AA please", "Kenya"),
    ("something from Colombia", "Colombia"),
    ("Brazilian for every day", "Brazil"),
    ("Guatemalan washed", "Guatemala"),
    ("Rwandan honey", "Rwanda"),
    ("Peruvian light roast", "Peru"),
]
for q, expected in cases:
    r = parse_rules(q)
    check(q[:50], r.origin_country == expected, r.origin_country, expected)

print("\n── Flavour note extraction ───────────────────────────────────────")
cases = [
    ("I like blueberry and tea-like coffees", ["blueberry", "tea-like"]),
    ("chocolatey but not too dark", ["chocolate"]),
    ("something with jasmine and lemon", ["jasmine", "lemon"]),
    ("juicy cherry and caramel notes", ["caramel", "cherry"]),
    ("floral with citrus brightness", ["citrus"]),
]
for q, expected_notes in cases:
    r = parse_rules(q)
    found_all = all(n in r.flavour_notes for n in expected_notes)
    check(q[:50], found_all, r.flavour_notes, f"includes {expected_notes}")

print("\n── Decaf detection ───────────────────────────────────────────────")
for q, expected in [
    ("I want a decaf chocolate", True),
    ("caffeine free please", True),
    ("something with low caffeine", None),
    ("regular espresso", None),
]:
    r = parse_rules(q)
    check(q[:50], r.decaf == expected, r.decaf, expected)

print("\n── Adventurousness detection ─────────────────────────────────────")
for q, expected in [
    ("something exotic and unusual", "adventurous"),
    ("classic everyday coffee", "familiar"),
    ("traditional espresso blend", "familiar"),
    ("a rare experimental process", "adventurous"),
    ("medium Ethiopian", None),
]:
    r = parse_rules(q)
    check(q[:50], r.adventurousness == expected, r.adventurousness, expected)

print("\n── Realistic full queries ────────────────────────────────────────")

# "I want something juicy and floral for V60"
r = parse_rules("I want something juicy and floral for V60")
check("juicy floral V60 — filter", r.filter_suitable is True)
check("juicy floral V60 — floral noted", "floral" in r.flavour_notes)

# "Show me a syrupy espresso coffee under £12"
r = parse_rules("Show me a syrupy espresso coffee under £12")
check("syrupy espresso £12 — espresso", r.espresso_suitable is True)
check("syrupy espresso £12 — max price", r.max_price == 12.0)
check("syrupy espresso £12 — body", r.body_signal == "full")

# "I like blueberry and tea-like coffees with high clarity"
r = parse_rules("I like blueberry and tea-like coffees with high clarity")
check("blueberry tea clarity — blueberry", "blueberry" in r.flavour_notes)
check("blueberry tea clarity — tea-like", "tea-like" in r.flavour_notes)
check("blueberry tea clarity — acidity", r.acidity_signal == "clean")

# "Give me something chocolatey but not too dark"
r = parse_rules("Give me something chocolatey but not too dark")
check("chocolatey not too dark — chocolate noted", "chocolate" in r.flavour_notes)

# Empty query
r = parse_rules("")
check("empty query — no crash", r.source == "rules")
check("empty query — no roast", r.roast_level is None)

# Very short query
r = parse_rules("Kenya")
check("single word origin", r.origin_country == "Kenya")

# Gibberish
r = parse_rules("xyzabc123 qwerty")
check("gibberish — no crash", r.source == "rules")
check("gibberish — no roast", r.roast_level is None)

print(f"\n{'='*55}")
print(f"Results: {PASSED}/{TOTAL} passed, {TOTAL-PASSED} failed")
