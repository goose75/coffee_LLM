"""
ExtractionPayload — the canonical intermediate schema.

Every extraction strategy (schema.org, HTML rules, LLM) MUST return an
ExtractionPayload. This is stored verbatim in raw_extractions.extracted_payload
as JSONB, and consumed by the normalisation pass in Phase 7.

Design rules:
  - All string fields default to "" (not None) so downstream code can always
    do `.strip()` without None checks.
  - All list fields default to [].
  - price_variants is a list — one entry per weight/grind combination found.
  - confidence is a 0.0–1.0 float set by each parser.
  - reasoning_summary is a brief human-readable explanation (shown to reviewers).
  - Raw values are preserved exactly as found — normalisation is a later concern.

The Pydantic model validates on construction. Parsers call `.model_validate()`
on their raw dict outputs, catching schema violations before any DB write.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class PriceVariantPayload(BaseModel):
    """One parsed price point: a weight + grind + price triplet."""

    weight_g: int | None = None
    grind_type: str = ""          # raw string, e.g. "Whole Bean"
    price_gbp: float = 0.0
    currency_code: str = "GBP"
    availability: str = "unknown"  # "in_stock" | "out_of_stock" | "unknown"

    @field_validator("price_gbp", mode="before")
    @classmethod
    def coerce_price(cls, v):
        try:
            return float(str(v).replace("£", "").replace(",", "").strip())
        except (ValueError, TypeError):
            return 0.0

    @field_validator("weight_g", mode="before")
    @classmethod
    def coerce_weight(cls, v):
        if v is None:
            return None
        try:
            return int(float(str(v)))
        except (ValueError, TypeError):
            return None


class ExtractionPayload(BaseModel):
    """
    Canonical intermediate schema produced by every extraction strategy.

    Stored as JSONB in raw_extractions.extracted_payload.
    All string fields are "" by default; all list fields are [] by default.
    """

    # ── Core identity ─────────────────────────────────────────────────────
    coffee_name: str = ""
    roaster_name: str = ""

    # ── Origin ───────────────────────────────────────────────────────────
    origin_country: str = ""
    origin_region: str = ""
    farm_or_estate: str = ""
    producer: str = ""

    # ── Cultivar & process ────────────────────────────────────────────────
    varietal: list[str] = Field(default_factory=list)
    process: str = ""            # raw text, e.g. "Washed" or "Anaerobic Natural"
    roast_level: str = ""        # raw text, e.g. "Light Roast"

    # ── Brew suitability ──────────────────────────────────────────────────
    brew_suitability: list[str] = Field(default_factory=list)  # ["espresso", "filter"]
    grind_options: list[str] = Field(default_factory=list)     # raw strings from source

    # ── Sensory ───────────────────────────────────────────────────────────
    flavour_notes: list[str] = Field(default_factory=list)

    # ── Pricing ───────────────────────────────────────────────────────────
    weights: list[int] = Field(default_factory=list)  # distinct weight_g values
    price_variants: list[PriceVariantPayload] = Field(default_factory=list)

    # ── Flags ─────────────────────────────────────────────────────────────
    decaf_flag: bool = False

    # ── Quality ───────────────────────────────────────────────────────────
    confidence: float = 0.0       # 0.0–1.0, set by the parser
    reasoning_summary: str = ""   # brief explanation for reviewers

    # ── Source metadata (not normalised, purely informational) ────────────
    source_url: str = ""
    raw_title: str = ""
    raw_description: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (ValueError, TypeError):
            return 0.0

    @field_validator("varietal", "brew_suitability", "grind_options", "flavour_notes", mode="before")
    @classmethod
    def coerce_str_list(cls, v):
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return []

    @field_validator("weights", mode="before")
    @classmethod
    def coerce_weights(cls, v):
        if isinstance(v, list):
            result = []
            for i in v:
                try:
                    result.append(int(float(i)))
                except (ValueError, TypeError):
                    pass
            return result
        return []

    @model_validator(mode="after")
    def sync_weights_from_variants(self) -> "ExtractionPayload":
        """
        If weights list is empty but price_variants have weight_g values,
        populate weights from variants for convenience.
        """
        if not self.weights and self.price_variants:
            seen: set[int] = set()
            for pv in self.price_variants:
                if pv.weight_g is not None and pv.weight_g not in seen:
                    seen.add(pv.weight_g)
                    self.weights.append(pv.weight_g)
        return self

    def completeness_score(self) -> float:
        """
        0.0–1.0 estimate of how complete this extraction is.
        Used to set confidence when the parser can't compute it directly.
        """
        scored = [
            bool(self.coffee_name),
            bool(self.origin_country),
            bool(self.origin_region),
            bool(self.process),
            bool(self.roast_level),
            bool(self.varietal),
            bool(self.flavour_notes),
            bool(self.price_variants),
            bool(self.farm_or_estate or self.producer),
        ]
        return round(sum(scored) / len(scored), 2)

    def to_db_dict(self) -> dict:
        """Serialise to a plain dict for JSONB storage."""
        return self.model_dump(mode="json")


class ExtractionResult(BaseModel):
    """
    Return type for every parser strategy.
    Wraps the payload with validation metadata.
    """

    payload: ExtractionPayload
    validation_status: str = "valid"   # "valid" | "invalid" | "partial"
    validation_errors: list[str] = Field(default_factory=list)
    extraction_method: str = ""        # populated by the caller

    @classmethod
    def invalid(cls, method: str, errors: list[str]) -> "ExtractionResult":
        return cls(
            payload=ExtractionPayload(),
            validation_status="invalid",
            validation_errors=errors,
            extraction_method=method,
        )

    @classmethod
    def partial(cls, payload: ExtractionPayload, method: str, errors: list[str]) -> "ExtractionResult":
        return cls(
            payload=payload,
            validation_status="partial",
            validation_errors=errors,
            extraction_method=method,
        )
