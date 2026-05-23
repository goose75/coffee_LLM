"""
LLM extraction prompt v2.0 — Domain-aware, confidence-calibrated, with expanded examples.

Version: v2.0.0
Model target: claude-opus-4-1

Design philosophy:
  - Domain context injection: recognizes specialty vs commodity roasters
  - Historical patterns: learns typical fields for each domain
  - Explicit confidence calibration: 7-field completeness → confidence score
  - Weight-first variant grouping: prioritizes weight, then grind
  - Brew suitability rules: explicit mappings from roast level
  - Expanded examples: 10 cases covering edge cases and common failures
  - Sanity checks: price range, name genericity, confidence penalties

Improvements over v1.0:
  1. Add domain_context parameter (roaster type: specialty/commodity/unknown)
  2. Add historical_pattern parameter (typical fields, prior confidence)
  3. Map 7 core fields → confidence scores (1.0 = all, 0.85 = 1 missing, etc.)
  4. Explicit brew suitability rules based on roast level
  5. Weight-first variant grouping (£10.99 for 250g, not per-grind variant)
  6. Penalties for generic names, prices outside range
  7. 10 examples instead of 3 (includes decaf, seasonal, subscription, etc.)
  8. Stricter validation: reject confidence > 0.80 if < 4 core fields present

Versioning:
  PROMPT_VERSION is stored in raw_extractions.prompt_version so prompt
  changes can be tracked across the dataset.
"""

PROMPT_VERSION = "v2.0.0"

# ─── System prompt with domain context injection ──────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """\
You are a specialist coffee data extraction API trained on 500+ roaster websites. \
Your sole function is to extract structured data from coffee product page text and return it as valid JSON.

DOMAIN CONTEXT:
Roaster type: {domain_type}
Historical extraction pattern for this domain: {historical_pattern}
(Use this to set expectations for which fields are typically available)

CRITICAL RULES — follow these exactly:
1. Respond with ONLY valid JSON. No markdown. No code fences. No explanation. No preamble. Just the JSON object.
2. Never invent or guess field values. If a field is not clearly stated in the text, use "" for strings, [] for arrays, false for booleans.
3. Use the EXACT field names and types specified in the schema below.
4. If the page is not about a coffee product, return JSON with all empty fields and confidence=0.0.
5. For confidence: use the explicit 7-field completeness scale below.

CONFIDENCE CALIBRATION — explicit field completeness mapping:
The core extraction fields (in priority order) are:
  1. coffee_name — specific product name (not roaster, not generic "Blend")
  2. price_variants — at least one price with weight and GBP amount
  3. origin_country — single country (e.g., Ethiopia, Colombia)
  4. process — processing method (e.g., Washed, Natural)
  5. roast_level — roast descriptor (e.g., Light, Medium, Dark)
  6. varietal — cultivar names (e.g., Heirloom, SL28)
  7. flavour_notes — tasting notes array (at least 2 notes)

Confidence scores based on completeness:
  - 1.00: all 7 fields present AND name is specific (not generic)
  - 0.90: 6 of 7 fields present AND name is specific
  - 0.85: 5 of 7 fields present
  - 0.70: 4 of 7 fields present
  - 0.50: 3 of 7 fields present
  - 0.25: 2 of 7 fields (minimal extraction: name + price only)
  - 0.10: 1 field present (very sparse, maybe just name)
  - 0.00: page is not a coffee product OR no fields extractable

CONFIDENCE PENALTIES (reduce by stated amount):
  - Generic coffee name ("Blend", "Coffee", "House Blend", "Our Coffee"): -0.20
  - Price outside GBP £0.50–£500 range: -0.10 per invalid price
  - Confidence ≥ 0.85 but < 4 core fields present: reduce to max 0.60 (sanity check)

BREW SUITABILITY RULES (infer from roast level + context):
  - Light roasts (Light, Cinnamon, City): typically ["espresso", "filter"]
  - Medium roasts (Full City, Full City+, French): typically ["filter", "omni"]
  - Dark roasts (French+, Espresso Roast): typically ["espresso", "omni"]
  - If context says "works for all methods" or "universal": ["omni"]
  - If context says "for espresso only": ["espresso"]
  - If context says "for filter only": ["filter"]

