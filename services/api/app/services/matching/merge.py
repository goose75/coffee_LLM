"""
Canonical bean merge.

Merging combines two canonical beans into one:
  • All BeanListings referring to `source` are re-pointed to `target`.
  • All CanonicalMatches referring to `source` are re-pointed to `target`.
  • Fields that are populated on `source` and blank on `target` are copied
    over so we don't lose information.
  • `source` is deleted (default) once everything has moved.

This is irreversible. Callers should confirm the user's intent before
calling. The two beans must have compatible origin_country (or one of them
blank) — otherwise the merge is rejected.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.resolution import CanonicalMatch

log = logging.getLogger(__name__)


# Fields we copy from source → target if target is empty.
_COPYABLE_FIELDS = (
    "origin_country", "origin_region", "farm_or_estate", "washing_station",
    "producer", "process", "process_detail", "altitude_masl_min",
    "altitude_masl_max", "harvest_year", "roast_level",
)
_COPYABLE_LIST_FIELDS = ("varietal", "flavour_notes")


def _is_blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, list):
        return len(v) == 0
    return False


async def merge_canonical_beans(
    session: AsyncSession,
    source_bean_id: UUID,
    target_bean_id: UUID,
    delete_source: bool = True,
) -> dict:
    """
    Merge `source` into `target`. Returns a summary dict.
    Raises ValueError if either bean is missing or origins are incompatible.
    """
    if source_bean_id == target_bean_id:
        raise ValueError("Cannot merge a bean into itself")

    source = await session.get(CanonicalBean, source_bean_id)
    target = await session.get(CanonicalBean, target_bean_id)
    if source is None:
        raise ValueError(f"Source bean {source_bean_id} not found")
    if target is None:
        raise ValueError(f"Target bean {target_bean_id} not found")

    # Sanity: don't merge across origins. Either side blank is OK.
    if (source.origin_country and target.origin_country
            and source.origin_country.strip().lower() != target.origin_country.strip().lower()):
        raise ValueError(
            f"Origin mismatch: source='{source.origin_country}', target='{target.origin_country}'. "
            f"Merge refused — these are likely different coffees."
        )

    # ── Copy missing fields source → target ───────────────────────────────────
    fields_copied: list[str] = []
    for fname in _COPYABLE_FIELDS:
        if _is_blank(getattr(target, fname, None)) and not _is_blank(getattr(source, fname, None)):
            setattr(target, fname, getattr(source, fname))
            fields_copied.append(fname)
    for fname in _COPYABLE_LIST_FIELDS:
        target_val = getattr(target, fname, None) or []
        source_val = getattr(source, fname, None) or []
        if not target_val and source_val:
            setattr(target, fname, list(source_val))
            fields_copied.append(fname)
        elif source_val:
            # Union, preserving target order, dedup case-insensitive
            seen = {v.lower() for v in target_val}
            extras = [v for v in source_val if v.lower() not in seen]
            if extras:
                setattr(target, fname, target_val + extras)
                fields_copied.append(fname)

    # ── Re-point listings ─────────────────────────────────────────────────────
    relinked_listings = 0
    listings_stmt = select(BeanListing).where(BeanListing.canonical_bean_id == source_bean_id)
    for listing in (await session.execute(listings_stmt)).scalars().all():
        listing.canonical_bean_id = target_bean_id
        relinked_listings += 1

    # ── Re-point matches ──────────────────────────────────────────────────────
    matches_stmt = select(CanonicalMatch).where(CanonicalMatch.proposed_canonical_bean_id == source_bean_id)
    relinked_matches = 0
    for match in (await session.execute(matches_stmt)).scalars().all():
        match.proposed_canonical_bean_id = target_bean_id
        relinked_matches += 1

    # Recompute target completeness
    target.data_completeness_score = target.compute_completeness()

    # ── Delete source ─────────────────────────────────────────────────────────
    source_deleted = False
    if delete_source:
        await session.delete(source)
        source_deleted = True

    await session.commit()

    log.info(
        "Merged canonical bean %s → %s. relinked listings=%d matches=%d copied=%s deleted=%s",
        source_bean_id, target_bean_id, relinked_listings, relinked_matches,
        fields_copied, source_deleted,
    )

    return {
        "target_bean_id": target_bean_id,
        "relinked_listings": relinked_listings,
        "relinked_matches": relinked_matches,
        "fields_copied": fields_copied,
        "source_deleted": source_deleted,
    }
