"""
coffee_classifier.py — Only admit roasted coffee beans (whole bean or ground).

Scope: whole bean coffee, ground coffee, single origin, blends, espresso blends,
decaf beans, green (unroasted) beans. Everything else is excluded.

NOT in scope: capsules, pods, gift sets, gift boxes, merchandise, equipment,
apparel, courses, classes, taste cards, subscriptions, posters, porcelain,
cleaning products, packaging accessories.
"""

from __future__ import annotations
import re


# ── STEP 1: Hard-exclude any product whose title matches these patterns ────────
# If ANY of these match, the product is rejected immediately — even if it also
# contains coffee-origin words.

_EXCLUDE_PATTERNS = [
    re.compile(p, re.I) for p in [
        # Capsules / pods — explicitly excluded per brief
        r"\bcapsule[s]?\b", r"\bpod[s]?\b", r"\bnespresso\b",
        r"\bnespresso[\s-]*compatible\b",

        # Gift sets, boxes, bundles — excluded per brief
        r"\bgift\s*(set|box|pack|card|message)\b",
        r"\be-?gift\b",
        r"\bbundle\b",
        # Subscriptions — exclude all variants. Many roasters just call them
        # "Subscription" with a duration prefix. We exclude the bare word
        # *anywhere in the title* because a real coffee bag is never named
        # like that. Loyalty/customer-only SKUs follow the same shape.
        r"\bsubscription\b",
        r"\b(?:weekly|monthly|fortnightly|quarterly)\s+(?:plan|box|delivery)\b",
        r"\b(?:one|two|three|four|six|twelve)[\s-]*month\b",
        r"\bcustomers?\s+only\b",
        r"\bbeanz\s+(?:customer|only)\b",  # specific Grind loyalty SKU
        r"\blove\s+affair\b",  # "Brazilian Love Affair Coffee Gift Box"

        # Taste cards / tasting notes cards — excluded per brief
        r"\btaste\s+card\b",

        # Courses, classes, events
        r"\bcourse\b", r"\bclass\b", r"\bworkshop\b",
        r"\bfundamentals\b",  # "Coffee Fundamentals - Nottingham"

        # Merchandise / print
        r"\bposter\b", r"\bprint\b",

        # Porcelain / vessels / cups / glassware
        r"\bporcelain\b", r"\bcup\b", r"\bmug\b", r"\btumbler\b",
        r"\bkeep\s*cup\b", r"\bglass\b", r"\bvessel\b",
        r"\bdimple\b",  # "porcelain dimple coffee cup"

        # Apparel / fashion
        r"\bt-?shirt\b", r"\bsweatshirt\b", r"\bhoodie\b",
        r"\bcap\b(?!\s*acity)", r"\btote\b", r"\bapron\b",

        # Equipment brands
        r"\bfellow\b", r"\bbialetti\b", r"\bbodum\b", r"\bcommandante\b",
        r"\bhuskee\b", r"\bflair\b", r"\bwacaco\b", r"\bpicopresso\b",
        r"\bwilfa\b", r"\btimemore\b", r"\bfelicita\b", r"\bpullman\b",
        r"\bsibarist\b", r"\bkalita\b", r"\baeropress\b", r"\baero\s*press\b",
        r"\bchemex\b", r"\bhario\b",

        # Equipment types
        r"\bgrinder\b", r"\bkettle\b", r"\bscale[s]?\b", r"\btamper\b",
        r"\bfilter\s*(paper|papers|plate|basket|pack)\b",
        r"\bmetal\s+filter\b", r"\breusable.*filter\b",
        r"\bdripper\b", r"\bcafetiere\b", r"\bfrench\s*press\b",
        r"\bespresso\s*machine\b", r"\bpod\s*machine\b",
        r"\bmilk\s*(jug|frother|steaming|pitcher)\b",
        r"\bcanister\b", r"\bairscape\b",
        r"\bknock\s*box\b",

        # Cleaning / maintenance
        r"\bcleaning\b", r"\bdescal",
        r"\bpuly\b", r"\bcaff\s*verde\b",
        r"\bcartridge\b", r"\bbwt\b",

        # Packaging accessories
        r"\bdegassing\s+valve\b", r"\bzip\s+lock\b", r"\bjute\b",

        # Stickers / pins / misc merch
        r"\bsticker\b", r"\bpin\s*badge\b", r"\bkeyring\b",
        r"\bcar\s+bumper\b",

        # Non-coffee drinks / food
        r"\bmatcha\b", r"\bdrinking\s+chocolate\b", r"\bchocolate\s+flakes\b",
        r"\bice\s+cube\b", r"\bliqueur\b", r"\bcold\s+brew\s+concentrate\b",
        r"\biced\s+oat\b", r"\boat\s+latte\b",
        r"\bsyrup\b",

        # Misc exclusions
        r"\bshipping\s+protection\b",
        r"\bgolden\s+ticket\b",
        r"\bgift\s+message\b",
        r"\bmembership\b",
        r"\bbeauty\s+pie\b", r"\bwowcher\b",
        r"\bpokemon\b", r"\bpok\xe9mon\b",
        r"\bbarista\s+(class|course|training)\b",
        r"\blatte\s+art\s+class\b",
        r"\bprivate\s+group\b",
    ]
]