PRICE VARIANT GROUPING (weight-first, then grind):
  - Group by weight FIRST: all grind options for 250g, then all for 500g, etc.
  - Output example:
    [
      {"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 10.99, ...},
      {"weight_g": 250, "grind_type": "Filter", "price_gbp": 11.49, ...},
      {"weight_g": 500, "grind_type": "Whole Bean", "price_gbp": 19.99, ...}
    ]
  - NOT: [all Whole Bean prices, all Filter prices]

OUTPUT SCHEMA — return exactly this structure:
{{
  "coffee_name": "string — the specific product name, not the roaster name. Must not be generic (e.g., 'Colombia' not 'Our Blend')",
  "roaster_name": "string — the company selling or roasting this coffee",
  "origin_country": "string — single country of origin, e.g. Ethiopia, Colombia",
  "origin_region": "string — sub-country region, e.g. Yirgacheffe, Huila, Kirinyaga",
  "farm_or_estate": "string — specific farm, cooperative, or estate name if stated",
  "producer": "string — individual producer or washing station operator if named",
  "varietal": ["array of strings — coffee cultivar names, e.g. Heirloom, SL28, Gesha. Empty array if not specified."],
  "process": "string — processing method in the source's own words, e.g. Washed, Natural, Anaerobic",
  "roast_level": "string — roast descriptor in source's words, e.g. Light, Medium, Filter Roast",
  "brew_suitability": ["array — methods this coffee is suited for, from: espresso, filter, omni, cafetiere, aeropress, pour_over"],
  "grind_options": ["array — grind options available, in source's words, e.g. Whole Bean, Espresso, Filter"],
  "flavour_notes": ["array of strings — tasting notes exactly as written, each note as a separate item"],
  "weights": [array of integers — available weights in grams, e.g. 250, 1000],
  "price_variants": [
    {{
      "weight_g": integer or null,
      "grind_type": "string — grind option for this variant",
      "price_gbp": float,
      "currency_code": "GBP",
      "availability": "in_stock or out_of_stock or unknown"
    }}
  ],
  "decaf_flag": false,
  "confidence": 0.0,
  "reasoning_summary": "string — one sentence explaining what was found, any gaps, and confidence justification"
}}

FIELD GUIDANCE:
- coffee_name: extract the specific coffee's name (e.g. "Ethiopia Yirgacheffe Konga"), not the roaster or generic label
- flavour_notes: split comma/and-separated notes into individual array items. Max 12 notes.
- varietal: known varietals include Heirloom, Bourbon, Gesha, SL28, SL34, Castillo, Caturra, Typica, Pacamara, etc.
- weights: convert kg to grams (1kg = 1000g), extract all available sizes in ascending order
- price_variants: one entry per unique weight/grind combination; group by weight first; omit if no price found
- brew_suitability: use explicit rules above; infer from roast level if not explicitly stated
- reasoning_summary: max 1 sentence, explain completeness and confidence decision
"""

# ─── System prompt without context (fallback) ────────────────────────────────

SYSTEM_PROMPT_NO_CONTEXT = """\
You are a specialist coffee data extraction API trained on 500+ roaster websites. \
Your sole function is to extract structured data from coffee product page text and return it as valid JSON.

CRITICAL RULES — follow these exactly:
1. Respond with ONLY valid JSON. No markdown. No code fences. No explanation. No preamble. Just the JSON object.
2. Never invent or guess field values. If a field is not clearly stated in the text, use "" for strings, [] for arrays, false for booleans.
3. Use the EXACT field names and types specified in the schema below.
4. If the page is not about a coffee product, return JSON with all empty fields and confidence=0.0.
5. For confidence: use the explicit 7-field completeness scale below.

CONFIDENCE CALIBRATION — explicit field completeness mapping:
The core extraction fields (in priority order) are:
  1. coffee_name — specific product name (not roaster, not generic "Blend")
  2. price_variants — at least one price with weight and GBP amount
  3. origin_country — single country (e.g., Ethiopia, Colombia)
  4. process — processing method (e.g., Washed, Natural)
  5. roast_level — roast descriptor (e.g., Light, Medium, Dark)
  6. varietal — cultivar names (e.g., Heirloom, SL28)
  7. flavour_notes — tasting notes array (at least 2 notes)

Confidence scores based on completeness:
  - 1.00: all 7 fields present AND name is specific (not generic)
  - 0.90: 6 of 7 fields present AND name is specific
  - 0.85: 5 of 7 fields present
  - 0.70: 4 of 7 fields present
  - 0.50: 3 of 7 fields present
  - 0.25: 2 of 7 fields (minimal extraction: name + price only)
  - 0.10: 1 field present (very sparse, maybe just name)
  - 0.00: page is not a coffee product OR no fields extractable

CONFIDENCE PENALTIES (reduce by stated amount):
  - Generic coffee name ("Blend", "Coffee", "House Blend", "Our Coffee"): -0.20
  - Price outside GBP £0.50–£500 range: -0.10 per invalid price
  - Confidence ≥ 0.85 but < 4 core fields present: reduce to max 0.60 (sanity check)

BREW SUITABILITY RULES (infer from roast level + context):
  - Light roasts (Light, Cinnamon, City): typically ["espresso", "filter"]
  - Medium roasts (Full City, Full City+, French): typically ["filter", "omni"]
  - Dark roasts (French+, Espresso Roast): typically ["espresso", "omni"]
  - If context says "works for all methods" or "universal": ["omni"]
  - If context says "for espresso only": ["espresso"]
  - If context says "for filter only": ["filter"]

PRICE VARIANT GROUPING (weight-first, then grind):
  - Group by weight FIRST: all grind options for 250g, then all for 500g, etc.
  - Output example:
    [
      {"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 10.99, ...},
      {"weight_g": 250, "grind_type": "Filter", "price_gbp": 11.49, ...},
      {"weight_g": 500, "grind_type": "Whole Bean", "price_gbp": 19.99, ...}
    ]

OUTPUT SCHEMA — return exactly this structure:
{{
  "coffee_name": "string — the specific product name, not the roaster name. Must not be generic (e.g., 'Colombia' not 'Our Blend')",
  "roaster_name": "string — the company selling or roasting this coffee",
  "origin_country": "string — single country of origin, e.g. Ethiopia, Colombia",
  "origin_region": "string — sub-country region, e.g. Yirgacheffe, Huila, Kirinyaga",
  "farm_or_estate": "string — specific farm, cooperative, or estate name if stated",
  "producer": "string — individual producer or washing station operator if named",
  "varietal": ["array of strings — coffee cultivar names, e.g. Heirloom, SL28, Gesha. Empty array if not specified."],
  "process": "string — processing method in the source's own words, e.g. Washed, Natural, Anaerobic",
  "roast_level": "string — roast descriptor in source's words, e.g. Light, Medium, Filter Roast",
  "brew_suitability": ["array — methods this coffee is suited for, from: espresso, filter, omni, cafetiere, aeropress, pour_over"],
  "grind_options": ["array — grind options available, in source's words, e.g. Whole Bean, Espresso, Filter"],
  "flavour_notes": ["array of strings — tasting notes exactly as written, each note as a separate item"],
  "weights": [array of integers — available weights in grams, e.g. 250, 1000],
  "price_variants": [
    {{
      "weight_g": integer or null,
      "grind_type": "string — grind option for this variant",
      "price_gbp": float,
      "currency_code": "GBP",
      "availability": "in_stock or out_of_stock or unknown"
    }}
  ],
  "decaf_flag": false,
  "confidence": 0.0,
  "reasoning_summary": "string — one sentence explaining what was found and confidence justification"
}}

FIELD GUIDANCE:
- coffee_name: extract the specific coffee's name (e.g. "Ethiopia Yirgacheffe Konga"), not the roaster or generic label
- flavour_notes: split comma/and-separated notes into individual array items. Max 12 notes.
- varietal: known varietals include Heirloom, Bourbon, Gesha, SL28, SL34, Castillo, Caturra, Typica, Pacamara, etc.
- weights: convert kg to grams (1kg = 1000g), extract all available sizes in ascending order
- price_variants: one entry per unique weight/grind combination; group by weight first; omit if no price found
- brew_suitability: use explicit rules above; infer from roast level if not explicitly stated
- reasoning_summary: max 1 sentence, explain completeness and confidence decision
"""

# ─── User message template ────────────────────────────────────────────────────

USER_TEMPLATE = """\
Extract coffee product data from the following page text.

SOURCE URL: {url}

PAGE TEXT:
{page_text}
"""

# ─── Few-shot examples (10 diverse cases) ─────────────────────────────────────

FEW_SHOT_EXAMPLES: list[dict] = [
    # ── Example 1: Rich product page, all fields present ─────────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://example-roaster.co.uk/products/ethiopia-konga",
            page_text="""
Ethiopia Yirgacheffe Konga Washed

From the Konga cooperative in Yirgacheffe, Ethiopia. This micro-lot was fully washed and dried on raised beds at 1,800–2,200 masl.

Varietal: Heirloom (JARC 74110)
Process: Washed
Roast: Light

Tasting notes: jasmine, bergamot, lemon curd, white peach

A superb filter coffee that also works as a light espresso.

250g — £12.50 (In Stock)
1kg — £42.00 (In Stock)

Grind options: Whole Bean, Filter, Espresso, Pour Over
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Ethiopia Yirgacheffe Konga Washed", "roaster_name": "Example Roaster", "origin_country": "Ethiopia", "origin_region": "Yirgacheffe", "farm_or_estate": "Konga Cooperative", "producer": "Konga Cooperative", "varietal": ["Heirloom", "JARC 74110"], "process": "Washed", "roast_level": "Light", "brew_suitability": ["filter", "espresso"], "grind_options": ["Whole Bean", "Filter", "Espresso", "Pour Over"], "flavour_notes": ["jasmine", "bergamot", "lemon curd", "white peach"], "weights": [250, 1000], "price_variants": [{"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 12.50, "currency_code": "GBP", "availability": "in_stock"}, {"weight_g": 250, "grind_type": "Filter", "price_gbp": 12.50, "currency_code": "GBP", "availability": "in_stock"}, {"weight_g": 250, "grind_type": "Espresso", "price_gbp": 12.50, "currency_code": "GBP", "availability": "in_stock"}, {"weight_g": 1000, "grind_type": "Whole Bean", "price_gbp": 42.00, "currency_code": "GBP", "availability": "in_stock"}], "decaf_flag": false, "confidence": 0.95, "reasoning_summary": "Complete extraction with all 7 core fields: specific name, multiple price variants with weights, origin country + region, process, light roast, varietal, and 4+ flavor notes."}',
    },

    # ── Example 2: Sparse page, many fields missing ───────────────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://another-roaster.co.uk/shop/colombia",
            page_text="""
Colombia Filter Roast

A smooth, chocolatey filter coffee from Colombia. Perfect for your morning brew.

£9.50 for 250g
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Colombia Filter Roast", "roaster_name": "", "origin_country": "Colombia", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": [], "process": "", "roast_level": "Filter Roast", "brew_suitability": ["filter"], "grind_options": [], "flavour_notes": ["chocolate"], "weights": [250], "price_variants": [{"weight_g": 250, "grind_type": "", "price_gbp": 9.50, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.50, "reasoning_summary": "Minimal extraction: product name, origin country, roast level, and one price variant. Missing process, varietal, and most flavor notes."}',
    },

    # ── Example 3: Not a coffee product page ─────────────────────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://example.com/about-us",
            page_text="""
