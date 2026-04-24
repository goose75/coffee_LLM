"""
LLM extraction prompt templates.

Version: v1.0.0
Model target: claude-sonnet-4-20250514

Design philosophy:
  - System prompt establishes strict JSON-only mode with no preamble.
  - Schema is specified twice: once as a JSON template with inline comments,
    once as a field-by-field reference. Redundancy helps the model be precise.
  - Few-shot examples cover the three hardest cases:
      1. A product with all fields present (shows full output)
      2. A product with missing/unknown fields (shows graceful empty defaults)
      3. A product page that is NOT a coffee (shows zero-confidence refusal)
  - The model is told to set confidence=0.0 and return empty fields when it
    cannot confidently extract — never to hallucinate or guess.
  - Input is capped server-side before this prompt is used (see llm_parser.py).

Versioning:
  PROMPT_VERSION is stored in raw_extractions.prompt_version so prompt
  changes can be tracked across the dataset.
"""

PROMPT_VERSION = "v1.0.0"

# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a specialist coffee data extraction API. Your sole function is to extract structured data from coffee product page text and return it as valid JSON.

CRITICAL RULES — follow these exactly:
1. Respond with ONLY valid JSON. No markdown. No code fences. No explanation. No preamble. Just the JSON object.
2. Never invent or guess field values. If a field is not clearly stated in the text, use "" for strings, [] for arrays, false for booleans, and 0.0 for confidence when returning a complete failure.
3. Use the EXACT field names and types specified in the schema below.
4. If the page is not about a coffee product, return the minimal JSON with confidence set to 0.0.
5. For confidence: 0.9+ means nearly all fields found with high certainty, 0.7-0.89 means most fields found, 0.5-0.69 means partial extraction, below 0.5 means very sparse data.

OUTPUT SCHEMA — return exactly this structure:
{
  "coffee_name": "string — the specific product name, not the roaster name",
  "roaster_name": "string — the company selling or roasting this coffee",
  "origin_country": "string — single country of origin, e.g. Ethiopia",
  "origin_region": "string — sub-country region, e.g. Yirgacheffe, Huila, Kirinyaga",
  "farm_or_estate": "string — specific farm, cooperative, or estate name if stated",
  "producer": "string — individual producer or washing station operator if named",
  "varietal": ["array of strings — coffee cultivar names, e.g. Heirloom, SL28, Gesha"],
  "process": "string — processing method in the source's own words, e.g. Washed, Natural, Anaerobic",
  "roast_level": "string — roast descriptor in source's words, e.g. Light, Medium, Filter Roast",
  "brew_suitability": ["array — methods this coffee is suited for, from: espresso, filter, omni, cafetiere, aeropress, pour_over"],
  "grind_options": ["array — grind options available, in source's words, e.g. Whole Bean, Espresso, Filter"],
  "flavour_notes": ["array of strings — tasting notes exactly as written, each note as a separate item"],
  "weights": [array of integers — available weights in grams, e.g. 250, 1000],
  "price_variants": [
    {
      "weight_g": integer or null,
      "grind_type": "string — grind option for this variant",
      "price_gbp": float,
      "currency_code": "GBP",
      "availability": "in_stock or out_of_stock or unknown"
    }
  ],
  "decaf_flag": false,
  "confidence": 0.0,
  "reasoning_summary": "string — one sentence explaining what was found and any gaps"
}

FIELD GUIDANCE:
- coffee_name: extract the specific coffee's name (e.g. "Ethiopia Yirgacheffe Konga"), not the roaster
- flavour_notes: split comma/and-separated notes into individual array items
- varietal: known varietals include Heirloom, Bourbon, Gesha, SL28, SL34, Castillo, Caturra, Typica, Pacamara, etc.
- weights: convert kg to grams (1kg = 1000g), extract all available sizes
- price_variants: one entry per unique weight/grind combination; omit if no price data found
- brew_suitability: infer from context ("espresso roast" → espresso, "filter coffee" → filter, "works for all methods" → omni)
- reasoning_summary: max 2 sentences, useful to a human reviewer
"""

# ─── User message template ────────────────────────────────────────────────────

USER_TEMPLATE = """\
Extract coffee product data from the following page text.

SOURCE URL: {url}

PAGE TEXT:
{page_text}
"""

# ─── Few-shot examples ────────────────────────────────────────────────────────
# These are injected as conversation turns before the live user message
# to demonstrate correct output format and edge-case handling.

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
        "content": '{"coffee_name": "Ethiopia Yirgacheffe Konga Washed", "roaster_name": "Example Roaster", "origin_country": "Ethiopia", "origin_region": "Yirgacheffe", "farm_or_estate": "Konga Cooperative", "producer": "Konga Cooperative", "varietal": ["Heirloom", "JARC 74110"], "process": "Washed", "roast_level": "Light", "brew_suitability": ["filter", "espresso"], "grind_options": ["Whole Bean", "Filter", "Espresso", "Pour Over"], "flavour_notes": ["jasmine", "bergamot", "lemon curd", "white peach"], "weights": [250, 1000], "price_variants": [{"weight_g": 250, "grind_type": "Whole Bean", "price_gbp": 12.50, "currency_code": "GBP", "availability": "in_stock"}, {"weight_g": 1000, "grind_type": "Whole Bean", "price_gbp": 42.00, "currency_code": "GBP", "availability": "in_stock"}], "decaf_flag": false, "confidence": 0.92, "reasoning_summary": "All core fields extracted from clearly structured product page. Two price variants found; grind options listed explicitly."}',
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
        "content": '{"coffee_name": "Colombia Filter Roast", "roaster_name": "", "origin_country": "Colombia", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": [], "process": "", "roast_level": "Filter Roast", "brew_suitability": ["filter"], "grind_options": [], "flavour_notes": ["chocolate"], "weights": [250], "price_variants": [{"weight_g": 250, "grind_type": "", "price_gbp": 9.50, "currency_code": "GBP", "availability": "unknown"}], "decaf_flag": false, "confidence": 0.52, "reasoning_summary": "Limited product information available; origin country and name extracted but no farm, varietal, or process details were present in the text."}',
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
        "content": '{"coffee_name": "", "roaster_name": "", "origin_country": "", "origin_region": "", "farm_or_estate": "", "producer": "", "varietal": [], "process": "", "roast_level": "", "brew_suitability": [], "grind_options": [], "flavour_notes": [], "weights": [], "price_variants": [], "decaf_flag": false, "confidence": 0.0, "reasoning_summary": "Page is an about/company page, not a coffee product listing. No extractable product data found."}',
    },
]

# ─── Input preprocessing ──────────────────────────────────────────────────────

MAX_INPUT_CHARS = 12_000   # ~3k tokens — keep well within context limits
MAX_OUTPUT_TOKENS = 1_200  # enough for a full JSON response

def build_messages(page_text: str, url: str) -> list[dict]:
    """
    Build the messages list for the Anthropic API call.
    Includes few-shot examples then the live user message.
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
