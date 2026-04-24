"""
Built-in normalisation rules.

This module contains the hard-coded pattern tables that power the rule-based
normaliser. The rules here are the fallback when the DB-backed
NormalisationMapping table has no entry for a given raw value.

Design decisions:
  - Patterns are tried most-specific first (longer/more-specific patterns first).
  - All matching is case-insensitive.
  - Every vocabulary type has an explicit "unknown" fallback.
  - Country and region tables are ISO-3166 based but extended with common
    coffee-industry informal names (e.g. "Kona" → country="United States").

Vocabulary sources:
  - Roast: SCAA roast colour scale + common UK/European roaster terminology
  - Grind: standard brew method taxonomy
  - Process: WCR/SCA process definitions
  - Country: ISO 3166-1 alpha-2 extended with coffee industry names
  - Region: major growing regions per country
  - Weight: SI + Imperial conventions used by UK sellers
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """A single normalisation rule: pattern + canonical value."""
    pattern: re.Pattern
    value: str


def _rule(raw: str, value: str, flags: int = re.IGNORECASE) -> Rule:
    return Rule(pattern=re.compile(raw, flags), value=value)


# ─── Roast level rules ────────────────────────────────────────────────────────
# Ordered most-specific first to avoid "medium" matching "medium-dark"

ROAST_RULES: list[Rule] = [
    _rule(r"\bmedium[\s\-]dark\b", "medium_dark"),
    _rule(r"\bmedium[\s\-]light\b", "medium_light"),
    _rule(r"\bfull[\s\-]city\+\b", "medium_dark"),
    _rule(r"\bfull[\s\-]city\b", "medium_dark"),
    _rule(r"\bcity\+\b", "medium_light"),
    _rule(r"\bcity[\s\-]roast\b", "medium"),
    _rule(r"\blight[\s\-]?(?:roast|roasted|filter)?\b", "light"),
    _rule(r"\bfilter[\s\-]roast\b", "light"),
    _rule(r"\bblonde\b", "light"),
    _rule(r"\b(?:nordic|scandinavian|filter|modern)\s*roast\b", "light"),
    _rule(r"\bespresso[\s\-]roast\b", "medium_dark"),
    _rule(r"\b(?:italian|french)\s*roast\b", "dark"),
    _rule(r"\bvienna[\s\-]roast\b", "medium_dark"),
    _rule(r"\bmedium[\s\-]?roast\b", "medium"),
    _rule(r"\bdark[\s\-]?roast\b", "dark"),
    _rule(r"\bmedium\b", "medium"),
    _rule(r"\bdark\b", "dark"),
    _rule(r"\blight\b", "light"),
]

# ─── Grind type rules ─────────────────────────────────────────────────────────

GRIND_RULES: list[Rule] = [
    _rule(r"\bwhole[\s\-]?beans?\b", "whole_bean"),
    _rule(r"\bunground\b", "whole_bean"),
    _rule(r"\bun[\s\-]?ground\b", "whole_bean"),
    _rule(r"\bpour[\s\-]?over\b", "pour_over"),
    _rule(r"\bv[\s\-]?60\b", "pour_over"),
    _rule(r"\bchem[\s\-]?ex\b", "pour_over"),
    _rule(r"\bcold[\s\-]brew\b", "filter"),        # coarse grind like filter
    _rule(r"\baero[\s\-]?press\b", "aeropress"),
    _rule(r"\bcafeti[eè]re\b", "cafetiere"),
    _rule(r"\bfrench[\s\-]?press\b", "cafetiere"),
    _rule(r"\bplunger\b", "cafetiere"),
    _rule(r"\bmoka[\s\-]?pot\b", "moka"),
    _rule(r"\bstovetop\b", "moka"),
    _rule(r"\bomni[\s\-]?grind\b", "omni"),
    _rule(r"\ball[\s\-](?:brew[\s\-])?methods?\b", "omni"),
    _rule(r"\bomni\b", "omni"),
    _rule(r"\bfilter\b", "filter"),
    _rule(r"\bdrip\b", "filter"),
    _rule(r"\bespresso\b", "espresso"),
    _rule(r"\bfine[\s\-]?grind\b", "espresso"),
    _rule(r"\bbeans?\b", "whole_bean"),  # bare "beans" = whole bean
]

# ─── Process rules ────────────────────────────────────────────────────────────
# More-specific compound patterns before single-word ones

PROCESS_RULES: list[Rule] = [
    _rule(r"\bcarbonic[\s\-]?maceration\b", "carbonic_maceration"),
    _rule(r"\bco2[\s\-]?maceration\b", "carbonic_maceration"),
    _rule(r"\bdouble[\s\-]?anaerobic\b", "anaerobic"),
    _rule(r"\banaerobic[\s\-]?natural\b", "anaerobic"),
    _rule(r"\banaerobic[\s\-]?washed\b", "anaerobic"),
    _rule(r"\banaerobic\b", "anaerobic"),
    _rule(r"\bwet[\s\-]?hulled?\b", "wet_hulled"),
    _rule(r"\bgiling[\s\-]?basah\b", "wet_hulled"),
    _rule(r"\bblack[\s\-]?honey\b", "honey"),
    _rule(r"\bred[\s\-]?honey\b", "honey"),
    _rule(r"\byellow[\s\-]?honey\b", "honey"),
    _rule(r"\bhoney\b", "honey"),
    _rule(r"\bfully[\s\-]?washed\b", "washed"),
    _rule(r"\bwet[\s\-]?process(?:ed)?\b", "washed"),
    _rule(r"\bwashed\b", "washed"),
    _rule(r"\bnatural[\s\-]?process(?:ed)?\b", "natural"),
    _rule(r"\bdry[\s\-]?process(?:ed)?\b", "natural"),
    _rule(r"\bsun[\s\-]?dried?\b", "natural"),
    _rule(r"\bnatural\b", "natural"),
    _rule(r"\bexperimental\b", "experimental"),
    _rule(r"\binnovative[\s\-]?process\b", "experimental"),
    _rule(r"\bspecial[\s\-]?ferment(?:ation)?\b", "experimental"),
]

# ─── Country normalisation ────────────────────────────────────────────────────
# Maps raw strings (including informal names) → ISO 3166-1 country name

COUNTRY_RULES: list[Rule] = [
    # Ethiopia / Africa
    _rule(r"\bethiopia\b|\bethiopian\b", "Ethiopia"),
    _rule(r"\bkenya\b|\bkenyan\b", "Kenya"),
    _rule(r"\brwanda\b|\brwandan\b", "Rwanda"),
    _rule(r"\burundi\b|\burundian\b", "Burundi"),
    _rule(r"\buganda\b|\bugandan\b", "Uganda"),
    _rule(r"\btanzania\b|\btanzanian\b", "Tanzania"),
    _rule(r"\bmalawi\b", "Malawi"),
    _rule(r"\bzambia\b", "Zambia"),
    _rule(r"\bzimbabwe\b", "Zimbabwe"),
    _rule(r"\bd(?:emocratic\s+republic\s+of\s+)?(?:the\s+)?congo\b|\bdrc\b", "Democratic Republic of Congo"),
    _rule(r"\bcameroon\b", "Cameroon"),
    _rule(r"\bburundi\b", "Burundi"),
    _rule(r"\byemen\b|\byemeni\b", "Yemen"),
    # Latin America
    _rule(r"\bcolombia\b|\bcolombian\b", "Colombia"),
    _rule(r"\bbrazil\b|\bbrazilian\b", "Brazil"),
    _rule(r"\bguatemala\b|\bguatemalan\b", "Guatemala"),
    _rule(r"\bcosta\s*rica\b|\bcosta\s*rican\b", "Costa Rica"),
    _rule(r"\bhonduras\b|\bhonduran\b", "Honduras"),
    _rule(r"\bel\s+salvador\b", "El Salvador"),
    _rule(r"\bnicaragua\b|\bnicaraguan\b", "Nicaragua"),
    _rule(r"\bpanama\b|\bpanamanian\b", "Panama"),
    _rule(r"\bperu\b|\bperuvian\b", "Peru"),
    _rule(r"\bbolivia\b|\bbolivian\b", "Bolivia"),
    _rule(r"\bmexico\b|\bmexican\b", "Mexico"),
    _rule(r"\bcuba\b|\bcuban\b", "Cuba"),
    _rule(r"\bjamaica\b|\bjamaican\b", "Jamaica"),
    _rule(r"\bhaiti\b|\bhaitian\b", "Haiti"),
    _rule(r"\bdominican\s+republic\b", "Dominican Republic"),
    _rule(r"\becuador\b|\becuadorian\b", "Ecuador"),
    _rule(r"\bvenezuela\b", "Venezuela"),
    # Asia / Pacific
    _rule(r"\bindonesia\b|\bindonesian\b", "Indonesia"),
    _rule(r"\bsumatra\b", "Indonesia"),          # island → country
    _rule(r"\bsulawesi\b", "Indonesia"),
    _rule(r"\bjava\b(?!\s*script)", "Indonesia"), # avoid JavaScript false match
    _rule(r"\bflores\b", "Indonesia"),
    _rule(r"\btimor[\s\-]leste\b|\beast\s+timor\b", "Timor-Leste"),
    _rule(r"\bpapua[\s\-]?new[\s\-]?guinea\b|\bpng\b", "Papua New Guinea"),
    _rule(r"\bvietnam\b|\bvietnamese\b|\bviet\s*nam\b", "Vietnam"),
    _rule(r"\bindia\b|\bindian\b", "India"),
    _rule(r"\bmyanmar\b|\bburma\b", "Myanmar"),
    _rule(r"\bthailand\b|\bthai\b", "Thailand"),
    _rule(r"\bchina\b|\bchinese\b|\byunnan\b", "China"),
    _rule(r"\bphilippines\b|\bfilipino\b", "Philippines"),
    _rule(r"\btaiwan\b", "Taiwan"),
    # Speciality / micro-origin
    _rule(r"\bkona\b", "United States"),          # Hawaii
    _rule(r"\bhawaii\b|\bhawaiian\b", "United States"),
    _rule(r"\bpuerto\s+rico\b", "United States"),
]

# ─── Region normalisation ─────────────────────────────────────────────────────
# Maps informal region names → canonical region + associated country
# Returns (region, country) tuples — country is used to fill origin_country
# when it is blank.

REGION_LOOKUP: dict[str, tuple[str, str]] = {
    # Ethiopia
    "yirgacheffe": ("Yirgacheffe", "Ethiopia"),
    "yirga cheffe": ("Yirgacheffe", "Ethiopia"),
    "guji": ("Guji", "Ethiopia"),
    "sidama": ("Sidama", "Ethiopia"),
    "sidamo": ("Sidama", "Ethiopia"),
    "harrar": ("Harrar", "Ethiopia"),
    "harar": ("Harrar", "Ethiopia"),
    "jimma": ("Jimma", "Ethiopia"),
    "limu": ("Limu", "Ethiopia"),
    "bench maji": ("Bench Maji", "Ethiopia"),
    "gedeo": ("Gedeo", "Ethiopia"),
    "kaffa": ("Kaffa", "Ethiopia"),
    "bench sheko": ("Bench Sheko", "Ethiopia"),
    # Kenya
    "kirinyaga": ("Kirinyaga", "Kenya"),
    "nyeri": ("Nyeri", "Kenya"),
    "murang'a": ("Murang'a", "Kenya"),
    "muranga": ("Murang'a", "Kenya"),
    "embu": ("Embu", "Kenya"),
    "meru": ("Meru", "Kenya"),
    "kiambu": ("Kiambu", "Kenya"),
    "machakos": ("Machakos", "Kenya"),
    # Colombia
    "huila": ("Huila", "Colombia"),
    "nariño": ("Nariño", "Colombia"),
    "narino": ("Nariño", "Colombia"),
    "cauca": ("Cauca", "Colombia"),
    "antioquia": ("Antioquia", "Colombia"),
    "tolima": ("Tolima", "Colombia"),
    "santander": ("Santander", "Colombia"),
    "cundinamarca": ("Cundinamarca", "Colombia"),
    "sierra nevada": ("Sierra Nevada", "Colombia"),
    # Guatemala
    "antigua": ("Antigua", "Guatemala"),
    "huehuetenango": ("Huehuetenango", "Guatemala"),
    "san marcos": ("San Marcos", "Guatemala"),
    "acatenango": ("Acatenango", "Guatemala"),
    # Costa Rica
    "tarrazú": ("Tarrazú", "Costa Rica"),
    "tarrazu": ("Tarrazú", "Costa Rica"),
    "west valley": ("West Valley", "Costa Rica"),
    "central valley": ("Central Valley", "Costa Rica"),
    # Brazil
    "cerrado mineiro": ("Cerrado Mineiro", "Brazil"),
    "sul de minas": ("Sul de Minas", "Brazil"),
    "mogiana": ("Mogiana", "Brazil"),
    "minas gerais": ("Minas Gerais", "Brazil"),
    "bahia": ("Bahia", "Brazil"),
    # Indonesia
    "aceh": ("Aceh", "Indonesia"),
    "gayo": ("Gayo", "Indonesia"),
    "toraja": ("Toraja", "Indonesia"),
    "flores": ("Flores", "Indonesia"),
    "java": ("Java", "Indonesia"),
    # Yemen
    "mokha": ("Mokha", "Yemen"),
    "mocha": ("Mokha", "Yemen"),
    "haraaz": ("Haraaz", "Yemen"),
    # India
    "coorg": ("Coorg", "India"),
    "chikmagalur": ("Chikmagalur", "India"),
    "araku valley": ("Araku Valley", "India"),
    "nilgiris": ("Nilgiris", "India"),
    "monsooned malabar": ("Malabar", "India"),
    # Rwanda
    "nyamasheke": ("Nyamasheke", "Rwanda"),
    "huye": ("Huye", "Rwanda"),
}

# ─── Weight parsing ───────────────────────────────────────────────────────────

_WEIGHT_G_RE = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE)
_WEIGHT_KG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*kg\b", re.IGNORECASE)
_WEIGHT_OZ_RE = re.compile(r"(\d+(?:\.\d+)?)\s*oz\b", re.IGNORECASE)
_WEIGHT_LB_RE = re.compile(r"(\d+(?:\.\d+)?)\s*lbs?\b", re.IGNORECASE)

# Standard weights that UK sellers use — used for fuzzy matching ambiguous inputs
STANDARD_WEIGHTS_G = [50, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 5000]


def parse_weight_g(raw: str) -> int | None:
    """
    Parse a weight string to integer grams.

    Handles: "250g", "1kg", "0.5kg", "12oz", "1lb", "1 KG"
    Returns None if no weight pattern is found.
    """
    if not raw:
        return None

    # Try grams first (most common)
    m = _WEIGHT_G_RE.search(raw)
    if m:
        return int(float(m.group(1)))

    # Kilograms
    m = _WEIGHT_KG_RE.search(raw)
    if m:
        return int(float(m.group(1)) * 1000)

    # Imperial: ounces (1 oz ≈ 28.3495g)
    m = _WEIGHT_OZ_RE.search(raw)
    if m:
        return round(float(m.group(1)) * 28.3495)

    # Imperial: pounds (1 lb ≈ 453.592g)
    m = _WEIGHT_LB_RE.search(raw)
    if m:
        return round(float(m.group(1)) * 453.592)

    return None


def parse_multiple_weights(raw: str) -> list[int]:
    """
    Extract all weight values from a string containing multiple sizes.

    e.g. "Available in 250g and 1kg" → [250, 1000]
    """
    weights: list[int] = []

    for m in _WEIGHT_G_RE.finditer(raw):
        w = int(float(m.group(1)))
        if w > 0 and w not in weights:
            weights.append(w)

    for m in _WEIGHT_KG_RE.finditer(raw):
        w = int(float(m.group(1)) * 1000)
        if w > 0 and w not in weights:
            weights.append(w)

    return sorted(weights)


def snap_to_standard_weight(weight_g: int, tolerance_pct: float = 0.05) -> int:
    """
    Snap a weight to the nearest standard value if within tolerance.

    Handles OCR/parse artefacts like 249g → 250g.
    tolerance_pct=0.05 means ±5%.
    """
    for std in STANDARD_WEIGHTS_G:
        if abs(weight_g - std) / std <= tolerance_pct:
            return std
    return weight_g