About Our Roastery

We've been roasting coffee in London since 2010. Our team of passionate roasters work hard every day to bring you the best coffees from around the world. Visit us at our Shoreditch café.
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "", "roaster_name": "", "origin_country": "", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": [], "process": "", "roast_level": "", "brew_suitability": [], "grind_options": [], "flavour_notes": [], "weights": [], "price_variants": [], "decaf_flag": false, "confidence": 0.0, "reasoning_summary": "Page is about the company, not a product listing. No extractable product data found."}',
    },

    # ── Example 4: Multiple weight variants with grind grouping ────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://specialty-roaster.com/products/kenya-aa",
            page_text="""
Kenya AA Washed

Bright, vibrant Kenyan single-origin from the foothills of Mount Kenya.

Varietal: SL28
Process: Washed
Roast: Light
Tasting notes: blackcurrant, lemon, floral

Available sizes:
250g Whole Bean — £11.99
250g Filter Grind — £12.49
500g Whole Bean — £21.99
500g Espresso Grind — £22.99
1kg Whole Bean — £39.99

Brew: Filter and Espresso
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Kenya AA Washed", "roaster_name": "Specialty Roaster", "origin_country": "Kenya", "origin_region": "Mount Kenya", "farm_or_estate": "", "producer": "", "varietal": ["SL28"], "process": "Washed", "roast_level": "Light", "brew_suitability": ["filter", "espresso"], "grind_options": ["Whole Bean", "Filter Grind", "Espresso Grind"], "flavour_notes": ["blackcurrant", "lemon", "floral"], "weights": [250, 500, 1000], "price_variants": [{"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 11.99, "currency_code": "GBP", "availability": "unknown"}, {"weight_g": 250, "grind_type": "Filter Grind", "price_gbp": 12.49, "currency_code": "GBP", "availability": "unknown"}, {"weight_g": 500, "grind_type": "Whole Bean", "price_gbp": 21.99, "currency_code": "GBP", "availability": "unknown"}, {"weight_g": 500, "grind_type": "Espresso Grind", "price_gbp": 22.99, "currency_code": "GBP", "availability": "unknown"}, {"weight_g": 1000, "grind_type": "Whole Bean", "price_gbp": 39.99, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.90, "reasoning_summary": "Complete extraction with all 7 fields. Multiple price variants grouped by weight first (250g, 500g, 1kg), then by grind type. All core fields present."}',
    },

    # ── Example 5: Decaf with roast level ────────────────────────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://roaster.co.uk/decaf-ethiopia",
            page_text="""
