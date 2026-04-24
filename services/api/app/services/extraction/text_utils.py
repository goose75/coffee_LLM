"""
Text mining utilities for coffee attribute extraction.

Used by both the schema.org parser (to mine descriptions) and the HTML
rules parser (to extract from text blocks). All functions accept raw
strings and return normalised values or empty defaults.

These are deliberately conservative — they only extract signals they're
confident about. Ambiguous text goes to the LLM fallback (Phase 6).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


# ─── HTML cleaning ─────────────────────────────────────────────────────────────

class _MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: list[str] = []
        self.convert_charrefs = True

    def handle_data(self, d: str) -> None:
        self.fed.append(d)

    def get_data(self) -> str:
        return " ".join(self.fed)


def clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities from a string."""
    if not raw:
        return ""
    s = _MLStripper()
    try:
        s.feed(raw)
        text = s.get_data()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


# ─── Origin country extraction ────────────────────────────────────────────────

_KNOWN_ORIGINS = [
    "Ethiopia", "Kenya", "Colombia", "Brazil", "Guatemala", "Costa Rica",
    "Honduras", "El Salvador", "Panama", "Peru", "Bolivia", "Mexico",
    "Nicaragua", "Rwanda", "Burundi", "Uganda", "Tanzania", "Malawi",
    "Zambia", "Zimbabwe", "DRC", "Congo", "Yemen", "India",
    "Indonesia", "Sumatra", "Sulawesi", "Timor", "Papua New Guinea",
    "Vietnam", "Myanmar", "China", "Thailand",
]

_ORIGIN_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _KNOWN_ORIGINS) + r")\b",
    re.IGNORECASE,
)


def extract_origin_country(text: str) -> str:
    """Return the first recognised origin country from text, or ''."""
    m = _ORIGIN_PATTERN.search(text)
    return m.group(1).title() if m else ""


# ─── Process extraction ───────────────────────────────────────────────────────

_PROCESS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bcarbonic\s+maceration\b", re.I), "Carbonic Maceration"),
    (re.compile(r"\banaerobic\s+natural\b", re.I), "Anaerobic Natural"),
    (re.compile(r"\banaerobic\s+washed\b", re.I), "Anaerobic Washed"),
    (re.compile(r"\banaerobic\b", re.I), "Anaerobic"),
    (re.compile(r"\bwet[- ]hulled?\b|\bgiling\s+basah\b", re.I), "Wet Hulled"),
    (re.compile(r"\bblack\s+honey\b", re.I), "Black Honey"),
    (re.compile(r"\bred\s+honey\b", re.I), "Red Honey"),
    (re.compile(r"\byellow\s+honey\b", re.I), "Yellow Honey"),
    (re.compile(r"\bhoney\s+process(?:ed)?\b|\bhoney\b", re.I), "Honey"),
    (re.compile(r"\bfully\s+washed\b|\bwet\s+process(?:ed)?\b", re.I), "Washed"),
    (re.compile(r"\bwashed\b", re.I), "Washed"),
    (re.compile(r"\bnatural\s+process(?:ed)?\b|\bdry\s+process(?:ed)?\b|\bsun.dried\b", re.I), "Natural"),
    (re.compile(r"\bnatural\b", re.I), "Natural"),
]


def extract_process(text: str) -> str:
    """Return the most specific process label found in text, or ''."""
    for pattern, label in _PROCESS_PATTERNS:
        if pattern.search(text):
            return label
    return ""


# ─── Roast level extraction ───────────────────────────────────────────────────

_ROAST_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bmedium[- ]dark\s*roast\b", re.I), "Medium Dark"),
    (re.compile(r"\bmedium[- ]light\s*roast\b", re.I), "Medium Light"),
    (re.compile(r"\blight\s*roast\b|\blightly\s+roasted\b", re.I), "Light"),
    (re.compile(r"\bmedium\s*roast\b", re.I), "Medium"),
    (re.compile(r"\bdark\s*roast\b", re.I), "Dark"),
    (re.compile(r"\bespresso\s*roast\b", re.I), "Medium Dark"),
    (re.compile(r"\bfilter\s*roast\b", re.I), "Light"),
    (re.compile(r"\bfull\s*city\+\b", re.I), "Medium Dark"),
    (re.compile(r"\bfull\s*city\b", re.I), "Medium"),
    (re.compile(r"\bcity\+\b", re.I), "Medium Light"),
    (re.compile(r"\bcity\s*roast\b", re.I), "Medium"),
]


def extract_roast_level(text: str) -> str:
    """Return the first roast level label found in text, or ''."""
    for pattern, label in _ROAST_PATTERNS:
        if pattern.search(text):
            return label
    return ""


# ─── Varietal extraction ──────────────────────────────────────────────────────

