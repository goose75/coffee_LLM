"""HTML ingestion pipeline — orchestrates extraction and saves to BeanListing."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bean_listing import BeanListing
from app.models.canonical_bean import CanonicalBean
from app.models.ingestion_run import IngestionRun
from app.models.pricing import ListingVariant, PriceHistory
from app.models.source_page import SourcePage
from app.models.store import Store
from app.models.enums import RunStatus, RunType, ListingStatus, AvailabilityStatus
from app.services.extraction.payload import ExtractionResult

from .extractor import HtmlExtractor

log = logging.getLogger(__name__)


class IngestionCounters:
    """Track extraction results."""
    def __init__(self):
        self.pages_fetched = 0
        self.pages_failed = 0
        self.records_seen = 0
        self.records_created = 0
        self.records_updated = 0
        self.records_unchanged = 0
        self.errors = []

    def error(self, message: str, url: str = "", detail: str = ""):
        self.errors.append({"message": message, "url": url, "detail": detail})


class HtmlIngestionPipeline:
    """
    Extracts products from HTML storefronts via parser chain.
    Follows ShopifyIngestionPipeline pattern exactly.
    """

    def __init__(self, session: AsyncSession, store: Store):
        self.session = session
        self.store = store
        self.extractor = HtmlExtractor()
        self.now = datetime.now(timezone.utc)

    async def run(self) -> IngestionRun:
        """Main orchestrator - always returns IngestionRun, never raises."""
        counters = IngestionCounters()

        # Open run
        run = await self._open_run()

        try:
            # Fetch all source_pages for this store
            source_pages = await self._fetch_source_pages()
            if not source_pages:
                counters.error("No source pages found for store")
                return await self._close_run(run, counters)

            # Process each page
            for source_page in source_pages:
                await self._process_page(source_page, counters)

            # Deactivate products not in this run
            await self._deactivate_missing(run.id, counters)

        except Exception as exc:
            counters.error(f"Pipeline error: {exc}", detail=str(exc))
            log.exception(f"HTML pipeline failed for {self.store.id}")

        # Close run
        return await self._close_run(run, counters)

    async def _fetch_source_pages(self) -> list[SourcePage]:
        """Get all known source pages for this store."""
        stmt = select(SourcePage).where(SourcePage.store_id == self.store.id)
        return (await self.session.execute(stmt)).scalars().all()

    async def _process_page(self, source_page: SourcePage, counters: IngestionCounters) -> None:
        """Fetch HTML and extract products."""
        try:
            import urllib.request
            import urllib.error

            # Fetch page
            try:
                req = urllib.request.Request(source_page.url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    if response.status != 200:
                        counters.error(
                            f"Page returned {response.status}",
                            url=source_page.url,
                            detail=f"HTTP {response.status}"
                        )
                        counters.pages_failed += 1
                        return
                    html_bytes = response.read()
            except urllib.error.HTTPError as e:
                counters.error(
                    f"Page returned {e.code}",
                    url=source_page.url,
                    detail=f"HTTP {e.code}"
                )
                counters.pages_failed += 1
                return

            counters.pages_fetched += 1

            # Extract products
            extractions = await self.extractor.extract_products(html_bytes, source_page.url)

            # Process each extraction
            for extraction in extractions:
                await self._process_product(extraction, source_page, counters)

        except Exception as exc:
            counters.error(f"Page fetch failed: {source_page.url}", detail=str(exc))
            counters.pages_failed += 1
            log.exception(f"Failed to fetch {source_page.url}")

    async def _process_product(self, extraction: ExtractionResult, source_page: SourcePage, counters: IngestionCounters) -> None:
        """Insert/update/touch product listing."""
        counters.records_seen += 1

        try:
            payload = extraction.payload
            content_hash = self._compute_hash(payload)
            seller_product_id = self._derive_seller_product_id(extraction, source_page)

            # Lookup existing listing
            existing_listing = await self._find_listing(seller_product_id)

            if existing_listing is None:
                # NEW: Insert
                listing = await self._insert_listing(extraction, source_page, content_hash, seller_product_id)
                await self._upsert_variants(listing, extraction)
                await self._append_price_history(listing, extraction)
                counters.records_created += 1

            elif existing_listing.content_hash == content_hash:
                # UNCHANGED: Touch freshness only
                await self._touch_listing(existing_listing)
                await self._append_price_history(existing_listing, extraction)
                counters.records_unchanged += 1

            else:
                # CHANGED: Update all fields
                await self._update_listing(existing_listing, extraction, source_page, content_hash)
                await self._upsert_variants(existing_listing, extraction)
                await self._append_price_history(existing_listing, extraction)
                counters.records_updated += 1

        except Exception as exc:
            counters.error(f"Failed to process product", detail=str(exc))
            log.exception("Product processing failed")

    async def _find_listing(self, seller_product_id: str) -> Optional[BeanListing]:
        """Lookup existing listing by seller_product_id."""
        stmt = select(BeanListing).where(
            and_(
                BeanListing.store_id == self.store.id,
                BeanListing.seller_product_id == seller_product_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _insert_listing(
        self,
        extraction: ExtractionResult,
        source_page: SourcePage,
        content_hash: str,
        seller_product_id: str,
    ) -> BeanListing:
        """Insert new listing."""
        payload = extraction.payload

        listing = BeanListing(
            store_id=self.store.id,
            canonical_bean_id=None,  # Will be matched later
            raw_title=payload.coffee_name or "Unknown",
            product_url=payload.source_url or source_page.url,
            listing_status=ListingStatus.active,
            active_flag=True,
            first_seen_at=self.now,
            last_seen_at=self.now,
            content_hash=content_hash,
            seller_product_id=seller_product_id,
        )
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def _update_listing(
        self,
        listing: BeanListing,
        extraction: ExtractionResult,
        source_page: SourcePage,
        new_hash: str,
    ) -> None:
        """Update changed listing."""
        payload = extraction.payload
        listing.raw_title = payload.coffee_name or listing.raw_title
        listing.product_url = payload.source_url or source_page.url
        listing.last_seen_at = self.now
        listing.content_hash = new_hash
        await self.session.flush()

    async def _touch_listing(self, listing: BeanListing) -> None:
        """Touch freshness timestamp only."""
        listing.last_seen_at = self.now
        await self.session.flush()

    async def _upsert_variants(self, listing: BeanListing, extraction: ExtractionResult) -> None:
        """Create/update listing variants."""
        payload = extraction.payload

        for price_var in payload.price_variants:
            seller_variant_id = f"{listing.seller_product_id}|{price_var.weight_g}|{price_var.grind_type}"

            existing = (
                await self.session.execute(
                    select(ListingVariant).where(
                        and_(
                            ListingVariant.bean_listing_id == listing.id,
                            ListingVariant.seller_variant_id == seller_variant_id,
                        )
                    )
                )
            ).scalar_one_or_none()

            if existing is None:
                variant = ListingVariant(
                    bean_listing_id=listing.id,
                    seller_variant_id=seller_variant_id,
                    variant_title_raw=f"{price_var.weight_g}g / {price_var.grind_type}",
                    weight_g=price_var.weight_g,
                    grind_type=price_var.grind_type,
                    price_gbp=float(price_var.price_gbp),
                    price_per_100g_gbp=self._price_per_100g(price_var.price_gbp, price_var.weight_g),
                    availability_status=price_var.availability,
                    sku=seller_variant_id,
                )
                self.session.add(variant)
            else:
                existing.price_gbp = float(price_var.price_gbp)
                existing.price_per_100g_gbp = self._price_per_100g(price_var.price_gbp, price_var.weight_g)
                existing.availability_status = price_var.availability

        await self.session.flush()

    async def _append_price_history(self, listing: BeanListing, extraction: ExtractionResult) -> None:
        """Append price history for all variants."""
        variants = (
            await self.session.execute(
                select(ListingVariant).where(ListingVariant.bean_listing_id == listing.id)
            )
        ).scalars().all()

        for variant in variants:
            history = PriceHistory(
                listing_variant_id=variant.id,
                price_gbp=variant.price_gbp,
                price_per_100g_gbp=variant.price_per_100g_gbp,
                availability_status=variant.availability_status,
                recorded_at=self.now,
            )
            self.session.add(history)

        await self.session.flush()

    async def _deactivate_missing(self, run_id: UUID, counters: IngestionCounters) -> None:
        """Deactivate products not seen in this run."""
        # For now, don't deactivate (simpler logic)
        pass

    async def _open_run(self) -> IngestionRun:
        """Create IngestionRun record."""
        run = IngestionRun(
            store_id=self.store.id,
            run_type=RunType.single_store,
            status=RunStatus.running,
            started_at=self.now,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def _close_run(self, run: IngestionRun, counters: IngestionCounters) -> IngestionRun:
        """Finalize IngestionRun record."""
        run.status = RunStatus.completed if not counters.errors else RunStatus.failed
        run.completed_at = datetime.now(timezone.utc)
        run.records_seen = counters.records_seen
        run.records_created = counters.records_created
        run.records_updated = counters.records_updated
        run.records_unchanged = counters.records_unchanged
        run.errors = counters.errors

        await self.session.commit()
        return run

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _compute_hash(self, payload) -> str:
        """SHA-256 of immutable fields."""
        fields = [
            payload.coffee_name,
            payload.raw_description or "",
            str(payload.varietal or []),
            payload.process or "",
            payload.origin_country or "",
            str(payload.price_variants),
        ]
        combined = "|".join(str(f) for f in fields)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _derive_seller_product_id(self, extraction: ExtractionResult, source_page: SourcePage) -> str:
        """Stable product ID from URL or hash."""
        from urllib.parse import urlparse, parse_qs

        url = extraction.payload.source_url or source_page.url
        path = urlparse(url).path
        slug = path.rstrip("/").split("/")[-1]

        if slug and slug not in ("shop", "products", "items", "coffee"):
            return slug

        params = parse_qs(urlparse(url).query)
        if "product" in params:
            return f"product-{params['product'][0]}"
        if "id" in params:
            return f"id-{params['id'][0]}"

        return hashlib.sha256(url.encode()).hexdigest()[:12]

    def _price_per_100g(self, price_gbp: float, weight_g: int) -> float:
        """Compute price per 100g."""
        if not weight_g or weight_g <= 0:
            return 0.0
        return round(price_gbp / weight_g * 100, 4)
