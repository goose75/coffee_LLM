"""
Flavour taxonomy definition.

Three-level hierarchy modelled on the SCA/WCR Coffee Taster's Flavour Wheel.
Simplified to be useful for a consumer-facing site — jargon minimised.

Structure:
  FAMILIES  — depth 0, 8 nodes, each with a distinct colour
  CATEGORIES — depth 1, ~30 nodes grouped under families
  TAGS      — depth 2, ~100 leaf nodes with synonym lists for matching

Each entry is a dict:
  slug      : unique dot-separated path, e.g. "fruity.citrus.lemon"
  label     : display name
  depth     : 0 | 1 | 2
  parent    : parent slug (None for families)
  colour    : CSS hex (set on families; categories/tags inherit)
  synonyms  : list of raw-text strings that map to this node
  sort_order: within siblings
"""

TAXONOMY: list[dict] = [

    # ── Fruity ─────────────────────────────────────────────────────────────────
    {"slug": "fruity",                 "label": "Fruity",         "depth": 0, "parent": None,              "colour": "#e05c3a", "synonyms": ["fruit", "fruity", "fruited"],       "sort_order": 0},
    {"slug": "fruity.citrus",          "label": "Citrus",         "depth": 1, "parent": "fruity",          "colour": "#e05c3a", "synonyms": ["citrus", "citrusy"],                 "sort_order": 0},
    {"slug": "fruity.citrus.lemon",    "label": "Lemon",          "depth": 2, "parent": "fruity.citrus",   "colour": "#e05c3a", "synonyms": ["lemon", "lemon zest", "lemon curd", "lemony", "citric"], "sort_order": 0},
    {"slug": "fruity.citrus.lime",     "label": "Lime",           "depth": 2, "parent": "fruity.citrus",   "colour": "#e05c3a", "synonyms": ["lime", "lime zest"],                 "sort_order": 1},
    {"slug": "fruity.citrus.orange",   "label": "Orange",         "depth": 2, "parent": "fruity.citrus",   "colour": "#e05c3a", "synonyms": ["orange", "mandarin", "tangerine", "clementine", "blood orange"], "sort_order": 2},
    {"slug": "fruity.citrus.grapefruit","label": "Grapefruit",    "depth": 2, "parent": "fruity.citrus",   "colour": "#e05c3a", "synonyms": ["grapefruit", "pomelo"],              "sort_order": 3},
    {"slug": "fruity.citrus.bergamot", "label": "Bergamot",       "depth": 2, "parent": "fruity.citrus",   "colour": "#e05c3a", "synonyms": ["bergamot", "earl grey"],             "sort_order": 4},

    {"slug": "fruity.berry",           "label": "Berry",          "depth": 1, "parent": "fruity",          "colour": "#e05c3a", "synonyms": ["berry", "berries"],                  "sort_order": 1},
    {"slug": "fruity.berry.strawberry","label": "Strawberry",     "depth": 2, "parent": "fruity.berry",    "colour": "#e05c3a", "synonyms": ["strawberry", "strawberries"],        "sort_order": 0},
    {"slug": "fruity.berry.raspberry", "label": "Raspberry",      "depth": 2, "parent": "fruity.berry",    "colour": "#e05c3a", "synonyms": ["raspberry", "raspberries"],          "sort_order": 1},
    {"slug": "fruity.berry.blackcurrant","label": "Blackcurrant", "depth": 2, "parent": "fruity.berry",    "colour": "#e05c3a", "synonyms": ["blackcurrant", "black currant", "cassis", "blackberry"], "sort_order": 2},
    {"slug": "fruity.berry.blueberry", "label": "Blueberry",      "depth": 2, "parent": "fruity.berry",    "colour": "#e05c3a", "synonyms": ["blueberry", "blueberries"],          "sort_order": 3},
    {"slug": "fruity.berry.cherry",    "label": "Cherry",         "depth": 2, "parent": "fruity.berry",    "colour": "#e05c3a", "synonyms": ["cherry", "cherries", "red cherry", "black cherry", "maraschino"], "sort_order": 4},

    {"slug": "fruity.tropical",        "label": "Tropical",       "depth": 1, "parent": "fruity",          "colour": "#e05c3a", "synonyms": ["tropical", "tropical fruit", "exotic"], "sort_order": 2},
    {"slug": "fruity.tropical.mango",  "label": "Mango",          "depth": 2, "parent": "fruity.tropical", "colour": "#e05c3a", "synonyms": ["mango", "mangoes"],                  "sort_order": 0},
    {"slug": "fruity.tropical.pineapple","label": "Pineapple",    "depth": 2, "parent": "fruity.tropical", "colour": "#e05c3a", "synonyms": ["pineapple"],                         "sort_order": 1},
    {"slug": "fruity.tropical.passionfruit","label": "Passionfruit","depth": 2,"parent": "fruity.tropical","colour": "#e05c3a", "synonyms": ["passionfruit", "passion fruit"],      "sort_order": 2},
    {"slug": "fruity.tropical.papaya", "label": "Papaya",         "depth": 2, "parent": "fruity.tropical", "colour": "#e05c3a", "synonyms": ["papaya", "guava"],                   "sort_order": 3},
    {"slug": "fruity.tropical.lychee", "label": "Lychee",         "depth": 2, "parent": "fruity.tropical", "colour": "#e05c3a", "synonyms": ["lychee", "lichi"],                   "sort_order": 4},

    {"slug": "fruity.stone",           "label": "Stone Fruit",    "depth": 1, "parent": "fruity",          "colour": "#e05c3a", "synonyms": ["stone fruit", "drupe"],              "sort_order": 3},
    {"slug": "fruity.stone.peach",     "label": "Peach",          "depth": 2, "parent": "fruity.stone",    "colour": "#e05c3a", "synonyms": ["peach", "peaches", "white peach", "yellow peach", "nectarine"], "sort_order": 0},
    {"slug": "fruity.stone.apricot",   "label": "Apricot",        "depth": 2, "parent": "fruity.stone",    "colour": "#e05c3a", "synonyms": ["apricot", "apricots"],               "sort_order": 1},
    {"slug": "fruity.stone.plum",      "label": "Plum",           "depth": 2, "parent": "fruity.stone",    "colour": "#e05c3a", "synonyms": ["plum", "plums", "prune", "dried plum"], "sort_order": 2},

    {"slug": "fruity.dried",           "label": "Dried Fruit",    "depth": 1, "parent": "fruity",          "colour": "#e05c3a", "synonyms": ["dried fruit", "raisin", "date", "fig"], "sort_order": 4},
    {"slug": "fruity.dried.raisin",    "label": "Raisin",         "depth": 2, "parent": "fruity.dried",    "colour": "#e05c3a", "synonyms": ["raisin", "sultana"],                 "sort_order": 0},
    {"slug": "fruity.dried.fig",       "label": "Fig",            "depth": 2, "parent": "fruity.dried",    "colour": "#e05c3a", "synonyms": ["fig", "figs", "date"],               "sort_order": 1},
    {"slug": "fruity.dried.tamarind",  "label": "Tamarind",       "depth": 2, "parent": "fruity.dried",    "colour": "#e05c3a", "synonyms": ["tamarind"],                          "sort_order": 2},

    # ── Floral ─────────────────────────────────────────────────────────────────
    {"slug": "floral",                 "label": "Floral",         "depth": 0, "parent": None,              "colour": "#c084c0", "synonyms": ["floral", "flower", "flowers", "flowery", "bloom"], "sort_order": 1},
    {"slug": "floral.jasmine",         "label": "Jasmine",        "depth": 2, "parent": "floral",          "colour": "#c084c0", "synonyms": ["jasmine", "jasmin"],                 "sort_order": 0},
    {"slug": "floral.rose",            "label": "Rose",           "depth": 2, "parent": "floral",          "colour": "#c084c0", "synonyms": ["rose", "rosewater", "rose hip"],     "sort_order": 1},
    {"slug": "floral.lavender",        "label": "Lavender",       "depth": 2, "parent": "floral",          "colour": "#c084c0", "synonyms": ["lavender"],                          "sort_order": 2},
    {"slug": "floral.elderflower",     "label": "Elderflower",    "depth": 2, "parent": "floral",          "colour": "#c084c0", "synonyms": ["elderflower", "elder flower"],       "sort_order": 3},
    {"slug": "floral.hibiscus",        "label": "Hibiscus",       "depth": 2, "parent": "floral",          "colour": "#c084c0", "synonyms": ["hibiscus", "rosehip"],               "sort_order": 4},
    {"slug": "floral.orange_blossom",  "label": "Orange Blossom", "depth": 2, "parent": "floral",          "colour": "#c084c0", "synonyms": ["orange blossom"],                    "sort_order": 5},

    # ── Sweet ──────────────────────────────────────────────────────────────────
    {"slug": "sweet",                  "label": "Sweet",          "depth": 0, "parent": None,              "colour": "#d4a84b", "synonyms": ["sweet", "sweetness", "dessert"],     "sort_order": 2},
    {"slug": "sweet.caramel",          "label": "Caramel",        "depth": 1, "parent": "sweet",           "colour": "#d4a84b", "synonyms": ["caramel", "toffee", "butterscotch", "dulce de leche"], "sort_order": 0},
    {"slug": "sweet.caramel.caramel",  "label": "Caramel",        "depth": 2, "parent": "sweet.caramel",   "colour": "#d4a84b", "synonyms": ["caramel", "salted caramel"],         "sort_order": 0},
    {"slug": "sweet.caramel.toffee",   "label": "Toffee",         "depth": 2, "parent": "sweet.caramel",   "colour": "#d4a84b", "synonyms": ["toffee", "butterscotch", "fudge"],   "sort_order": 1},
    {"slug": "sweet.caramel.molasses", "label": "Molasses",       "depth": 2, "parent": "sweet.caramel",   "colour": "#d4a84b", "synonyms": ["molasses", "treacle", "brown sugar", "demerara"], "sort_order": 2},
    {"slug": "sweet.vanilla",          "label": "Vanilla",        "depth": 1, "parent": "sweet",           "colour": "#d4a84b", "synonyms": ["vanilla", "vanilla bean", "cream"],  "sort_order": 1},
    {"slug": "sweet.vanilla.vanilla",  "label": "Vanilla",        "depth": 2, "parent": "sweet.vanilla",   "colour": "#d4a84b", "synonyms": ["vanilla", "vanilla extract"],        "sort_order": 0},
    {"slug": "sweet.vanilla.cream",    "label": "Cream",          "depth": 2, "parent": "sweet.vanilla",   "colour": "#d4a84b", "synonyms": ["cream", "creamy", "milk", "custard"], "sort_order": 1},
    {"slug": "sweet.honey",            "label": "Honey",          "depth": 1, "parent": "sweet",           "colour": "#d4a84b", "synonyms": ["honey", "honeyed", "nectar", "syrup"], "sort_order": 2},
    {"slug": "sweet.honey.honey",      "label": "Honey",          "depth": 2, "parent": "sweet.honey",     "colour": "#d4a84b", "synonyms": ["honey", "honeycomb", "clover honey"], "sort_order": 0},
    {"slug": "sweet.honey.maple",      "label": "Maple Syrup",    "depth": 2, "parent": "sweet.honey",     "colour": "#d4a84b", "synonyms": ["maple syrup", "maple"],              "sort_order": 1},
    {"slug": "sweet.confection",       "label": "Confection",     "depth": 1, "parent": "sweet",           "colour": "#d4a84b", "synonyms": ["candy", "confection", "sweet"],      "sort_order": 3},
    {"slug": "sweet.confection.candy", "label": "Candy",          "depth": 2, "parent": "sweet.confection","colour": "#d4a84b", "synonyms": ["candy", "boiled sweets", "haribo", "sherbet"], "sort_order": 0},
    {"slug": "sweet.confection.marzipan","label": "Marzipan",     "depth": 2, "parent": "sweet.confection","colour": "#d4a84b", "synonyms": ["marzipan", "almond paste"],          "sort_order": 1},

    # ── Chocolate ──────────────────────────────────────────────────────────────
    {"slug": "chocolate",              "label": "Chocolate",      "depth": 0, "parent": None,              "colour": "#7c4b2a", "synonyms": ["chocolate", "cocoa", "cacao"],       "sort_order": 3},
    {"slug": "chocolate.dark",         "label": "Dark Chocolate", "depth": 2, "parent": "chocolate",       "colour": "#7c4b2a", "synonyms": ["dark chocolate", "bittersweet chocolate", "70% chocolate"], "sort_order": 0},
    {"slug": "chocolate.milk",         "label": "Milk Chocolate", "depth": 2, "parent": "chocolate",       "colour": "#7c4b2a", "synonyms": ["milk chocolate", "white chocolate"],  "sort_order": 1},
    {"slug": "chocolate.cocoa",        "label": "Cocoa",          "depth": 2, "parent": "chocolate",       "colour": "#7c4b2a", "synonyms": ["cocoa", "cacao", "cocoa powder", "raw cacao"], "sort_order": 2},
    {"slug": "chocolate.mocha",        "label": "Mocha",          "depth": 2, "parent": "chocolate",       "colour": "#7c4b2a", "synonyms": ["mocha", "coffee chocolate"],         "sort_order": 3},

    # ── Nutty ──────────────────────────────────────────────────────────────────
    {"slug": "nutty",                  "label": "Nutty",          "depth": 0, "parent": None,              "colour": "#a07850", "synonyms": ["nutty", "nut", "nuts"],              "sort_order": 4},
    {"slug": "nutty.almond",           "label": "Almond",         "depth": 2, "parent": "nutty",           "colour": "#a07850", "synonyms": ["almond", "amaretto", "marzipan"],   "sort_order": 0},
    {"slug": "nutty.hazelnut",         "label": "Hazelnut",       "depth": 2, "parent": "nutty",           "colour": "#a07850", "synonyms": ["hazelnut", "hazel", "praline"],      "sort_order": 1},
    {"slug": "nutty.walnut",           "label": "Walnut",         "depth": 2, "parent": "nutty",           "colour": "#a07850", "synonyms": ["walnut", "pecan"],                   "sort_order": 2},
    {"slug": "nutty.peanut",           "label": "Peanut",         "depth": 2, "parent": "nutty",           "colour": "#a07850", "synonyms": ["peanut", "peanut butter"],           "sort_order": 3},
    {"slug": "nutty.cashew",           "label": "Cashew",         "depth": 2, "parent": "nutty",           "colour": "#a07850", "synonyms": ["cashew"],                            "sort_order": 4},

    # ── Spice ──────────────────────────────────────────────────────────────────
    {"slug": "spice",                  "label": "Spice",          "depth": 0, "parent": None,              "colour": "#c47820", "synonyms": ["spice", "spiced", "spicy", "warm spice"], "sort_order": 5},
    {"slug": "spice.cinnamon",         "label": "Cinnamon",       "depth": 2, "parent": "spice",           "colour": "#c47820", "synonyms": ["cinnamon", "cassia"],                "sort_order": 0},
    {"slug": "spice.clove",            "label": "Clove",          "depth": 2, "parent": "spice",           "colour": "#c47820", "synonyms": ["clove", "cloves"],                   "sort_order": 1},
    {"slug": "spice.cardamom",         "label": "Cardamom",       "depth": 2, "parent": "spice",           "colour": "#c47820", "synonyms": ["cardamom", "cardamon"],              "sort_order": 2},
    {"slug": "spice.pepper",           "label": "Black Pepper",   "depth": 2, "parent": "spice",           "colour": "#c47820", "synonyms": ["black pepper", "pepper", "white pepper"], "sort_order": 3},
    {"slug": "spice.nutmeg",           "label": "Nutmeg",         "depth": 2, "parent": "spice",           "colour": "#c47820", "synonyms": ["nutmeg", "mace"],                    "sort_order": 4},
    {"slug": "spice.anise",            "label": "Anise",          "depth": 2, "parent": "spice",           "colour": "#c47820", "synonyms": ["anise", "star anise", "liquorice", "licorice"], "sort_order": 5},

    # ── Earthy ─────────────────────────────────────────────────────────────────
    {"slug": "earthy",                 "label": "Earthy",         "depth": 0, "parent": None,              "colour": "#6b7c4a", "synonyms": ["earthy", "earth", "terroir", "rustic"], "sort_order": 6},
    {"slug": "earthy.woody",           "label": "Woody",          "depth": 2, "parent": "earthy",          "colour": "#6b7c4a", "synonyms": ["woody", "wood", "cedar", "oak", "pine"], "sort_order": 0},
    {"slug": "earthy.tobacco",         "label": "Tobacco",        "depth": 2, "parent": "earthy",          "colour": "#6b7c4a", "synonyms": ["tobacco", "tobacco leaf", "cigar"],  "sort_order": 1},
    {"slug": "earthy.leather",         "label": "Leather",        "depth": 2, "parent": "earthy",          "colour": "#6b7c4a", "synonyms": ["leather"],                           "sort_order": 2},
    {"slug": "earthy.mushroom",        "label": "Mushroom",       "depth": 2, "parent": "earthy",          "colour": "#6b7c4a", "synonyms": ["mushroom", "fungal", "umami"],       "sort_order": 3},
    {"slug": "earthy.herbal",          "label": "Herbal",         "depth": 2, "parent": "earthy",          "colour": "#6b7c4a", "synonyms": ["herbal", "herbs", "green tea", "black tea", "grassy", "grass"], "sort_order": 4},

    # ── Fermented / Complex ────────────────────────────────────────────────────
    {"slug": "fermented",              "label": "Fermented",      "depth": 0, "parent": None,              "colour": "#8b6bab", "synonyms": ["fermented", "funky", "complex", "experimental"], "sort_order": 7},
    {"slug": "fermented.wine",         "label": "Wine",           "depth": 2, "parent": "fermented",       "colour": "#8b6bab", "synonyms": ["wine", "winey", "red wine", "white wine", "port"], "sort_order": 0},
    {"slug": "fermented.whisky",       "label": "Whisky",         "depth": 2, "parent": "fermented",       "colour": "#8b6bab", "synonyms": ["whisky", "whiskey", "bourbon", "rum", "spirit"], "sort_order": 1},
    {"slug": "fermented.vinegar",      "label": "Vinegar",        "depth": 2, "parent": "fermented",       "colour": "#8b6bab", "synonyms": ["vinegar", "acetic", "sour", "kombucha"], "sort_order": 2},
    {"slug": "fermented.yoghurt",      "label": "Yoghurt",        "depth": 2, "parent": "fermented",       "colour": "#8b6bab", "synonyms": ["yoghurt", "yogurt", "kefir", "lactic"], "sort_order": 3},

]

# Build slug → node lookup for parent resolution
TAXONOMY_BY_SLUG: dict[str, dict] = {node["slug"]: node for node in TAXONOMY}


def get_families() -> list[dict]:
    return [n for n in TAXONOMY if n["depth"] == 0]


def get_family_colour(slug: str) -> str:
    """Return the colour for any node by walking up to its family."""
    parts = slug.split(".")
    family = TAXONOMY_BY_SLUG.get(parts[0], {})
    return family.get("colour", "#9a9080")
