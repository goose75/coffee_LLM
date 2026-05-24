"""
Domain Context Injection for LLM v2.0.0 Prompt

Provides roaster classification and historical pattern extraction
for improved LLM extraction confidence and calibration.
"""

from typing import Optional
from enum import Enum
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.models.store import Store
from app.models.raw_extraction import RawExtraction


class RoasterType(str, Enum):
    """Classification of roaster business model"""
    SPECIALTY = "specialty"
    COMMODITY = "commodity"
    UNKNOWN = "unknown"


def infer_domain_type(store_name: str, homepage_content: str = "") -> RoasterType:
    """
    Classify roaster as specialty, commodity, or unknown.

    Specialty indicators:
    - Single-origin, single estate, specialty grade, third-wave, pour-over
    - Craft, artisan, micro-batch, small batch
    - Tasting notes, flavor profiles, origin stories
    - Price point: typically £8-20+ per 250g

    Commodity indicators:
    - Bulk ordering, wholesale, discount, budget
    - Instant coffee, standard blend, generic
    - Large volume discounts, catering packs
    - Price point: typically £2-5 per 250g

    Args:
        store_name: Store/roaster name (e.g., "Has Bean", "Starbucks")
        homepage_content: Raw HTML or text from homepage (optional)

    Returns:
        RoasterType: SPECIALTY, COMMODITY, or UNKNOWN
    """

    # Keywords indicating specialty roasters
    specialty_keywords = {
        "single-origin",
        "single origin",
        "specialty",
        "specialty grade",
        "third-wave",
        "third wave",
        "pour-over",
        "pour over",
        "craft",
        "artisan",
        "microlot",
        "micro-lot",
        "micro lot",
        "small batch",
        "small-batch",
        "single estate",
        "estate coffee",
        "direct trade",
        "fair trade",
        "organic",
        "natural process",
        "washed process",
        "fermented",
        "tasting notes",
        "flavor profile",
        "origin story",
        "specialty roaster",
        "third-wave coffee",
        "specialty coffee",
    }

    # Keywords indicating commodity/budget roasters
    commodity_keywords = {
        "bulk",
        "wholesale",
        "discount",
        "budget",
        "cheap",
        "catering",
        "commercial",
        "industrial",
        "instant coffee",
        "instant",
        "standard blend",
        "commodity",
        "volume discount",
        "bulk order",
        "office coffee",
        "break room",
    }

    # Combine store name and homepage content
    combined_text = (store_name + " " + homepage_content).lower()

    # Count keyword matches
    specialty_score = sum(1 for kw in specialty_keywords if kw in combined_text)
    commodity_score = sum(1 for kw in commodity_keywords if kw in combined_text)

    # Decision logic
    if specialty_score >= 2:
        return RoasterType.SPECIALTY
    elif commodity_score >= 2:
        return RoasterType.COMMODITY
    else:
        return RoasterType.UNKNOWN


async def get_historical_patterns(
    session: AsyncSession,
    store_id: str,
    limit: int = 5,
) -> dict:
    """
    Extract patterns from last N successful extractions from a store.

    Patterns tracked:
    - Typical fields present (origin, process, roast, etc.)
    - Average confidence achieved
    - Common errors or missing fields
    - Typical price range

    Used in LLM prompt as context: "This domain typically has: origin,
    process, roast (from 5 previous extractions)"

    Args:
        session: AsyncSession for database queries
        store_id: UUID of store to analyze
        limit: Number of previous extractions to examine

    Returns:
        dict: Historical pattern summary for prompt injection
    """

    # Query recent successful extractions
    stmt = (
        select(RawExtraction)
        .where(
            and_(
                RawExtraction.store_id == store_id,
                RawExtraction.validation_status.in_(["valid", "partial"]),
            )
        )
        .order_by(desc(RawExtraction.created_at))
        .limit(limit)
    )

    result = await session.execute(stmt)
    recent_extractions = result.scalars().all()

    if not recent_extractions:
        return {
            "typical_fields": [],
            "typical_confidence": [],
            "typical_price_range": "unknown",
            "common_missing_fields": [],
        }

    # Analyze patterns
    patterns = {
        "typical_fields": [],
        "typical_confidence": [],
        "typical_price_range": "",
        "common_missing_fields": [],
    }

    field_presence = {
        "origin": 0,
        "process": 0,
        "roast": 0,
        "varietal": 0,
        "flavor_notes": 0,
        "weight": 0,
        "price": 0,
    }

    confidence_scores = []
    price_values = []

    for extraction in recent_extractions:
        payload = extraction.extracted_payload

        # Track field presence
        if payload.get("origin_country"):
            field_presence["origin"] += 1
        if payload.get("process"):
            field_presence["process"] += 1
        if payload.get("roast_level"):
            field_presence["roast"] += 1
        if payload.get("varietal"):
            field_presence["varietal"] += 1
        if payload.get("flavour_notes"):
            field_presence["flavor_notes"] += 1

        # Track price variants
        if payload.get("price_variants"):
            field_presence["weight"] += 1
            field_presence["price"] += 1

            # Extract price range
            for variant in payload.get("price_variants", []):
                if variant.get("price_gbp"):
                    price_values.append(variant["price_gbp"])

        # Track confidence
        confidence = float(payload.get("confidence", 0))
        confidence_scores.append(confidence)

    # Calculate prevalence
    extraction_count = len(recent_extractions)
    for field, count in field_presence.items():
        if count / extraction_count >= 0.6:  # Present in 60%+ of extractions
            patterns["typical_fields"].append(field)

    # Average confidence
    if confidence_scores:
        patterns["typical_confidence"] = [
            round(sum(confidence_scores) / len(confidence_scores), 2),
            round(min(confidence_scores), 2),
            round(max(confidence_scores), 2),
        ]

    # Price range
    if price_values:
        min_price = min(price_values)
        max_price = max(price_values)
        avg_price = sum(price_values) / len(price_values)

        if max_price - min_price < 5:
            patterns["typical_price_range"] = f"£{min_price:.2f}-£{max_price:.2f}"
        else:
            patterns["typical_price_range"] = f"£{min_price:.2f}-£{max_price:.2f} (varies by weight)"

    # Identify missing fields
    for field, count in field_presence.items():
        if count / extraction_count < 0.4:  # Missing in 60%+ of extractions
            patterns["common_missing_fields"].append(field)

    return patterns


