"""Add flavour taxonomy tables

Revision ID: 002_flavour_taxonomy
Revises: 001_initial_schema
Create Date: 2025-01-15 00:00:00

New tables:
  - flavour_taxonomy   : controlled vocabulary tree (family → category → tag)
  - bean_flavour_tags  : M2M between canonical_beans and taxonomy tags,
                         with confidence score, source, and LLM audit JSONB

Design notes:
  - Raw flavour_notes on canonical_beans are NEVER modified — additive only.
  - A tag has depth 0 (family), 1 (category), 2 (specific tag).
  - bean_flavour_tags.source: 'rule' | 'llm' | 'manual'
  - review_status mirrors the existing pattern from canonical_matches.
  - llm_audit stores the raw LLM response for explainability.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_flavour_taxonomy"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. flavour_taxonomy ───────────────────────────────────────────────────
    op.create_table(
        "flavour_taxonomy",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Hierarchical slug — unique, URL-safe, e.g. "fruity.citrus.lemon"
        sa.Column("slug", sa.String(100), nullable=False),
        # Human-readable label for display
        sa.Column("label", sa.String(100), nullable=False),
        # depth: 0=family, 1=category, 2=tag
        sa.Column("depth", sa.Integer, nullable=False),
        # Parent reference — NULL for family (depth=0) nodes
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flavour_taxonomy.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # Colour used by the wheel visualisation (CSS hex)
        sa.Column("colour", sa.String(7), nullable=True),
        # Synonyms stored as text array for fuzzy matching
        sa.Column(
            "synonyms",
            postgresql.ARRAY(sa.String(100)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        # Sort order within siblings
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_flavour_taxonomy_slug", "flavour_taxonomy", ["slug"], unique=True)
    op.create_index("ix_flavour_taxonomy_parent_id", "flavour_taxonomy", ["parent_id"])
    op.create_index("ix_flavour_taxonomy_depth", "flavour_taxonomy", ["depth"])
    # GIN index on synonyms for @> containment queries
    op.execute("""
        CREATE INDEX ix_flavour_taxonomy_synonyms_gin
        ON flavour_taxonomy USING gin (synonyms)
    """)

    # ── 2. bean_flavour_tags ──────────────────────────────────────────────────
    op.create_table(
        "bean_flavour_tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "bean_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_beans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "taxonomy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flavour_taxonomy.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Raw note that triggered this tag (preserved verbatim)
        sa.Column("raw_note", sa.String(200), nullable=False),
        # 0.0–1.0 confidence from the normalisation source
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        # 'rule' | 'llm' | 'manual'
        sa.Column("source", sa.String(20), nullable=False, server_default="rule"),
        # Review workflow mirrors canonical_matches
        sa.Column(
            "review_status",
            postgresql.ENUM(name="review_status", create_type=False),
            nullable=False,
            server_default="accepted",
        ),
        # Full LLM response stored for audit / explainability
        sa.Column("llm_audit", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_bean_flavour_tags_bean_id", "bean_flavour_tags", ["bean_id"])
    op.create_index("ix_bean_flavour_tags_taxonomy_id", "bean_flavour_tags", ["taxonomy_id"])
    op.create_index("ix_bean_flavour_tags_review_status", "bean_flavour_tags", ["review_status"])
    op.create_index("ix_bean_flavour_tags_source", "bean_flavour_tags", ["source"])
    op.create_index("ix_bean_flavour_tags_confidence", "bean_flavour_tags", ["confidence"])
    # Unique: one tag per (bean, taxonomy node, raw_note) — prevents duplicate mapping
    op.create_index(
        "ix_bean_flavour_tags_unique",
        "bean_flavour_tags",
        ["bean_id", "taxonomy_id", "raw_note"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("bean_flavour_tags")
    op.drop_table("flavour_taxonomy")
