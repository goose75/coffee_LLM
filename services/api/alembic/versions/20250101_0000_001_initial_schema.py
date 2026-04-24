"""Initial schema — all core tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-01-01 00:00:00

Tables created (in dependency order):
  1. stores
  2. source_pages
  3. raw_extractions
  4. canonical_beans          ← pgvector embedding column
  5. bean_listings
  6. listing_variants
  7. price_history             ← append-only
  8. canonical_matches
  9. normalisation_mappings
 10. ingestion_runs

Enum types created:
  - roast_level, grind_type, process
  - source_type, parser_strategy, page_type
  - extraction_method, validation_status
  - listing_status, availability_status
  - match_method, review_status
  - mapping_type, run_type, run_status

Indexes:
  - Primary keys (all tables)
  - Foreign key columns (all)
  - Selective columns for common query patterns
  - IVFFlat index on canonical_beans.embedding_vector (pgvector approximate search)
  - Composite: (store_id, domain) uniqueness, (listing_variant_id, recorded_at) for history

Extensions:
  - pgvector
  - pg_trgm  (trigram similarity for fuzzy matching)
  - btree_gist (used by exclusion constraints if needed later)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


# ─── Enum helpers ──────────────────────────────────────────────────────────────

def create_enum(name: str, values: list[str]) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:

    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")  # gen_random_uuid()

    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE roast_level AS ENUM (
            'light', 'medium_light', 'medium', 'medium_dark', 'dark', 'unknown'
        )
    """)
    op.execute("""
        CREATE TYPE grind_type AS ENUM (
            'whole_bean', 'espresso', 'filter', 'cafetiere',
            'moka', 'aeropress', 'pour_over', 'omni', 'unknown'
        )
    """)
    op.execute("""
        CREATE TYPE process AS ENUM (
            'washed', 'natural', 'honey', 'anaerobic',
            'wet_hulled', 'carbonic_maceration', 'experimental', 'unknown'
        )
    """)
    op.execute("""
        CREATE TYPE source_type AS ENUM ('shopify', 'html', 'schema_org', 'dataset')
    """)
    op.execute("""
        CREATE TYPE parser_strategy AS ENUM ('shopify', 'schema_org', 'html', 'llm', 'unknown')
    """)
    op.execute("""
        CREATE TYPE page_type AS ENUM ('listing', 'product', 'feed', 'sitemap', 'homepage')
    """)
    op.execute("""
        CREATE TYPE extraction_method AS ENUM
            ('shopify_json', 'schema_org', 'html_rules', 'llm')
    """)
    op.execute("""
        CREATE TYPE validation_status AS ENUM ('valid', 'invalid', 'partial')
    """)
    op.execute("""
        CREATE TYPE listing_status AS ENUM ('active', 'inactive', 'archived')
    """)
    op.execute("""
        CREATE TYPE availability_status AS ENUM
            ('in_stock', 'out_of_stock', 'preorder', 'unknown')
    """)
    op.execute("""
        CREATE TYPE match_method AS ENUM ('exact', 'fuzzy', 'embedding', 'combined', 'manual')
    """)
    op.execute("""
        CREATE TYPE review_status AS ENUM ('pending', 'accepted', 'rejected', 'skipped')
    """)
    op.execute("""
        CREATE TYPE mapping_type AS ENUM
            ('grind', 'roast_level', 'process', 'country', 'region', 'varietal')
    """)
    op.execute("""
        CREATE TYPE run_type AS ENUM ('full', 'incremental', 'single_store', 'single_page')
    """)
    op.execute("""
        CREATE TYPE run_status AS ENUM ('running', 'completed', 'failed', 'partial')
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. stores
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "stores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("homepage_url", sa.Text, nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(name="source_type", create_type=False),
            nullable=False,
            server_default="html",
        ),
        sa.Column(
            "parser_strategy",
            postgresql.ENUM(name="parser_strategy", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="GB"),
        sa.Column("uk_region", sa.String(100), nullable=True),
        sa.Column("roaster_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cafe_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ecommerce_flag", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("active_flag", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("crawl_frequency_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("last_successful_crawl_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_stores_domain", "stores", ["domain"], unique=True)
    op.create_index("ix_stores_active_flag", "stores", ["active_flag"])
    op.create_index("ix_stores_source_type", "stores", ["source_type"])
    op.create_index("ix_stores_parser_strategy", "stores", ["parser_strategy"])

    # Trigger: auto-update updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER stores_updated_at
        BEFORE UPDATE ON stores
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. source_pages
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "source_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column(
            "page_type",
            postgresql.ENUM(name="page_type", create_type=False),
            nullable=False,
            server_default="product",
        ),
        sa.Column(
            "parser_strategy",
            postgresql.ENUM(name="parser_strategy", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("changed_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("raw_storage_path", sa.Text, nullable=True),
    )
    op.create_index("ix_source_pages_store_id", "source_pages", ["store_id"])
    op.create_index("ix_source_pages_content_hash", "source_pages", ["content_hash"])
    op.create_index("ix_source_pages_changed_flag", "source_pages", ["changed_flag"])
    op.create_index("ix_source_pages_page_type", "source_pages", ["page_type"])
    # Composite: fast lookup of a store's pages of a specific type
    op.create_index(
        "ix_source_pages_store_page_type",
        "source_pages",
        ["store_id", "page_type"],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. raw_extractions
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "raw_extractions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "extraction_method",
            postgresql.ENUM(name="extraction_method", create_type=False),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("extracted_payload", postgresql.JSONB, nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "validation_status",
            postgresql.ENUM(name="validation_status", create_type=False),
            nullable=False,
            server_default="valid",
        ),
        sa.Column("validation_errors", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_raw_extractions_source_page_id", "raw_extractions", ["source_page_id"])
    op.create_index("ix_raw_extractions_method", "raw_extractions", ["extraction_method"])
    op.create_index("ix_raw_extractions_validation", "raw_extractions", ["validation_status"])
    op.create_index("ix_raw_extractions_confidence", "raw_extractions", ["confidence_score"])
    # GIN index for JSONB payload queries
    op.execute("""
        CREATE INDEX ix_raw_extractions_payload_gin
        ON raw_extractions USING gin (extracted_payload)
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. canonical_beans  (pgvector embedding column)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "canonical_beans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("canonical_name", sa.String(500), nullable=False),
        # Origin
        sa.Column("origin_country", sa.String(100), nullable=True),
        sa.Column("origin_region", sa.String(200), nullable=True),
        sa.Column("farm_or_estate", sa.String(300), nullable=True),
        sa.Column("washing_station", sa.String(300), nullable=True),
        sa.Column("producer", sa.String(300), nullable=True),
        # Cultivar & process
        sa.Column(
            "varietal",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "process",
            postgresql.ENUM(name="process", create_type=False),
            nullable=True,
        ),
        sa.Column("process_detail", sa.Text, nullable=True),
        # Altitude
        sa.Column("altitude_masl_min", sa.Integer, nullable=True),
        sa.Column("altitude_masl_max", sa.Integer, nullable=True),
        # Harvest & roast
        sa.Column("harvest_year", sa.Integer, nullable=True),
        sa.Column(
            "roast_level",
            postgresql.ENUM(name="roast_level", create_type=False),
            nullable=True,
        ),
        # Sensory
        sa.Column(
            "flavour_notes",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default="{}",
        ),
        # Brew suitability
        sa.Column("decaf_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("espresso_suitable_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("filter_suitable_flag", sa.Boolean, nullable=False, server_default="false"),
        # Embedding (pgvector) — 1536-dim for text-embedding-3-small
        sa.Column("embedding_vector", sa.Text, nullable=True),  # overridden below
        # Quality
        sa.Column("data_completeness_score", sa.Float, nullable=False, server_default="0.0"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Replace the placeholder Text column with the actual vector type
    op.execute("ALTER TABLE canonical_beans DROP COLUMN embedding_vector")
    op.execute("ALTER TABLE canonical_beans ADD COLUMN embedding_vector vector(1536)")

    op.create_index("ix_canonical_beans_name", "canonical_beans", ["canonical_name"])
    op.create_index("ix_canonical_beans_origin_country", "canonical_beans", ["origin_country"])
    op.create_index("ix_canonical_beans_process", "canonical_beans", ["process"])
    op.create_index("ix_canonical_beans_roast_level", "canonical_beans", ["roast_level"])
    op.create_index("ix_canonical_beans_harvest_year", "canonical_beans", ["harvest_year"])
    op.create_index("ix_canonical_beans_decaf", "canonical_beans", ["decaf_flag"])

    # IVFFlat index for approximate nearest-neighbour search on embeddings.
    # lists=100 is appropriate for up to ~1M rows; tune upward as dataset grows.
    # Requires at least one row with a non-null embedding before it can be built.
    op.execute("""
        CREATE INDEX ix_canonical_beans_embedding_ivfflat
        ON canonical_beans
        USING ivfflat (embedding_vector vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding_vector IS NOT NULL
    """)

    # GIN index on flavour_notes array for containment queries
    op.execute("""
        CREATE INDEX ix_canonical_beans_flavour_notes_gin
        ON canonical_beans USING gin (flavour_notes)
    """)

    # Trigram index on canonical_name for LIKE / similarity queries
    op.execute("""
        CREATE INDEX ix_canonical_beans_name_trgm
        ON canonical_beans USING gin (canonical_name gin_trgm_ops)
    """)

    # updated_at trigger
    op.execute("""
        CREATE TRIGGER canonical_beans_updated_at
        BEFORE UPDATE ON canonical_beans
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. bean_listings
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "bean_listings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "canonical_bean_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_beans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Raw source fields
        sa.Column("raw_title", sa.String(500), nullable=False),
        sa.Column("raw_subtitle", sa.String(500), nullable=True),
        sa.Column("raw_description", sa.Text, nullable=True),
        sa.Column("roast_label_raw", sa.String(200), nullable=True),
        sa.Column("process_label_raw", sa.String(200), nullable=True),
        sa.Column("origin_label_raw", sa.String(300), nullable=True),
        sa.Column("varietal_label_raw", sa.String(300), nullable=True),
        # Source identifiers
        sa.Column("seller_product_id", sa.String(255), nullable=True),
        sa.Column("product_url", sa.Text, nullable=True),
        # Status
        sa.Column(
            "listing_status",
            postgresql.ENUM(name="listing_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("active_flag", sa.Boolean, nullable=False, server_default="true"),
        # Temporal tracking
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        # Change detection
        sa.Column("content_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_bean_listings_store_id", "bean_listings", ["store_id"])
    op.create_index("ix_bean_listings_canonical_bean_id", "bean_listings", ["canonical_bean_id"])
    op.create_index("ix_bean_listings_source_page_id", "bean_listings", ["source_page_id"])
    op.create_index("ix_bean_listings_active_flag", "bean_listings", ["active_flag"])
    op.create_index("ix_bean_listings_listing_status", "bean_listings", ["listing_status"])
    op.create_index("ix_bean_listings_first_seen_at", "bean_listings", ["first_seen_at"])
    op.create_index("ix_bean_listings_content_hash", "bean_listings", ["content_hash"])
    # Composite: unique product per store (seller_product_id is Shopify's stable handle)
    op.create_index(
        "ix_bean_listings_store_seller_product",
        "bean_listings",
        ["store_id", "seller_product_id"],
        unique=True,
        postgresql_where=sa.text("seller_product_id IS NOT NULL"),
    )
    # Trigram on raw_title for search
    op.execute("""
        CREATE INDEX ix_bean_listings_raw_title_trgm
        ON bean_listings USING gin (raw_title gin_trgm_ops)
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. listing_variants
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "listing_variants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "bean_listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bean_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant_title_raw", sa.String(300), nullable=False),
        sa.Column("weight_g", sa.Integer, nullable=True),
        sa.Column(
            "grind_type",
            postgresql.ENUM(name="grind_type", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("pack_count", sa.Integer, nullable=True),
        sa.Column("price_gbp", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_per_100g_gbp", sa.Numeric(10, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column(
            "availability_status",
            postgresql.ENUM(name="availability_status", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("sku", sa.String(255), nullable=True),
        sa.Column("seller_variant_id", sa.String(255), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_listing_variants_bean_listing_id", "listing_variants", ["bean_listing_id"])
    op.create_index("ix_listing_variants_seller_variant_id", "listing_variants", ["seller_variant_id"])
    op.create_index("ix_listing_variants_grind_type", "listing_variants", ["grind_type"])
    op.create_index("ix_listing_variants_weight_g", "listing_variants", ["weight_g"])
    op.create_index("ix_listing_variants_availability", "listing_variants", ["availability_status"])
    op.create_index("ix_listing_variants_price_gbp", "listing_variants", ["price_gbp"])
    # Unique seller variant per listing (upsert key)
    op.create_index(
        "ix_listing_variants_listing_seller_variant",
        "listing_variants",
        ["bean_listing_id", "seller_variant_id"],
        unique=True,
        postgresql_where=sa.text("seller_variant_id IS NOT NULL"),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 7. price_history  (append-only)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "price_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "listing_variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listing_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_gbp", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_per_100g_gbp", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "availability_status",
            postgresql.ENUM(name="availability_status", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_price_history_variant_id", "price_history", ["listing_variant_id"])
    op.create_index("ix_price_history_recorded_at", "price_history", ["recorded_at"])
    # Composite: time series query pattern
    op.create_index(
        "ix_price_history_variant_recorded",
        "price_history",
        ["listing_variant_id", "recorded_at"],
    )

    # Prevent accidental UPDATE/DELETE on price_history (append-only guarantee)
    op.execute("""
        CREATE RULE price_history_no_update AS
        ON UPDATE TO price_history DO INSTEAD NOTHING;
    """)
    op.execute("""
        CREATE RULE price_history_no_delete AS
        ON DELETE TO price_history DO INSTEAD NOTHING;
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 8. canonical_matches
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "canonical_matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "bean_listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bean_listings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposed_canonical_bean_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_beans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_method",
            postgresql.ENUM(name="match_method", create_type=False),
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("accepted_by_system_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reviewed_by_user_id", sa.String(255), nullable=True),
        sa.Column(
            "review_status",
            postgresql.ENUM(name="review_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("review_notes", sa.String(1000), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_signals_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_canonical_matches_bean_listing_id", "canonical_matches", ["bean_listing_id"])
    op.create_index("ix_canonical_matches_canonical_bean_id", "canonical_matches", ["proposed_canonical_bean_id"])
    op.create_index("ix_canonical_matches_review_status", "canonical_matches", ["review_status"])
    op.create_index("ix_canonical_matches_confidence_score", "canonical_matches", ["confidence_score"])
    op.create_index("ix_canonical_matches_match_method", "canonical_matches", ["match_method"])
    # Composite: review queue query
    op.create_index(
        "ix_canonical_matches_review_queue",
        "canonical_matches",
        ["review_status", "confidence_score"],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 9. normalisation_mappings
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "normalisation_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "mapping_type",
            postgresql.ENUM(name="mapping_type", create_type=False),
            nullable=False,
        ),
        sa.Column("raw_value", sa.String(500), nullable=False),
        sa.Column("normalised_value", sa.String(200), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_normalisation_mappings_type", "normalisation_mappings", ["mapping_type"])
    op.create_index(
        "ix_normalisation_mappings_raw_value",
        "normalisation_mappings",
        ["raw_value"],
    )
    # Unique: one normalised value per (type, raw_value) pair
    op.create_index(
        "ix_normalisation_mappings_unique",
        "normalisation_mappings",
        ["mapping_type", "raw_value"],
        unique=True,
    )
    # Trigram on raw_value for fuzzy lookup
    op.execute("""
        CREATE INDEX ix_normalisation_mappings_raw_trgm
        ON normalisation_mappings USING gin (raw_value gin_trgm_ops)
    """)
    op.execute("""
        CREATE TRIGGER normalisation_mappings_updated_at
        BEFORE UPDATE ON normalisation_mappings
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 10. ingestion_runs
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "ingestion_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_type",
            postgresql.ENUM(name="run_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="run_status", create_type=False),
            nullable=False,
            server_default="running",
        ),
        sa.Column("records_seen", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_unchanged", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pages_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pages_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warnings", postgresql.JSONB, nullable=False, server_default="'[]'"),
        sa.Column("errors", postgresql.JSONB, nullable=False, server_default="'[]'"),
    )
    op.create_index("ix_ingestion_runs_store_id", "ingestion_runs", ["store_id"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_run_type", "ingestion_runs", ["run_type"])
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])
    # Composite: dashboard query — recent runs per store
    op.create_index(
        "ix_ingestion_runs_store_started",
        "ingestion_runs",
        ["store_id", "started_at"],
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("ingestion_runs")
    op.drop_table("normalisation_mappings")
    op.drop_table("canonical_matches")
    op.drop_table("price_history")
    op.drop_table("listing_variants")
    op.drop_table("bean_listings")
    op.drop_table("canonical_beans")
    op.drop_table("raw_extractions")
    op.drop_table("source_pages")
    op.drop_table("stores")

    # Drop triggers and function
    op.execute("DROP TRIGGER IF EXISTS stores_updated_at ON stores")
    op.execute("DROP TRIGGER IF EXISTS canonical_beans_updated_at ON canonical_beans")
    op.execute("DROP TRIGGER IF EXISTS normalisation_mappings_updated_at ON normalisation_mappings")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")

    # Drop enum types
    for enum_name in [
        "run_status", "run_type", "mapping_type", "review_status",
        "match_method", "availability_status", "listing_status",
        "validation_status", "extraction_method", "page_type",
        "parser_strategy", "source_type", "process", "grind_type", "roast_level",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
