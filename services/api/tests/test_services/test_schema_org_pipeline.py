"""
Integration tests for SchemaOrgIngestionPipeline.

Tests:
  - Basic extraction from schema.org fixtures
  - Content hashing and change detection
  - Product ID derivation
  - Price history appending
"""

from pathlib import Path
import pytest
from datetime import datetime, timezone

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_ORG_FIXTURES = FIXTURES / "schema_org"


@pytest.mark.asyncio
async def test_schema_org_pipeline_extracts_from_fixture(session_factory):
    """Test that SchemaOrgIngestionPipeline successfully extracts products from schema.org markup."""
    from app.services.schema_org.pipeline import SchemaOrgIngestionPipeline
    from app.models.store import Store
    from app.models.source_page import SourcePage
    from app.models.enums import ParserStrategy, PageType
    from sqlalchemy.ext.asyncio import AsyncSession

    # Load test HTML with schema.org markup
    html_bytes = (SCHEMA_ORG_FIXTURES / "colonna_woocommerce.html").read_bytes()

    async with session_factory() as session:
        # Create test store
        store = Store(
            name="Test Coffee Store",
            domain="test.coffee",
            homepage_url="https://test.coffee/",
            source_type="roaster",
            parser_strategy=ParserStrategy.schema_org.value,
            country_code="GB",
            active_flag=True,
            ecommerce_flag=True,
            roaster_flag=True,
            crawl_frequency_hours=24,
        )
        session.add(store)
        await session.flush()

        # Create source page
        source_page = SourcePage(
            store_id=store.id,
            url="https://test.coffee/products/test-coffee",
            page_type=PageType.product.value,
            parser_strategy=ParserStrategy.schema_org.value,
            discovered_at=datetime.now(timezone.utc),
        )
        session.add(source_page)
        await session.flush()

        # Create mock HTTP fetch
        async def mock_fetch(url):
            return html_bytes

        # Create pipeline
        pipeline = SchemaOrgIngestionPipeline(session=session, store=store)

        # Mock the fetch method
        original_fetch = pipeline._fetch_page
        pipeline._fetch_page = mock_fetch

        # Run pipeline
        run = await pipeline.run()

        # Verify results
        assert run is not None
        assert run.records_seen > 0, "Pipeline should have found products in schema.org markup"
        assert run.records_created > 0, "Pipeline should have created new listings"
        assert run.status == "completed", f"Pipeline should complete successfully, got {run.status}"

        # Verify BeanListing was created
        from sqlalchemy import select
        from app.models.bean_listing import BeanListing

        listings = (await session.execute(
            select(BeanListing).where(BeanListing.store_id == store.id)
        )).scalars().all()

        assert len(listings) > 0, "Pipeline should have created BeanListing records"
        assert listings[0].content_hash is not None
        assert listings[0].extraction_method == "schema_org"


@pytest.mark.asyncio
async def test_schema_org_pipeline_handles_missing_markup(session_factory):
    """Test that SchemaOrgIngestionPipeline gracefully handles pages without schema.org markup."""
    from app.services.schema_org.pipeline import SchemaOrgIngestionPipeline
    from app.models.store import Store
    from app.models.source_page import SourcePage
    from app.models.enums import ParserStrategy, PageType
    from datetime import datetime, timezone

    html_bytes = b"<html><body>No schema.org markup here</body></html>"

    async with session_factory() as session:
        # Create test store
        store = Store(
            name="Test Coffee Store",
            domain="test.coffee",
            homepage_url="https://test.coffee/",
            source_type="roaster",
            parser_strategy=ParserStrategy.schema_org.value,
            country_code="GB",
            active_flag=True,
            ecommerce_flag=True,
            roaster_flag=True,
            crawl_frequency_hours=24,
        )
        session.add(store)
        await session.flush()

        # Create source page
        source_page = SourcePage(
            store_id=store.id,
            url="https://test.coffee/no-schema",
            page_type=PageType.product.value,
            parser_strategy=ParserStrategy.schema_org.value,
            discovered_at=datetime.now(timezone.utc),
        )
        session.add(source_page)
        await session.flush()

        # Create pipeline
        pipeline = SchemaOrgIngestionPipeline(session=session, store=store)

        # Mock the fetch method
        async def mock_fetch(url):
            return html_bytes

        pipeline._fetch_page = mock_fetch

        # Run pipeline - should not crash
        run = await pipeline.run()

        assert run is not None
        assert run.status in ("completed", "partial")
        # No records should be created since there's no schema.org markup
        assert run.records_created == 0