def format_domain_context_prompt(
    domain_type: RoasterType,
    historical_patterns: dict,
    store_name: str = "",
) -> str:
    """
    Format domain context for injection into LLM v2.0.0 prompt.

    Example output:
    "Domain: specialty coffee roaster (Has Bean)
    Typical fields: origin, process, roast, varietal, flavor_notes
    Typical confidence: 0.78 (range 0.65-0.92 from 5 recent extractions)
    Typical price: £8.50-£15.99 per 250g
    Common missing: none"

    Args:
        domain_type: Inferred roaster type (specialty/commodity/unknown)
        historical_patterns: Pattern dict from get_historical_patterns()
        store_name: Name of store (for context)

    Returns:
        str: Formatted context string for prompt injection
    """

    lines = []

    # Domain classification
    domain_description = {
        RoasterType.SPECIALTY: "specialty coffee roaster (high-quality, single-origin focus)",
        RoasterType.COMMODITY: "commodity coffee supplier (volume-focused, budget pricing)",
        RoasterType.UNKNOWN: "coffee seller (unclear market positioning)",
    }

    store_suffix = f" ({store_name})" if store_name else ""
    lines.append(f"Domain type: {domain_description[domain_type]}{store_suffix}")

    # Typical fields
    if historical_patterns.get("typical_fields"):
        fields = ", ".join(historical_patterns["typical_fields"])
        lines.append(f"Typical fields present: {fields}")

    # Typical confidence from history
    if historical_patterns.get("typical_confidence"):
        conf = historical_patterns["typical_confidence"]
        if len(conf) == 3:
            lines.append(
                f"Historical confidence: {conf[0]} avg "
                f"(range {conf[1]}-{conf[2]} from recent extractions)"
            )
        else:
            lines.append(f"Historical confidence: {conf[0]}")

    # Price range
    if historical_patterns.get("typical_price_range"):
        lines.append(f"Typical price range: {historical_patterns['typical_price_range']}")

    # Missing fields to watch for
    if historical_patterns.get("common_missing_fields"):
        missing = ", ".join(historical_patterns["common_missing_fields"])
        lines.append(f"Commonly missing fields: {missing}")
    else:
        if historical_patterns.get("typical_fields"):
            lines.append("Commonly missing fields: none (consistent extraction)")

    return "\n".join(lines)


def inject_domain_context_into_prompt(
    base_prompt: str,
    domain_context: str,
) -> str:
    """
    Inject domain context into LLM v2.0.0 prompt.

    Finds the marker "{{DOMAIN_CONTEXT}}" in the prompt and replaces
    it with formatted domain context.

    Args:
        base_prompt: v2.0.0 prompt template with {{DOMAIN_CONTEXT}} marker
        domain_context: Formatted context from format_domain_context_prompt()

    Returns:
        str: Prompt with domain context injected
    """

    if "{{DOMAIN_CONTEXT}}" in base_prompt:
        return base_prompt.replace("{{DOMAIN_CONTEXT}}", domain_context)

    # Fallback: inject before "Key rules:" section if marker not found
    if "Key rules:" in base_prompt:
        return base_prompt.replace(
            "Key rules:",
            f"{domain_context}\n\nKey rules:"
        )

    # Last resort: inject after system message opening
    return base_prompt.replace(
        "You are extracting",
        f"You are extracting\n\n{domain_context}\n"
    )


# Example usage in LLM parser:
#
# async def extract_with_domain_context(
#     self, html_bytes: bytes, url: str, store_id: str
# ) -> ExtractionResult:
#     """Enhanced extract with domain context injection"""
#
#     # Get domain type and historical patterns
#     store = await session.get(Store, store_id)
#     domain_type = infer_domain_type(store.name, store.homepage_content)
#     patterns = await get_historical_patterns(session, store_id)
#
#     # Format context
#     domain_context = format_domain_context_prompt(
#         domain_type, patterns, store.name
#     )
#
#     # Inject into prompt
#     prompt_v2 = await get_system_prompt("v2.0.0")
#     enhanced_prompt = inject_domain_context_into_prompt(
#         prompt_v2, domain_context
#     )
#
#     # Extract with enhanced prompt
#     return await self.llm_parser.extract(
#         html_bytes, url,
#         system_prompt_override=enhanced_prompt
#     )