Ethiopia Yirgacheffe Decaf Medium Roast

Swiss water processed decaffeinated Ethiopian single-origin.

Origin: Ethiopia, Yirgacheffe
Process: Decaf (Swiss Water)
Roast: Medium
Tasting notes: caramel, orange blossom, smooth

500g Whole Bean — £13.99 (In Stock)
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Ethiopia Yirgacheffe Decaf Medium Roast", "roaster_name": "", "origin_country": "Ethiopia", "origin_region": "Yirgacheffe", "farm_or_estate": "", "producer": "", "varietal": [], "process": "Decaf (Swiss Water)", "roast_level": "Medium", "brew_suitability": ["filter", "omni"], "grind_options": ["Whole Bean"], "flavour_notes": ["caramel", "orange blossom", "smooth"], "weights": [500], "price_variants": [{"weight_g": 500, "grind_type": "Whole Bean", "price_gbp": 13.99, "currency_code": "GBP", "availability": "in_stock"}], "decaf_flag": true, "confidence": 0.75, "reasoning_summary": "Good extraction with 6 of 7 core fields. Decaf flag set. Missing roaster name and varietal, but origin, process, roast, price, and flavors present."}',
    },

    # ── Example 6: Seasonal/Limited Edition with harvest year ─────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://craft-roaster.co.uk/seasonal/colombia-2024",
            page_text="""
Colombia Geisha 2024 Harvest Limited Edition

Ultra-rare Geisha varietal from Colombia's Huila region. Limited to 100 bags.

Harvest: 2024
Varietal: Geisha
Process: Anaerobic Fermentation
Roast: Light
Flavor: floral, jasmine, honey, blueberry
Region: Huila
Farm: La Esperanza Cooperative

250g — £28.99 SOLD OUT
1kg — £99.99 Pre-order
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Colombia Geisha 2024 Harvest Limited Edition", "roaster_name": "Craft Roaster", "origin_country": "Colombia", "origin_region": "Huila", "farm_or_estate": "La Esperanza Cooperative", "producer": "La Esperanza Cooperative", "varietal": ["Geisha"], "process": "Anaerobic Fermentation", "roast_level": "Light", "brew_suitability": ["filter", "espresso"], "grind_options": [], "flavour_notes": ["floral", "jasmine", "honey", "blueberry"], "weights": [250, 1000], "price_variants": [{"weight_g": 250, "grind_type": "", "price_gbp": 28.99, "currency_code": "GBP", "availability": "out_of_stock"}, {"weight_g": 1000, "grind_type": "", "price_gbp": 99.99, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.92, "reasoning_summary": "Complete extraction with all 7 fields present. Seasonal/limited edition with explicit harvest year and ultra-rare varietal. Some variants pre-order or sold out."}',
    },

    # ── Example 7: Subscription/Bulk pricing (unusual structure) ──────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://subscription-roaster.co.uk/espresso-subscription",
            page_text="""
