"""
Shopify Ingestion Pipeline.

This is the top-level orchestrator for ingesting a single Shopify store.
It coordinates: HTTP fetching → storage → change detection → DB writes.

Pipeline steps per store:
  1. Open ingestion_run record (status=running)
  2. Fetch all products.json pages via ShopifyClient
  3. For each page: store raw bytes, compute page hash
  4. For each product: compute product hash, check against bean_listing.content_hash
     a. Hash unchanged → update last_seen_at, append price_history only
     b. Hash changed   → upsert bean_listing, upsert listing_variants, append price_history
     c. New product    → insert bean_listing, insert listing_variants, append price_history
  5. Mark products missing from feed as inactive
  6. Close ingestion_run (status=completed|partial|failed)

Idempotency guarantees:
  - All writes use upsert (INSERT ... ON CONFLICT DO UPDATE)
  - price_history is append-only — duplicate runs create duplicate rows,
    which is intentional (shows "no change" as repeated price points)
  - Re-running the same data produces the same final state

The pipeline is self-contained per store. Running it concurrently for
multiple stores is safe as long as each call uses its own DB session.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bean_listing import BeanListing
from app.models.enums import (
    AvailabilityStatus,
    GrindType,
    ListingStatus,
    RunStatus,
    RunType,
)
from app.models.ingestion_run import IngestionRun
from app.models.pricing import ListingVariant, PriceHistory
from app.models.source_page import SourcePage
from app.models.store import Store
from app.models.enums import PageType, ParserStrategy
from app.services.shopify.client import FetchedPage, ShopifyClient
from app.services.shopify.hashing import compute_product_hash
from app.services.shopify.parser import parse_product_fields, parse_variant
from app.services.storage.backend import StorageBackend, compute_hash, get_storage_backend

log = logging.getLogger(__name__)


@dataclass
class IngestionCounters:
    """Mutable counters threaded through the pipeline."""
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    pages_fetched: int = 0
    pages_failed: int = 0
    warnings: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def warn(self, message: str, url: str | None = None, detail: str | None = None) -> None:
        self.warnings.append({"message": message, "url": url, "detail": detail})
        log.warning("%s | %s", message, detail or "")

    def error(self, message: str, url: str | None = None, detail: str | None = None) -> None:
        self.errors.append({"message": message, "url": url, "detail": detail})
        log.error("%s | %s", message, detail or "")


class ShopifyIngestionPipeline:
    """
    Ingests all products from one Shopify store into the platform database.

    Usage:
        pipeline = ShopifyIngestionPipeline(session, store)
        run = await pipeline.run()
    """

    def __init__(
        self,
        session: AsyncSession,
        store: Store,
        storage: StorageBackend | None = None,
    ) -> None:
        self.session = session
        self.store = store
        self.storage = storage or get_storage_backend()
        self.counters = IngestionCounters()
        self._run: IngestionRun | None = None
        self._now = datetime.now(timezone.utc)

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(self) -> IngestionRun:
        """
        Execute the full ingestion pipeline for this store.
        Always returns an IngestionRun — never raises.
        """
        self._run = await self._open_run()

        try:
            async with ShopifyClient(self.store.domain) as client:
                fetch_result = await client.fetch_all_products()

            if not fetch_result.success:
                for err in fetch_result.errors:
                    self.counters.error(**err)
                return await self._close_run(RunStatus.failed)

            # Track which seller_product_ids we see in this run
            seen_seller_ids: set[str] = set()

            for page in fetch_result.pages:
                await self._process_page(page, seen_seller_ids)

            # Mark products absent from this feed run as inactive
            await self._deactivate_missing(seen_seller_ids)

            # Update store crawl timestamp
            await self._update_store_crawl_time()

            status = RunStatus.partial if self.counters.errors else RunStatus.completed
            return await self._close_run(status)

        except Exception as exc:
            log.error("Pipeline failure for %s: %s", self.store.domain, exc, exc_info=True)
            self.counters.error(f"Pipeline exception: {exc}", detail=repr(exc))
            return await self._close_run(RunStatus.failed)

    # ── Page processing ───────────────────────────────────────────────────────

    async def _process_page(self, page: FetchedPage, seen_ids: set[str]) -> None:
        """Store raw page payload and process each product on it."""
        # 1. Compute content hash of raw page bytes
        page_hash = compute_hash(page.raw_bytes)

        # 2. Upsert the source_page record
        source_page = await self._upsert_source_page(page, page_hash)

        # 3. Store raw bytes in object storage
        storage_path = self.storage.build_path(
            store_domain=self.store.domain,
            source_type="shopify",
            filename=f"products_page_{page.page_number}.json",
            date=self._now,
        )
        try:
            actual_path = await self.storage.write(storage_path, page.raw_bytes)
            source_page.raw_storage_path = actual_path
            self.counters.pages_fetched += 1
        except Exception as exc:
            self.counters.warn(
                f"Failed to write page {page.page_number} to storage",
                url=page.url,
                detail=str(exc),
            )

        # 4. Process each product on this page
        for product in page.products:
            self.counters.records_seen += 1
            seller_id = str(product.get("id", ""))
            if seller_id:
                seen_ids.add(seller_id)
            try:
                await self._process_product(product, source_page)
            except Exception as exc:
                self.counters.error(
                    f"Failed processing product '{product.get('title', seller_id)}'",
                    detail=str(exc),
                )

        await self.session.flush()

    async def _process_product(self, product: dict, source_page: SourcePage) -> None:
        """
        Upsert a single Shopify product and all its variants.

        Decision tree:
          - Product hash unchanged → update timestamps + price history only
          - Product hash changed   → update listing fields + variants + price history
          - New product            → insert listing + variants + price history
        """
        product_hash = compute_product_hash(product)
        seller_product_id = str(product.get("id", ""))
        product_handle = product.get("handle", "")

        # Look up existing listing by seller_product_id + store_id
        existing_listing = await self._find_listing(seller_product_id)

        if existing_listing is not None:
            if existing_listing.content_hash == product_hash:
                # ── Unchanged: update freshness and append prices only ────
                await self._touch_listing(existing_listing)
                await self._append_price_history_for_listing(existing_listing, product)
                self.counters.records_unchanged += 1
                return

            # ── Changed: update listing fields and variants ───────────────
            await self._update_listing(existing_listing, product, source_page, product_hash)
            await self._upsert_variants(existing_listing, product)
            await self._append_price_history_for_listing(existing_listing, product)
            self.counters.records_updated += 1

        else:
            # ── New product: insert listing and variants ───────────────────
            listing = await self._insert_listing(product, source_page, product_hash)
            await self._upsert_variants(listing, product)
            await self._append_price_history_for_listing(listing, product)
            self.counters.records_created += 1

    # ── Listing operations ────────────────────────────────────────────────────

    async def _find_listing(self, seller_product_id: str) -> BeanListing | None:
        stmt = select(BeanListing).where(
            BeanListing.store_id == self.store.id,
            BeanListing.seller_product_id == seller_product_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _insert_listing(
        self, product: dict, source_page: SourcePage, product_hash: str
    ) -> BeanListing:
        fields = parse_product_fields(product)
        listing = BeanListing(
            store_id=self.store.id,
            source_page_id=source_page.id,
            content_hash=product_hash,
            listing_status=ListingStatus.active,
            active_flag=True,
            first_seen_at=self._now,
            last_seen_at=self._now,
            last_changed_at=self._now,
            **{k: v for k, v in fields.items() if k not in ("product_handle", "tags")},
        )
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def _update_listing(
        self,
        listing: BeanListing,
        product: dict,
        source_page: SourcePage,
        product_hash: str,
    ) -> None:
        fields = parse_product_fields(product)
        listing.content_hash = product_hash
        listing.last_seen_at = self._now
        listing.last_changed_at = self._now
        listing.source_page_id = source_page.id
        listing.listing_status = ListingStatus.active
        listing.active_flag = True
        # Update raw label fields if they changed
        for field_name in ("raw_title", "raw_description", "roast_label_raw",
                           "process_label_raw", "origin_label_raw", "varietal_label_raw"):
            new_val = fields.get(field_name)
            if new_val is not None:
                setattr(listing, field_name, new_val)

    async def _touch_listing(self, listing: BeanListing) -> None:
        """Update only last_seen_at for unchanged listings."""
        listing.last_seen_at = self._now

    # ── Variant upsert ────────────────────────────────────────────────────────

    async def _upsert_variants(self, listing: BeanListing, product: dict) -> None:
        """
        Upsert all variants for a listing.

        Uses PostgreSQL INSERT ... ON CONFLICT (bean_listing_id, seller_variant_id)
        DO UPDATE to maintain idempotency. The ON CONFLICT clause matches the
        partial unique index created in the migration.
        """
        variants_raw = product.get("variants", [])

        for variant_raw in variants_raw:
            parsed = parse_variant(variant_raw, product_title=product.get("title", ""))
            seller_variant_id = parsed.seller_variant_id

            # Look up existing variant
            existing_stmt = select(ListingVariant).where(
                ListingVariant.bean_listing_id == listing.id,
                ListingVariant.seller_variant_id == seller_variant_id,
            )
            existing = (await self.session.execute(existing_stmt)).scalar_one_or_none()

            if existing is None:
                variant = ListingVariant(
                    bean_listing_id=listing.id,
                    variant_title_raw=parsed.variant_title_raw,
                    weight_g=parsed.weight_g,
                    grind_type=parsed.grind_type,
                    pack_count=parsed.pack_count,
                    price_gbp=parsed.price_gbp,
                    price_per_100g_gbp=parsed.price_per_100g_gbp,
                    currency_code=parsed.currency_code,
                    availability_status=parsed.availability_status,
                    sku=parsed.sku,
                    seller_variant_id=seller_variant_id,
                    recorded_at=self._now,
                )
                self.session.add(variant)
            else:
                # Update price and availability; preserve weight/grind (stable)
                existing.price_gbp = parsed.price_gbp
                existing.price_per_100g_gbp = parsed.price_per_100g_gbp
                existing.availability_status = parsed.availability_status
                existing.recorded_at = self._now
                # Update weight/grind if we now have a better value
                if parsed.weight_g is not None:
                    existing.weight_g = parsed.weight_g
                if parsed.grind_type != GrindType.unknown:
                    existing.grind_type = parsed.grind_type

    # ── Price history ─────────────────────────────────────────────────────────

    async def _append_price_history_for_listing(
        self, listing: BeanListing, product: dict
    ) -> None:
        """
        Append one PriceHistory row per variant on every run.
        This is intentional — price_history is the time series.
        The DB-level rule prevents UPDATE/DELETE on this table.
        """
        # Fetch the current persisted variants for this listing
        variant_stmt = select(ListingVariant).where(
            ListingVariant.bean_listing_id == listing.id
        )
        variants = (await self.session.execute(variant_stmt)).scalars().all()

        # Build a lookup from seller_variant_id to parsed price/availability
        raw_variants = {
            str(v.get("id", "")): v for v in product.get("variants", [])
        }

        for variant in variants:
            raw = raw_variants.get(variant.seller_variant_id or "")
            if raw is None:
                # Variant exists in DB but not in current feed — out of stock
                price = variant.price_gbp
                avail = AvailabilityStatus.out_of_stock
                price_per_100g = variant.price_per_100g_gbp
            else:
                from app.services.shopify.parser import parse_price, compute_price_per_100g
                price = parse_price(raw.get("price"))
                avail = parse_variant(raw).availability_status
                price_per_100g = compute_price_per_100g(price, variant.weight_g)

            history = PriceHistory(
                listing_variant_id=variant.id,
                price_gbp=price,
                price_per_100g_gbp=price_per_100g,
                availability_status=avail,
                recorded_at=self._now,
            )
            self.session.add(history)

    # ── Source page upsert ────────────────────────────────────────────────────

    async def _upsert_source_page(self, page: FetchedPage, page_hash: str) -> SourcePage:
        feed_url = f"https://{self.store.domain}/products.json"
        stmt = select(SourcePage).where(
            SourcePage.store_id == self.store.id,
            SourcePage.url == feed_url,
        )
        source_page = (await self.session.execute(stmt)).scalar_one_or_none()

        if source_page is None:
            source_page = SourcePage(
                store_id=self.store.id,
                url=feed_url,
                page_type=PageType.feed,
                parser_strategy=ParserStrategy.shopify,
                discovered_at=self._now,
                last_fetched_at=self._now,
                status_code=200,
                content_hash=page_hash,
                changed_flag=True,
            )
            self.session.add(source_page)
        else:
            changed = source_page.content_hash != page_hash
            source_page.last_fetched_at = self._now
            source_page.status_code = 200
            source_page.changed_flag = changed
            source_page.content_hash = page_hash

        await self.session.flush()
        return source_page

    # ── Deactivation ──────────────────────────────────────────────────────────

    async def _deactivate_missing(self, seen_seller_ids: set[str]) -> None:
        """
        Mark listings that weren't in the current feed as inactive.
        This catches products that have been removed from the store.
        """
        if not seen_seller_ids:
            return

        stmt = select(BeanListing).where(
            BeanListing.store_id == self.store.id,
            BeanListing.active_flag == True,  # noqa: E712
            BeanListing.seller_product_id.notin_(seen_seller_ids),
        )
        missing = (await self.session.execute(stmt)).scalars().all()
        for listing in missing:
            listing.active_flag = False
            listing.listing_status = ListingStatus.inactive
            self.counters.warn(
                f"Product deactivated (absent from feed): {listing.raw_title}",
                detail=f"seller_product_id={listing.seller_product_id}",
            )

    # ── Store update ──────────────────────────────────────────────────────────

    async def _update_store_crawl_time(self) -> None:
        self.store.last_successful_crawl_at = self._now

    # ── Run lifecycle ─────────────────────────────────────────────────────────

    async def _open_run(self) -> IngestionRun:
        run = IngestionRun(
            run_type=RunType.incremental,
            store_id=self.store.id,
            started_at=self._now,
            status=RunStatus.running,
        )
        self.session.add(run)
        await self.session.commit()
        log.info("Opened ingestion run %s for %s", run.id, self.store.domain)
        return run

    async def _close_run(self, status: RunStatus) -> IngestionRun:
        completed_at = datetime.now(timezone.utc)
        self._run.status = status
        self._run.completed_at = completed_at
        self._run.records_seen = self.counters.records_seen
        self._run.records_created = self.counters.records_created
        self._run.records_updated = self.counters.records_updated
        self._run.records_unchanged = self.counters.records_unchanged
        self._run.pages_fetched = self.counters.pages_fetched
        self._run.pages_failed = self.counters.pages_failed
        self._run.warnings = self.counters.warnings
        self._run.errors = self.counters.errors

        await self.session.commit()

        duration = (completed_at - self._now).total_seconds()
        log.info(
            "Ingestion run %s closed: status=%s seen=%d created=%d updated=%d "
            "unchanged=%d errors=%d duration=%.1fs",
            self._run.id, status.value,
            self.counters.records_seen, self.counters.records_created,
            self.counters.records_updated, self.counters.records_unchanged,
            len(self.counters.errors), duration,
        )
        return self._run
