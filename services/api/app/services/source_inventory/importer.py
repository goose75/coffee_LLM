"""
Source inventory importer.

Reads a CSV of UK roasters, runs domain detection for each, and writes
results to the stores and source_pages tables.

Designed to be run:
  - On initial setup (against the full seed CSV)
  - Incrementally (new rows in CSV are detected and inserted; existing rows updated)
  - Via the admin API's POST /admin/sources/import endpoint

CSV format (headers required):
  domain, name, region, roaster_flag, cafe_flag

Idempotency:
  - Stores are upserted on domain (unique key).
  - Source pages are upserted on (store_id, url).
  - Detection results always overwrite — re-running updates strategy/status.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Store
from app.models.source_page import SourcePage
from app.models.enums import ParserStrategy, SourceType, PageType
from app.services.source_inventory.detector import BulkDetector, DomainDetector
from app.services.source_inventory.detection_result import DomainDetectionResult

log = logging.getLogger(__name__)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _rows_from_csv(content: str) -> list[dict]:
    """Parse CSV content into row dicts. Accepts string or bytes."""
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for row in reader:
        domain = row.get("domain", "").strip().lower()
        name = row.get("name", "").strip()
        if not domain or not name:
            continue
        rows.append({
            "domain": domain,
            "name": name,
            "region": row.get("region", "").strip() or None,
            "roaster_flag": parse_bool(row.get("roaster_flag", "false")),
            "cafe_flag": parse_bool(row.get("cafe_flag", "false")),
        })
    return rows


async def _upsert_store(
    session: AsyncSession,
    row: dict,
    detection: DomainDetectionResult,
) -> Store:
    """
    Insert or update a store from CSV row + detection result.
    Returns the persisted Store instance.
    """
    existing = await session.execute(
        select(Store).where(Store.domain == row["domain"])
    )
    store = existing.scalar_one_or_none()

    parser_strategy = ParserStrategy(detection.parser_strategy)
    source_type = SourceType(detection.source_type) if detection.source_type in [e.value for e in SourceType] else SourceType.html

    if store is None:
        store = Store(
            name=row["name"],
            domain=row["domain"],
            homepage_url=detection.homepage_url,
            source_type=source_type,
            parser_strategy=parser_strategy,
            country_code="GB",
            uk_region=row.get("region"),
            roaster_flag=row.get("roaster_flag", False),
            cafe_flag=row.get("cafe_flag", False),
            ecommerce_flag=True,
            active_flag=detection.reachable,
            crawl_frequency_hours=12 if parser_strategy == ParserStrategy.shopify else 24,
        )
        session.add(store)
        log.info("Inserting new store: %s", row["domain"])
    else:
        # Update detection-derived fields, preserve operator-set fields
        store.parser_strategy = parser_strategy
        store.source_type = source_type
        store.active_flag = detection.reachable
        store.homepage_url = detection.homepage.final_url or detection.homepage_url if detection.homepage else detection.homepage_url
        log.info("Updating existing store: %s", row["domain"])

    await session.flush()  # get ID before inserting source_pages
    return store


async def _upsert_source_pages(
    session: AsyncSession,
    store: Store,
    detection: DomainDetectionResult,
) -> int:
    """Insert or update source_pages from discovered URLs. Returns count of upserted rows."""
    now = datetime.now(timezone.utc)
    count = 0

    for url_info in detection.discovered_urls:
        existing = await session.execute(
            select(SourcePage).where(
                SourcePage.store_id == store.id,
                SourcePage.url == url_info["url"],
            )
        )
        page = existing.scalar_one_or_none()

        page_type_str = url_info.get("page_type", "product")
        page_type = PageType(page_type_str) if page_type_str in [e.value for e in PageType] else PageType.product
        strategy = ParserStrategy(url_info.get("parser_strategy", "unknown"))

        if page is None:
            page = SourcePage(
                store_id=store.id,
                url=url_info["url"],
                page_type=page_type,
                parser_strategy=strategy,
                discovered_at=now,
            )
            session.add(page)
            count += 1

    return count


class SourceInventoryImporter:
    """
    Orchestrates CSV parsing → domain detection → DB writes.
    
    Usage:
        importer = SourceInventoryImporter(session)
        report = await importer.import_csv_file(Path("data/uk_roasters_seed.csv"))
    """

    def __init__(self, session: AsyncSession, concurrency: int = 8) -> None:
        self.session = session
        self.concurrency = concurrency

    async def import_csv_content(self, csv_content: str) -> dict:
        """Import from a CSV string. Returns a summary report."""
        rows = _rows_from_csv(csv_content)
        return await self._process_rows(rows)

    async def import_csv_file(self, path: Path) -> dict:
        """Import from a CSV file path."""
        content = path.read_text(encoding="utf-8")
        return await self.import_csv_content(content)

    async def detect_single_domain(self, domain: str) -> DomainDetectionResult:
        """Run detection for a single domain without writing to DB."""
        async with DomainDetector() as detector:
            return await detector.detect(domain)

    async def rescan_store(self, store: Store) -> dict:
        """Re-run detection for an existing store and update its fields."""
        detection = await self.detect_single_domain(store.domain)
        updated = await _upsert_store(self.session, {
            "domain": store.domain,
            "name": store.name,
            "region": store.uk_region,
            "roaster_flag": store.roaster_flag,
            "cafe_flag": store.cafe_flag,
        }, detection)
        pages_upserted = await _upsert_source_pages(self.session, updated, detection)
        await self.session.commit()
        return {
            "domain": store.domain,
            "parser_strategy": detection.parser_strategy,
            "reachable": detection.reachable,
            "pages_upserted": pages_upserted,
            "signals": [s.value for s in detection.signals],
        }

    async def _process_rows(self, rows: list[dict]) -> dict:
        """Run bulk detection and write results."""
        report = {
            "total": len(rows),
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "unreachable": 0,
            "strategies": {"shopify": 0, "schema_org": 0, "html": 0, "unknown": 0},
            "errors": [],
        }

        if not rows:
            return report

        domains = [r["domain"] for r in rows]
        domain_to_row = {r["domain"]: r for r in rows}

        bulk = BulkDetector(concurrency=self.concurrency)
        detections = await bulk.detect_all(domains)
        detection_map: dict[str, DomainDetectionResult] = {d.domain: d for d in detections}

        for domain, row in domain_to_row.items():
            detection = detection_map.get(domain)
            if detection is None:
                report["failed"] += 1
                report["errors"].append({"domain": domain, "error": "detection missing"})
                continue

            if not detection.reachable:
                report["unreachable"] += 1

            try:
                # Check if store is new or existing for reporting
                existing = await self.session.execute(
                    select(Store).where(Store.domain == domain)
                )
                is_new = existing.scalar_one_or_none() is None

                store = await _upsert_store(self.session, row, detection)
                await _upsert_source_pages(self.session, store, detection)

                if is_new:
                    report["inserted"] += 1
                else:
                    report["updated"] += 1

                strategy = detection.parser_strategy
                if strategy in report["strategies"]:
                    report["strategies"][strategy] += 1

            except Exception as exc:
                log.error("Failed to write store %s: %s", domain, exc, exc_info=True)
                report["failed"] += 1
                report["errors"].append({"domain": domain, "error": str(exc)})
                await self.session.rollback()
                continue

        try:
            await self.session.commit()
        except Exception as exc:
            log.error("Commit failed: %s", exc, exc_info=True)
            await self.session.rollback()
            report["errors"].append({"error": f"commit failed: {exc}"})

        return report