_KNOWN_VARIETALS = [
    # Ethiopian heirlooms
    "Heirloom", "74110", "74112", "JARC 74110",
    # Arabica cultivars
    "Bourbon", "Typica", "Caturra", "Catuai", "Mundo Novo",
    "Pacamara", "Pacas", "Maragogipe", "Geisha", "Gesha",
    "SL28", "SL34", "Ruiru 11", "Batian",
    # Castillo, Colombia
    "Castillo", "Colombia", "Tabi",
    # Hybrids
    "Catimor", "Sarchimor", "Marsellesa",
    # Indonesian
    "Linie S", "Onan Ganjang", "Tim Tim",
    # Specialty
    "Pink Bourbon", "Red Bourbon", "Yellow Bourbon", "Orange Bourbon",
    "Chiroso", "Sidra", "Sudan Rume",
]

_VARIETAL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in _KNOWN_VARIETALS) + r")\b",
    re.IGNORECASE,
)


def extract_varietal(text: str) -> list[str]:
    """Return all recognised varietal names found in text."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _VARIETAL_PATTERN.finditer(text):
        name = m.group(1)
        key = name.lower()
        if key not in seen:
            seen.add(key)
            # Normalise case: find canonical form
            canonical = next((v for v in _KNOWN_VARIETALS if v.lower() == key), name.title())
            found.append(canonical)
    return found


# ─── Flavour note extraction ──────────────────────────────────────────────────

_FLAVOUR_WORDS = [
    # Fruit
    "strawberry", "blueberry", "blackberry", "raspberry", "cherry", "red cherry",
    "black cherry", "peach", "apricot", "plum", "prune", "grape", "raisin",
    "lemon", "lime", "grapefruit", "orange", "bergamot", "mandarin", "tropical",
    "mango", "pineapple", "papaya", "passionfruit", "guava", "watermelon",
    "apple", "pear", "fig", "dates",
    # Chocolate & sweet
    "chocolate", "dark chocolate", "milk chocolate", "cocoa", "cacao",
    "caramel", "toffee", "butterscotch", "brown sugar", "molasses",
    "honey", "maple syrup", "vanilla", "candy", "sugar cane",
    # Floral
    "jasmine", "rose", "lavender", "hibiscus", "elderflower", "florals",
    # Nutty & spice
    "almond", "hazelnut", "walnut", "peanut", "pistachio",
    "cinnamon", "clove", "cardamom", "black pepper", "nutmeg",
    # Savoury & herbal
    "black tea", "green tea", "earl grey", "tobacco", "cedar", "oak",
    "tomato", "red wine", "whisky", "rum",
    # Generic descriptors kept (common in coffee tasting)
    "citrus", "stone fruit", "red fruit", "dark fruit", "dried fruit",
    "stone", "floral", "herbal", "spice", "earthy", "smoky",
    "bright", "juicy", "clean", "complex", "balanced",
]

_FLAVOUR_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(f) for f in _FLAVOUR_WORDS) + r")\b",
    re.IGNORECASE,
)

# "tasting notes: X, Y and Z" pattern
_TASTING_NOTES_SECTION = re.compile(
    r"tasting\s+notes?:?\s*([^.;\n]{5,120})",
    re.IGNORECASE,
)
_FLAVOUR_PREFIX = re.compile(
    r"(?:notes?\s+of|hints?\s+of|flavours?\s+of|aromas?\s+of|taste[sd]?\s+of)\s*:?\s*([^.;\n]{3,100})",
    re.IGNORECASE,
)


def extract_flavour_notes(text: str) -> list[str]:
    """
    Extract flavour notes from text.

    Strategy:
    1. Look for "tasting notes: X, Y and Z" section and parse the list.
    2. Scan full text for known flavour words.
    Returns deduplicated, title-cased list.
    """
    notes: list[str] = []
    seen: set[str] = set()

    def _add(word: str) -> None:
        key = word.lower().strip()
        if key and key not in seen:
            seen.add(key)
            notes.append(word.strip().title())

    # Priority: tasting notes section
    for section_match in list(_TASTING_NOTES_SECTION.finditer(text)) + list(_FLAVOUR_PREFIX.finditer(text)):
        section = section_match.group(1)
        # Split on commas, "and", "&"
        parts = re.split(r",\s*|\s+and\s+|\s*&\s*", section)
        for part in parts:
            part = part.strip().rstrip(".")
            if 2 < len(part) < 40:
                _add(part)

    # Scan full text for known words (don't duplicate what section already found)
    for m in _FLAVOUR_PATTERN.finditer(text):
        _add(m.group(1))

    return notes[:12]  # Cap at 12 — longer lists are usually noise


# ─── Weight extraction ────────────────────────────────────────────────────────

_WEIGHT_G_RE = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE)
_WEIGHT_KG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*kg\b", re.IGNORECASE)


def extract_weight_g(text: str) -> int | None:
    """Extract weight in grams from text. Returns None if not found."""
    m = _WEIGHT_G_RE.search(text)
    if m:
        return int(float(m.group(1)))
    m = _WEIGHT_KG_RE.search(text)
    if m:
        return int(float(m.group(1)) * 1000)
    return None


# ─── Price extraction ─────────────────────────────────────────────────────────

_PRICE_RE = re.compile(r"£\s*(\d+(?:\.\d{1,2})?)")


def extract_price_gbp(text: str) -> float | None:
    """Extract first GBP price from text."""
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None