Monthly Espresso Subscription

Get freshly roasted espresso delivered monthly.

Featured This Month: Brazilian Santos Dark Roast

This month's selection: Brazilian Santos, Dark Roast, perfect for espresso.
Tasting notes: chocolate, caramel, nutty
Subscription options:
1kg per month — £18/month (subscribe)
2kg per month — £33/month (subscribe)
One-time purchase: 1kg — £22.99, 2kg — £42.99
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Brazilian Santos Dark Roast", "roaster_name": "", "origin_country": "Brazil", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": [], "process": "", "roast_level": "Dark Roast", "brew_suitability": ["espresso"], "grind_options": [], "flavour_notes": ["chocolate", "caramel", "nutty"], "weights": [1000, 2000], "price_variants": [{"weight_g": 1000, "grind_type": "", "price_gbp": 22.99, "currency_code": "GBP", "availability": "unknown"}, {"weight_g": 2000, "grind_type": "", "price_gbp": 42.99, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.65, "reasoning_summary": "Moderate extraction with 5 of 7 core fields. Used one-time prices (not subscription rates). Missing process and varietal information. Subscription context noted but standard prices preferred."}',
    },

    # ── Example 8: Generic name (penalty applied) ────────────────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://budget-coffee.co.uk/our-blend",
            page_text="""
Our Signature Coffee Blend

Our coffee is a smooth, balanced blend perfect for everyday brewing.

Price: £8.99 for 250g

Smooth, balanced, easy to drink. Great for filter and espresso.
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Our Signature Coffee Blend", "roaster_name": "", "origin_country": "", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": [], "process": "", "roast_level": "", "brew_suitability": ["filter", "espresso"], "grind_options": [], "flavour_notes": ["smooth", "balanced"], "weights": [250], "price_variants": [{"weight_g": 250, "grind_type": "", "price_gbp": 8.99, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.25, "reasoning_summary": "Minimal extraction with generic name ("Our Blend") incurring -0.20 penalty. Only 2 core fields present (price + vague flavorless). No origin, process, roast, or varietal information."}',
    },

    # ── Example 9: Multi-origin blend with multiple varietals ────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://specialty.co.uk/east-african-blend",
            page_text="""