def test_schema_org_parser_extracts_from_fixture():
    """Test that SchemaOrgParser extracts products from test fixture."""
    from app.services.extraction.schema_org_parser import SchemaOrgParser

    html_bytes = (SCHEMA_ORG_FIXTURES / "colonna_woocommerce.html").read_bytes()
    parser = SchemaOrgParser()

    result = parser.extract(html_bytes, "https://test.coffee/products/test")

    assert result is not None
    assert result.validation_status in ("valid", "partial"), f"Got status: {result.validation_status}"
    assert result.payload is not None
    assert result.payload.coffee_name, "Should extract coffee name from schema.org"
    assert len(result.payload.price_variants) > 0, "Should extract price variants"


def test_schema_org_pipeline_derives_product_ids():
    """Test seller_product_id derivation logic."""
    from app.services.schema_org.pipeline import SchemaOrgIngestionPipeline
    from app.services.extraction.payload import ExtractionPayload
    from app.models.source_page import SourcePage
    from app.models.enums import PageType, ParserStrategy

    pipeline = SchemaOrgIngestionPipeline(None, None)

    # Test URL path derivation
    source_page = SourcePage(
        url="https://test.coffee/products/ethiopian-yirgacheffe",
        page_type=PageType.product.value,
        parser_strategy=ParserStrategy.schema_org.value,
    )
    payload = ExtractionPayload(coffee_name="Ethiopian Yirgacheffe")

    product_id = pipeline._derive_seller_product_id(payload, source_page)
    assert product_id == "ethiopian-yirgacheffe"

    # Test query param derivation
    source_page2 = SourcePage(
        url="https://test.coffee/?product=456",
        page_type=PageType.product.value,
        parser_strategy=ParserStrategy.schema_org.value,
    )
    product_id2 = pipeline._derive_seller_product_id(payload, source_page2)
    assert product_id2.startswith("product-")


def test_schema_org_pipeline_content_hash():
    """Test that content hashing works for change detection."""
    from app.services.schema_org.pipeline import SchemaOrgIngestionPipeline
    from app.services.extraction.payload import ExtractionPayload, PriceVariantPayload

    pipeline = SchemaOrgIngestionPipeline(None, None)

    # Identical payloads should have same hash
    payload1 = ExtractionPayload(
        coffee_name="Test Coffee",
        roaster_name="Test Roaster",
        raw_title="Test Title",
        varietal=["Bourbon"],
        process="Washed",
        origin_country="Ethiopia",
        price_variants=[
            PriceVariantPayload(price_gbp=12.50, weight_g=250)
        ]
    )

    payload2 = ExtractionPayload(
        coffee_name="Test Coffee",
        roaster_name="Test Roaster",
        raw_title="Test Title",
        varietal=["Bourbon"],
        process="Washed",
        origin_country="Ethiopia",
        price_variants=[
            PriceVariantPayload(price_gbp=12.50, weight_g=250)
        ]
    )

    hash1 = pipeline._compute_hash(payload1)
    hash2 = pipeline._compute_hash(payload2)

    assert hash1 == hash2, "Identical payloads should have same hash"

    # Different prices should have different hash
    payload3 = ExtractionPayload(
        coffee_name="Test Coffee",
        roaster_name="Test Roaster",
        raw_title="Test Title",
        varietal=["Bourbon"],
        process="Washed",
        origin_country="Ethiopia",
        price_variants=[
            PriceVariantPayload(price_gbp=15.00, weight_g=250)  # Different price
        ]
    )

    hash3 = pipeline._compute_hash(payload3)
    assert hash1 != hash3, "Different prices should produce different hashes"