# ── STEP 2: Must contain at least one POSITIVE coffee-bean signal ─────────────
# After passing exclude checks, the product must show evidence it is actually
# a roasted or green coffee bean product.

_ORIGIN_WORDS = {
    "ethiopia", "ethiopian", "kenya", "kenyan", "colombia", "colombian",
    "brazil", "brazilian", "guatemala", "guatemalan", "rwanda", "rwandan",
    "burundi", "uganda", "peru", "peruvian", "honduras", "honduran",
    "costa rica", "panama", "panamanian", "el salvador", "indonesia",
    "indonesian", "yemen", "yemeni", "india", "indian", "mexico", "mexican",
    "nicaragua", "tanzanian", "tanzania",
    "papua new guinea", "bolivia", "malawi",
    "yirgacheffe", "sidamo", "guji", "kirinyaga", "nyeri", "huila",
    "antioquia", "cauca", "nariño",
}

_BEAN_SIGNALS = {
    # Bean types
    "whole bean", "whole-bean", "ground coffee", "coffee beans", "coffee bean",
    "green coffee", "unroasted",
    # Roast levels
    "light roast", "medium roast", "dark roast", "espresso roast",
    # Process
    "washed", "natural process", "honey process", "anaerobic",
    "wet-hulled", "carbonic maceration",
    # Varieties
    "arabica", "robusta", "geisha", "gesha",
    "bourbon", "typica", "catuai", "caturra", "pacamara", "sidra",
    "pink bourbon", "sl28", "sl34", "mejorado",
    # Blend/product words that specifically mean beans
    "espresso blend", "filter blend", "house blend", "single origin",
    "decaf",  # decaf beans
    # Roastery naming conventions
    "nº",  # Rave numbering e.g. "Signature Blend Nº 1"
    "lot",  # lot numbers
    "compostable",  # compostable coffee bags
    # Green coffee
    "green coffee beans",
}

# Title patterns that confirm bean content
_BEAN_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"\bblend\s+(n[oº°]|#)?\s*\d",     # "Blend Nº 1"
        r"n[oº°]\s*\d+",                     # "Nº 50", "N° 341"
        r"\b(250|500|1000|1kg|250g|500g)\b", # weight indicators
        r"\b(light|medium|dark)\s+roast\b",
        r"\bwhole\s*bean\b",
        r"\bground\b(?!\s*(floor|floor|up|down|breaking|work|level))",
        r"\bespresso\s+blend\b",
        r"\bfilter\s+blend\b",
        r"\bdecaf\b",
        r"\bsingle\s+origin\b",
        r"\bgreen\s+coffee\b",
        r"\bcompostable\b",  # compostable bags = coffee bags
        r"\broast\s+date\b",
        r"\bhalf\s+caf\b",
    ]
]


def is_coffee_product(product: dict) -> tuple[bool, str]:
    """
    Return (True, reason) if the product is a roasted/green coffee bean product.
    Return (False, reason) if it should be excluded.
    """
    title: str = product.get("title", "") or ""
    title_lower = title.lower()

    product_type: str = (product.get("product_type", "") or "").lower().strip()

    raw_tags = product.get("tags", "")
    if isinstance(raw_tags, list):
        tags = [t.strip().lower() for t in raw_tags if t.strip()]
    else:
        tags = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]

    tags_str = " ".join(tags)
    combined = f"{title_lower} {tags_str}"

    # ── Step 1: Hard excludes ─────────────────────────────────────────────────
    for pattern in _EXCLUDE_PATTERNS:
        if pattern.search(title):
            return False, f"excluded: '{pattern.pattern[:50]}'"

    # ── Step 2: Must have at least one positive bean signal ───────────────────

    # Check product_type first
    if product_type in {"coffee", "coffee beans", "whole bean", "ground coffee",
                        "espresso", "single origin", "filter coffee", "decaf",
                        "specialty coffee", "green coffee"}:
        return True, f"product_type='{product_type}'"

    # Origin word
    for word in _ORIGIN_WORDS:
        if word in combined:
            return True, f"origin: '{word}'"

    # Bean signal word
    for word in _BEAN_SIGNALS:
        if word in combined:
            return True, f"bean signal: '{word}'"

    # Bean pattern in title
    for pattern in _BEAN_PATTERNS:
        if pattern.search(title):
            return True, f"bean pattern: '{pattern.pattern[:40]}'"

    return False, "no coffee bean signals"
