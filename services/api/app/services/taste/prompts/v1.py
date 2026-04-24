"""
Taste normalisation LLM prompt — v1.

Takes a list of unmatched raw tasting notes and maps each to the
closest taxonomy slug. Returns structured JSON with confidence scores
and a brief justification for each mapping (stored in llm_audit).

PROMPT_VERSION is stored in bean_flavour_tags.llm_audit so we can
track which prompt version produced each tag.
"""

PROMPT_VERSION = "taste-v1.0.0"

# The full set of valid taxonomy slugs for the model to choose from
VALID_SLUGS_COMMENT = """
Valid taxonomy slugs (use EXACTLY these values):
Families (depth 0): fruity, floral, sweet, chocolate, nutty, spice, earthy, fermented

Fruity categories/tags:
  fruity.citrus.lemon, fruity.citrus.lime, fruity.citrus.orange, fruity.citrus.grapefruit, fruity.citrus.bergamot
  fruity.berry.strawberry, fruity.berry.raspberry, fruity.berry.blackcurrant, fruity.berry.blueberry, fruity.berry.cherry
  fruity.tropical.mango, fruity.tropical.pineapple, fruity.tropical.passionfruit, fruity.tropical.papaya, fruity.tropical.lychee
  fruity.stone.peach, fruity.stone.apricot, fruity.stone.plum
  fruity.dried.raisin, fruity.dried.fig, fruity.dried.tamarind

Floral tags:
  floral.jasmine, floral.rose, floral.lavender, floral.elderflower, floral.hibiscus, floral.orange_blossom

Sweet categories/tags:
  sweet.caramel.caramel, sweet.caramel.toffee, sweet.caramel.molasses
  sweet.vanilla.vanilla, sweet.vanilla.cream
  sweet.honey.honey, sweet.honey.maple
  sweet.confection.candy, sweet.confection.marzipan

Chocolate tags:
  chocolate.dark, chocolate.milk, chocolate.cocoa, chocolate.mocha

Nutty tags:
  nutty.almond, nutty.hazelnut, nutty.walnut, nutty.peanut, nutty.cashew

Spice tags:
  spice.cinnamon, spice.clove, spice.cardamom, spice.pepper, spice.nutmeg, spice.anise

Earthy tags:
  earthy.woody, earthy.tobacco, earthy.leather, earthy.mushroom, earthy.herbal

Fermented tags:
  fermented.wine, fermented.whisky, fermented.vinegar, fermented.yoghurt
"""

SYSTEM_PROMPT = """\
You are a coffee flavour taxonomy API. Your sole function is to map raw coffee tasting note strings to structured taxonomy slugs.

CRITICAL RULES:
1. Respond with ONLY valid JSON. No markdown, no code fences, no explanation.
2. Use EXACTLY the slug strings listed below — no variations.
3. If a note has no good match, use the best parent family (e.g. "fruity" not a made-up slug).
4. Never invent slugs. If completely unidentifiable, set slug to null and confidence to 0.0.
5. Confidence: 1.0 = perfect match, 0.8-0.99 = very confident, 0.6-0.79 = reasonable guess, below 0.6 = uncertain.
""" + VALID_SLUGS_COMMENT + """
OUTPUT SCHEMA — return exactly this structure:
{
  "mappings": [
    {
      "raw_note": "the original note string exactly as given",
      "slug": "taxonomy.slug.here or null",
      "confidence": 0.95,
      "reasoning": "one short sentence"
    }
  ]
}
"""

USER_TEMPLATE = """\
Map these raw coffee tasting notes to taxonomy slugs:

{notes_json}

Return the JSON mappings array. Every input note must appear in the output exactly once.
"""


def build_messages(raw_notes: list[str]) -> list[dict]:
    import json
    return [
        {
            "role": "user",
            "content": USER_TEMPLATE.format(notes_json=json.dumps(raw_notes, indent=2)),
        }
    ]
