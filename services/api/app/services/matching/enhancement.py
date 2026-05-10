"""
Canonical bean field enhancement.

Two layers:

1. Deterministic consensus — for each missing field on a canonical bean, look
   at what its linked listings claim. If 60% or more of listings with a value
   for that field agree, propose the consensus value. This is fast, free,
   and accounts for most enrichment opportunities (origin_country,
   process, varietal show up cleanly in raw_title / *_label_raw fields).

2. LLM fallback — for fields where consensus is unclear AND the canonical's
   listings have descriptive raw_description text (>200 chars combined),
   we *could* run the LLM extractor. We don't trigger this automatically;
   the deterministic pass covers the meaningful cases at zero token cost.
   The hook is here so a future iteration can wire it up.

The output is an EnhancementProposal — just suggestions. Nothing is written
to the database from this module; the API endpoint applies changes when the
operator approves.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.schemas.matching import EnhancementProposal, FieldSuggestion

log = logging.getLogger(__name__)


# Fields we attempt to enhance. Each tuple:
#   (canonical_attr, listing_getter, normalise_fn or None, min_listings)
def _normalise_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s.lower() if s else None


def _normalise_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip().lower() for x in v if str(x).strip()]
    s = str(v).strip()
    return [s.lower()] if s else []


_FIELDS = [
    # (canonical_attr, listing_attr_or_callable, kind: "scalar"|"list", description)
    ("origin_country", "origin_label_raw", "scalar", "country of origin"),
    ("process", "process_label_raw", "scalar", "processing method"),
    ("varietal", "varietal_label_raw", "list", "varietal(s)"),
]


def _mine_listing_text(listing: Any, field: str) -> str | list[str] | None:
    """
    Pull a value for `field` out of the listing's raw_description if the
    structured *_label_raw column is blank. Returns a string for scalar
    fields, a list for list fields, or None if nothing found.
    """
    text = (
        getattr(listing, "raw_description", None)
        or getattr(listing, "raw_title", None)
        or ""
    )
    if not text:
        return None
    try:
        from app.services.extraction.text_utils import (
            clean_html, extract_origin_country, extract_process, extract_varietal,
        )
        cleaned = clean_html(text)
    except Exception:
        return None

    if field == "origin_country":
        v = extract_origin_country(cleaned)
        return v or None
    if field == "process":
        v = extract_process(cleaned)
        return v or None
    if field == "varietal":
        vs = extract_varietal(cleaned)
        return vs or None
    return None


def _value_or_none(canonical: CanonicalBean, field: str) -> Any:
    """Helper to read a canonical field that might be empty/zero/[]."""
    v = getattr(canonical, field, None)
    if v is None:
        return None
    if isinstance(v, list):
        return v if v else None
    if isinstance(v, str):
        return v if v.strip() else None
    # Enum-typed columns — coerce via .value
    if hasattr(v, "value"):
        return v.value
    return v


# Maps loose vocab — what extractors typically return — to the strict
# Process enum values defined in app.models.enums. Anything not here is
# rejected; we'd rather leave the field blank than store the wrong value.
_PROCESS_ALIASES: dict[str, str] = {
    "washed": "washed",
    "wet": "washed",
    "fully washed": "washed",
    "natural": "natural",
    "dry": "natural",
    "sun-dried": "natural",
    "honey": "honey",
    "yellow honey": "honey",
    "red honey": "honey",
    "black honey": "honey",
    "white honey": "honey",
    "pulped natural": "honey",
    "anaerobic": "anaerobic",
    "anaerobic natural": "anaerobic",
    "anaerobic washed": "anaerobic",
    "wet hulled": "wet_hulled",
    "wet-hulled": "wet_hulled",
    "wet_hulled": "wet_hulled",
    "giling basah": "wet_hulled",
    "carbonic maceration": "carbonic_maceration",
    "carbonic-maceration": "carbonic_maceration",
    "carbonic_maceration": "carbonic_maceration",
    "experimental": "experimental",
    "lactic": "experimental",
    "thermal shock": "experimental",
    "co-fermented": "experimental",
}


def _normalise_process_value(raw: str | None) -> str | None:
    """Return a value safe to pass to Process(...), or None if unknown."""
    if not raw:
        return None
    key = raw.strip().lower()
    return _PROCESS_ALIASES.get(key)


async def propose_enhancement(
    session: AsyncSession,
    bean_id: UUID,
    consensus_threshold: float = 0.60,
) -> EnhancementProposal | None:
    """
    Build an EnhancementProposal for one canonical bean.

    Returns None if the bean doesn't exist. Returns a proposal with no
    suggestions if there's nothing to enhance.
    """
    stmt = (
        select(CanonicalBean)
        .where(CanonicalBean.id == bean_id)
        .options(selectinload(CanonicalBean.bean_listings))
    )
    bean = (await session.execute(stmt)).scalar_one_or_none()
    if bean is None:
        return None

    listings: list[BeanListing] = list(bean.bean_listings or [])
    suggestions: list[FieldSuggestion] = []

    for canonical_attr, listing_attr, kind, _description in _FIELDS:
        current = _value_or_none(bean, canonical_attr)
        if current is not None and current != [] and current != "":
            # Don't second-guess populated fields — that's Pass 3's job.
            continue

        if kind == "scalar":
            counter: Counter[str] = Counter()
            mined_count = 0
            for l in listings:
                v = _normalise_text(getattr(l, listing_attr, None))
                if not v:
                    # Fall back to mining the listing's description text.
                    mined = _mine_listing_text(l, canonical_attr)
                    if isinstance(mined, str):
                        v = _normalise_text(mined)
                        if v:
                            mined_count += 1
                if v:
                    counter[v] += 1
            considered = sum(counter.values())
            if considered == 0:
                continue
            most_common, top_count = counter.most_common(1)[0]
            if top_count / considered >= consensus_threshold:
                src = f"{top_count} of {considered} listings agree"
                if mined_count:
                    src += f" ({mined_count} mined from description)"
                suggestions.append(FieldSuggestion(
                    field=canonical_attr,
                    current_value=None,
                    suggested_value=most_common,
                    confidence=round(top_count / considered, 2),
                    source_summary=src,
                ))

        elif kind == "list":
            # Aggregate distinct values mentioned across listings, count freq.
            counter = Counter()
            considered = 0
            mined_count = 0
            for l in listings:
                values = _normalise_list(getattr(l, listing_attr, None))
                if not values:
                    mined = _mine_listing_text(l, canonical_attr)
                    if isinstance(mined, list) and mined:
                        values = [v.lower() for v in mined]
                        mined_count += 1
                if values:
                    considered += 1
                    for v in values:
                        counter[v] += 1
            if considered == 0:
                continue
            keep = [v for v, c in counter.items() if c / considered >= 0.5]
            if keep:
                src = f"present in ≥50% of {considered} listings"
                if mined_count:
                    src += f" ({mined_count} mined from description)"
                suggestions.append(FieldSuggestion(
                    field=canonical_attr,
                    current_value=None,
                    suggested_value=", ".join(sorted(keep)),
                    confidence=round(min(c / considered for v, c in counter.items() if v in keep), 2),
                    source_summary=src,
                ))

    notes = None
    if not listings:
        notes = "No linked listings — nothing to enhance from."
    elif not suggestions:
        notes = "No deterministic consensus reached. LLM enrichment not yet wired up."

    return EnhancementProposal(
        bean_id=bean.id,
        canonical_name=bean.canonical_name,
        current_completeness=bean.data_completeness_score or 0.0,
        listings_considered=len(listings),
        suggestions=suggestions,
        notes=notes,
    )


async def apply_enhancement(
    session: AsyncSession,
    bean_id: UUID,
    proposal: EnhancementProposal,
    accepted_fields: list[str],
) -> tuple[CanonicalBean, list[str]]:
    """
    Apply a subset of proposal suggestions to the canonical bean.

    Returns (updated_bean, fields_actually_updated).
    """
    bean = await session.get(CanonicalBean, bean_id)
    if bean is None:
        raise ValueError(f"Canonical bean {bean_id} not found")

    suggestion_by_field = {s.field: s for s in proposal.suggestions}
    updated: list[str] = []

    for fname in accepted_fields:
        s = suggestion_by_field.get(fname)
        if s is None:
            continue

        # Type-aware coercion before write
        if fname == "varietal":
            value = [v.strip() for v in (s.suggested_value or "").split(",") if v.strip()]
            if value:
                bean.varietal = value
                updated.append(fname)
        elif fname == "process":
            # Normalise loose vocab to enum values before coercion. The
            # extractor returns values like "carbonic maceration", "anaerobic
            # natural", "black honey" that don't exactly match enum names.
            try:
                from app.models.enums import Process
                process_value = _normalise_process_value(s.suggested_value)
                if process_value is not None:
                    bean.process = Process(process_value)
                    updated.append(fname)
                else:
                    log.warning("Could not normalise '%s' into Process enum", s.suggested_value)
            except (ValueError, KeyError):
                log.warning("Could not coerce '%s' into Process enum", s.suggested_value)
        else:
            setattr(bean, fname, s.suggested_value)
            updated.append(fname)

    bean.data_completeness_score = bean.compute_completeness()
    await session.commit()
    return bean, updated


async def bulk_enhance(
    session: AsyncSession,
    max_completeness: float = 0.5,
    limit: int = 100,
    auto_apply_threshold: float = 0.9,
) -> dict:
    """
    Walk all canonical beans whose completeness is below `max_completeness`,
    propose enhancements, and auto-apply suggestions whose confidence is at
    least `auto_apply_threshold`. Returns a summary dict.
    """
    stmt = (
        select(CanonicalBean.id)
        .where(CanonicalBean.data_completeness_score < max_completeness)
        .order_by(CanonicalBean.data_completeness_score)
        .limit(limit)
    )
    bean_ids = [row[0] for row in (await session.execute(stmt)).all()]

    examined = 0
    beans_updated = 0
    fields_updated = 0
    skipped_no_listings = 0
    skipped_no_suggestions = 0
    errors: list[str] = []

    for bid in bean_ids:
        examined += 1
        try:
            proposal = await propose_enhancement(session, bid)
        except Exception as exc:
            errors.append(f"{bid}: propose failed: {exc}")
            continue
        if proposal is None:
            continue
        if proposal.listings_considered == 0:
            skipped_no_listings += 1
            continue

        accepted = [s.field for s in proposal.suggestions if s.confidence >= auto_apply_threshold]
        if not accepted:
            skipped_no_suggestions += 1
            continue

        try:
            _, updated = await apply_enhancement(session, bid, proposal, accepted)
        except Exception as exc:
            errors.append(f"{bid}: apply failed: {exc}")
            continue

        if updated:
            beans_updated += 1
            fields_updated += len(updated)

    return {
        "beans_examined": examined,
        "beans_updated": beans_updated,
        "fields_updated_total": fields_updated,
        "skipped_no_listings": skipped_no_listings,
        "skipped_no_suggestions": skipped_no_suggestions,
        "errors": errors[:20],
    }
