"""
CoffeeNormaliser — converts raw extraction strings to controlled vocabulary values.

Two-stage normalisation pipeline:
  Stage 1 — DB-backed mappings (NormalisationMapping table)
    • Exact case-insensitive lookup against operator-curated entries
    • Highest trust: manually verified or LLM-suggested + confirmed
    • If found, returns immediately (DB wins over rules)

  Stage 2 — Rule-based fallback (rules.py pattern tables)
    • Regex patterns applied in priority order
    • Lower trust: automated, may miss unusual wordings
    • Unknown returned if nothing matches

Core principle: raw values are ALWAYS preserved alongside normalised values.
The normaliser never replaces source text — it appends a parallel normalised value.

Usage:
    normaliser = CoffeeNormaliser(session)
    result = await normaliser.normalise_roast("Light filter roast")
    # → NormalisationResult(raw="Light filter roast", normalised="light",
    #                        confidence=0.95, source="rule")

    bean_result = await normaliser.normalise_bean_listing(listing)
    # → NormalisedListing with all fields populated

The normaliser is async because Stage 1 DB lookups are async. Stage 2 rules
are sync, so the normaliser can be used in a sync context by calling the
_apply_rules() methods directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GrindType, MappingType, Process, RoastLevel
from app.models.resolution import NormalisationMapping
from app.services.normalisation.rules import (
    COUNTRY_RULES,
    GRIND_RULES,
    PROCESS_RULES,
    REGION_LOOKUP,
    ROAST_RULES,
    parse_weight_g,
    parse_multiple_weights,
    snap_to_standard_weight,
)

log = logging.getLogger(__name__)


@dataclass
class NormalisationResult:
    """
    Result of normalising a single field value.
    Carries both raw and normalised values — raw is never lost.
    """
    raw: str                          # Original text, unchanged
    normalised: str                   # Controlled vocabulary value
    confidence: float = 1.0           # 0.0–1.0
    source: str = "rule"              # "db" | "rule" | "default"
    mapping_type: str = ""            # For DB persistence

    @property
    def is_unknown(self) -> bool:
        return self.normalised == "unknown" or self.normalised == ""

    def __str__(self) -> str:
        return f"{self.raw!r} → {self.normalised!r} (conf={self.confidence:.2f}, src={self.source})"


@dataclass
class NormalisedListing:
    """
    Fully normalised representation of a bean listing's key fields.
    Preserves all raw values alongside normalised ones.
    """
    # Roast
    roast_level_raw: str = ""
    roast_level: str = "unknown"
    roast_confidence: float = 0.0

    # Grind
    grind_type_raw: str = ""
    grind_type: str = "unknown"
    grind_confidence: float = 0.0

    # Process
    process_raw: str = ""
    process: str = "unknown"
    process_confidence: float = 0.0

    # Origin
    origin_country_raw: str = ""
    origin_country: str = ""
    country_confidence: float = 0.0

    origin_region_raw: str = ""
    origin_region: str = ""
    region_confidence: float = 0.0

    # Weight
    weight_raw: str = ""
    weight_g: Optional[int] = None

    # Errors / warnings from normalisation
    warnings: list[str] = field(default_factory=list)


class CoffeeNormaliser:
    """
    Normalises raw coffee attribute strings to controlled vocabulary values.

    Combines DB-backed mappings (operator-curated) with rule-based fallbacks.
    Instantiate once per request with a DB session; it caches DB lookups.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._cache: dict[tuple[str, str], NormalisationResult | None] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    async def normalise_roast(self, raw: str) -> NormalisationResult:
        """Map raw roast text to RoastLevel enum value."""
        return await self._normalise(
            raw=raw,
            mapping_type=MappingType.roast_level,
            rules=ROAST_RULES,
            default="unknown",
            valid_values={e.value for e in RoastLevel},
        )

    async def normalise_grind(self, raw: str) -> NormalisationResult:
        """Map raw grind text to GrindType enum value."""
        return await self._normalise(
            raw=raw,
            mapping_type=MappingType.grind,
            rules=GRIND_RULES,
            default="unknown",
            valid_values={e.value for e in GrindType},
        )

    async def normalise_process(self, raw: str) -> NormalisationResult:
        """Map raw process text to Process enum value."""
        return await self._normalise(
            raw=raw,
            mapping_type=MappingType.process,
            rules=PROCESS_RULES,
            default="unknown",
            valid_values={e.value for e in Process},
        )

    async def normalise_country(self, raw: str) -> NormalisationResult:
        """Normalise raw country text to ISO-standard country name."""
        return await self._normalise(
            raw=raw,
            mapping_type=MappingType.country,
            rules=COUNTRY_RULES,
            default="",
            valid_values=None,  # Open vocabulary — no enum constraint
        )

    async def normalise_region(self, raw: str) -> NormalisationResult:
        """
        Normalise raw region text to canonical region name.
        Also attempts to derive origin_country if region is recognised.
        """
        # Stage 1: DB lookup
        db_result = await self._db_lookup(raw, MappingType.region.value)
        if db_result is not None:
            return db_result

        # Stage 2: region lookup table
        key = raw.strip().lower()
        if key in REGION_LOOKUP:
            canonical_region, _ = REGION_LOOKUP[key]
            return NormalisationResult(
                raw=raw,
                normalised=canonical_region,
                confidence=0.95,
                source="rule",
                mapping_type=MappingType.region.value,
            )

        # Partial match — find region names that appear in raw text
        for key_candidate, (region_name, _) in REGION_LOOKUP.items():
            if key_candidate in key or key in key_candidate:
                return NormalisationResult(
                    raw=raw,
                    normalised=region_name,
                    confidence=0.75,
                    source="rule",
                    mapping_type=MappingType.region.value,
                )

        return NormalisationResult(
            raw=raw,
            normalised=raw.strip().title() if raw.strip() else "",
            confidence=0.4,
            source="default",
            mapping_type=MappingType.region.value,
        )

    def normalise_weight(self, raw: str) -> NormalisationResult:
        """
        Parse weight string to integer grams.
        Sync — no DB lookup needed for weights.
        """
        weight_g = parse_weight_g(raw)
        if weight_g is not None:
            snapped = snap_to_standard_weight(weight_g)
            snapped_note = f" (snapped from {weight_g}g)" if snapped != weight_g else ""
            return NormalisationResult(
                raw=raw,
                normalised=str(snapped),
                confidence=0.99 if not snapped_note else 0.90,
                source="rule",
                mapping_type="weight",
            )

        return NormalisationResult(
            raw=raw,
            normalised="",
            confidence=0.0,
            source="default",
            mapping_type="weight",
        )

    def parse_weights(self, raw: str) -> list[int]:
        """Extract all weights from a multi-weight string."""
        return parse_multiple_weights(raw)

    async def normalise_bean_listing(
        self,
        roast_raw: str = "",
        grind_raw: str = "",
        process_raw: str = "",
        country_raw: str = "",
        region_raw: str = "",
        weight_raw: str = "",
    ) -> NormalisedListing:
        """
        Normalise all fields for a bean listing in one call.
        Returns a NormalisedListing with parallel raw + normalised fields.
        """
        result = NormalisedListing(
            roast_level_raw=roast_raw,
            grind_type_raw=grind_raw,
            process_raw=process_raw,
            origin_country_raw=country_raw,
            origin_region_raw=region_raw,
            weight_raw=weight_raw,
        )

        if roast_raw:
            r = await self.normalise_roast(roast_raw)
            result.roast_level = r.normalised
            result.roast_confidence = r.confidence

        if grind_raw:
            r = await self.normalise_grind(grind_raw)
            result.grind_type = r.normalised
            result.grind_confidence = r.confidence

        if process_raw:
            r = await self.normalise_process(process_raw)
            result.process = r.normalised
            result.process_confidence = r.confidence

        if country_raw:
            r = await self.normalise_country(country_raw)
            result.origin_country = r.normalised
            result.country_confidence = r.confidence

        if region_raw:
            r = await self.normalise_region(region_raw)
            result.origin_region = r.normalised
            result.region_confidence = r.confidence
            # Fill country from region if country was blank
            if not result.origin_country and region_raw.strip().lower() in REGION_LOOKUP:
                _, derived_country = REGION_LOOKUP[region_raw.strip().lower()]
                result.origin_country = derived_country
                result.country_confidence = 0.8

        if weight_raw:
            r = self.normalise_weight(weight_raw)
            result.weight_g = int(r.normalised) if r.normalised else None

        return result

    # ── Mapping persistence helpers ───────────────────────────────────────────

    async def record_mapping(
        self,
        raw: str,
        normalised: str,
        mapping_type: MappingType,
        confidence: float = 1.0,
        source: str = "rule",
    ) -> NormalisationMapping:
        """
        Upsert a mapping into the normalisation_mappings table.
        Called when a rule produces a result not already in the DB.
        """
        existing = await self.session.execute(
            select(NormalisationMapping).where(
                NormalisationMapping.mapping_type == mapping_type,
                NormalisationMapping.raw_value == raw,
            )
        )
        mapping = existing.scalar_one_or_none()

        if mapping is None:
            mapping = NormalisationMapping(
                mapping_type=mapping_type,
                raw_value=raw,
                normalised_value=normalised,
                confidence_score=confidence,
                source=source,
            )
            self.session.add(mapping)
        else:
            # Only update if the new confidence is higher or source is more trusted
            source_rank = {"manual": 3, "db": 2, "rule": 1, "default": 0}
            if confidence > mapping.confidence_score or source_rank.get(source, 0) > source_rank.get(mapping.source, 0):
                mapping.normalised_value = normalised
                mapping.confidence_score = confidence
                mapping.source = source

        return mapping

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _normalise(
        self,
        raw: str,
        mapping_type: MappingType,
        rules: list,
        default: str,
        valid_values: set[str] | None,
    ) -> NormalisationResult:
        """Two-stage normalisation: DB lookup → rule application."""
        if not raw or not raw.strip():
            return NormalisationResult(
                raw=raw,
                normalised=default,
                confidence=0.0,
                source="default",
                mapping_type=mapping_type.value,
            )

        # Stage 1: DB lookup (cached per session)
        db_result = await self._db_lookup(raw, mapping_type.value)
        if db_result is not None:
            return db_result

        # Stage 2: Rule-based
        rule_result = self._apply_rules(raw, rules, mapping_type.value)
        if rule_result is not None:
            # Validate result is in the controlled vocabulary
            if valid_values and rule_result.normalised not in valid_values:
                log.warning(
                    "Rule produced '%s' for '%s' which is not in valid_values %s",
                    rule_result.normalised, raw, valid_values,
                )
                rule_result = NormalisationResult(
                    raw=raw,
                    normalised=default,
                    confidence=0.0,
                    source="default",
                    mapping_type=mapping_type.value,
                )
            return rule_result

        return NormalisationResult(
            raw=raw,
            normalised=default,
            confidence=0.0,
            source="default",
            mapping_type=mapping_type.value,
        )

    async def _db_lookup(self, raw: str, mapping_type_value: str) -> NormalisationResult | None:
        """Look up exact (case-insensitive) match in DB mappings."""
        cache_key = (raw.strip().lower(), mapping_type_value)
        if cache_key in self._cache:
            return self._cache[cache_key]

        stmt = select(NormalisationMapping).where(
            NormalisationMapping.mapping_type == mapping_type_value,
            NormalisationMapping.raw_value.ilike(raw.strip()),
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()

        if row is not None:
            result = NormalisationResult(
                raw=raw,
                normalised=row.normalised_value,
                confidence=row.confidence_score,
                source="db",
                mapping_type=mapping_type_value,
            )
            self._cache[cache_key] = result
            return result

        self._cache[cache_key] = None
        return None

    @staticmethod
    def _apply_rules(raw: str, rules: list, mapping_type: str) -> NormalisationResult | None:
        """Apply regex rules in order, returning the first match."""
        for rule in rules:
            if rule.pattern.search(raw):
                return NormalisationResult(
                    raw=raw,
                    normalised=rule.value,
                    confidence=0.88,
                    source="rule",
                    mapping_type=mapping_type,
                )
        return None