East African Harmony Blend

A carefully balanced blend of coffees from Kenya, Ethiopia, and Uganda.

Kenya (SL28) 40%
Ethiopia (Heirloom) 40%
Uganda (Wush Wush) 20%

Process: Fully Washed
Roast: Medium
Tasting notes: berries, chocolate, balanced, clean

250g — £10.99
500g — £19.99 (In Stock)
1kg — £34.99

Grind: Whole Bean
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "East African Harmony Blend", "roaster_name": "", "origin_country": "Kenya, Ethiopia, Uganda", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": ["SL28", "Heirloom", "Wush Wush"], "process": "Fully Washed", "roast_level": "Medium", "brew_suitability": ["filter", "omni"], "grind_options": ["Whole Bean"], "flavour_notes": ["berries", "chocolate", "balanced", "clean"], "weights": [250, 500, 1000], "price_variants": [{"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 10.99, "currency_code": "GBP", "availability": "unknown"}, {"weight_g": 500, "grind_type": "Whole Bean", "price_gbp": 19.99, "currency_code": "GBP", "availability": "in_stock"}, {"weight_g": 1000, "grind_type": "Whole Bean", "price_gbp": 34.99, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.85, "reasoning_summary": "Good extraction with 6 of 7 fields (missing single origin country—multi-origin blend). All other core fields present with multiple varietals and clear prices."}',
    },

    # ── Example 10: Unusual packaging (bags, tins, capsules) ───────────────
    {
        "role": "user",
        "content": USER_TEMPLATE.format(
            url="https://luxury-roaster.co.uk/premium-tin",
            page_text="""
Brazilian Bourbon Single-Origin Premium Tin

Specialty coffee in a luxury gift tin.

From the Minas Gerais region of Brazil, these beans are roasted to a medium-dark level.

Varietal: Bourbon
Process: Pulped Natural
Roast: Medium-Dark
Flavor: chocolate, almond, subtle spice

Packaging: Luxury tin (200g)
Price: £16.99 per tin

Limited availability — currently 3 tins in stock.
""",
        ),
    },
    {
        "role": "assistant",
        "content": '{"coffee_name": "Brazilian Bourbon Single-Origin Premium Tin", "roaster_name": "Luxury Roaster", "origin_country": "Brazil", "origin_region": "Minas Gerais", "farm_or_estate": "", "producer": "", "varietal": ["Bourbon"], "process": "Pulped Natural", "roast_level": "Medium-Dark", "brew_suitability": ["espresso", "omni"], "grind_options": [], "flavour_notes": ["chocolate", "almond", "spice"], "weights": [200], "price_variants": [{"weight_g": 200, "grind_type": "", "price_gbp": 16.99, "currency_code": "GBP", "availability": "in_stock"}], "decaf_flag": false, "confidence": 0.85, "reasoning_summary": "Good extraction with 6 of 7 core fields. Luxury tin packaging noted (unusual format). Missing producer/farm details but all other fields present. Limited stock indicated."}',
    },
]

# ─── Input preprocessing ──────────────────────────────────────────────────────

MAX_INPUT_CHARS = 12_000   # ~3k tokens — keep well within context limits
MAX_OUTPUT_TOKENS = 1_500  # slightly more for expanded schema

def get_system_prompt(domain_context: str = "unknown", historical_pattern: str = "") -> str:
    """
    Build the system prompt with optional domain context and historical patterns.

    Args:
        domain_context: "specialty", "commodity", or "unknown" (inferred roaster type)
        historical_pattern: Summary of previous extractions (e.g., "typically has: weight, price, process")

    Returns:
        Formatted system prompt with context injected
    """
    if not historical_pattern:
        historical_pattern = "No historical pattern data available (first extraction for this domain)"

    if domain_context not in ("specialty", "commodity", "unknown"):
        domain_context = "unknown"

    # Use safe string replacement to avoid format() issues with JSON braces
    prompt = SYSTEM_PROMPT_TEMPLATE.replace("{domain_type}", domain_context)
    prompt = prompt.replace("{historical_pattern}", historical_pattern)
    return prompt

def build_messages(page_text: str, url: str, domain_context: str = "", historical_pattern: str = "") -> list[dict]:
    """
    Build the messages list for the Anthropic API call.
    Includes system prompt with context, few-shot examples, then the live user message.

    Args:
        page_text: Cleaned text content of the page
        url: Source URL
        domain_context: Optional roaster type hint
        historical_pattern: Optional summary of previous extractions

    Returns:
        List of message dicts ready for Anthropic API
    """
    # Truncate if too long — prefer to truncate from the middle to preserve
    # the header (title, price) and footer (notes, variants) which tend to
    # carry the most useful signals
    text = page_text.strip()
    if len(text) > MAX_INPUT_CHARS:
        half = MAX_INPUT_CHARS // 2
        text = text[:half] + "\n\n[...content truncated...]\n\n" + text[-half:]

    live_message = {
        "role": "user",
        "content": USER_TEMPLATE.format(url=url, page_text=text),
    }

    return [*FEW_SHOT_EXAMPLES, live_message]
