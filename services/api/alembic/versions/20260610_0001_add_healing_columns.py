"""
Add healing and extraction control columns to stores table

Revision ID: 20260610_0001
Revises: 20260522_0001_extraction_feedback
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260610_0001"
down_revision = "20260522_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add health_status column with default "unknown"
    op.add_column(
        "stores",
        sa.Column("health_status", sa.String(50), nullable=False, server_default="unknown"),
    )

    # Create index on health_status for healing queries
    op.create_index("ix_stores_health_status", "stores", ["health_status"])

    # Add extraction_retry_count column
    op.add_column(
        "stores",
        sa.Column("extraction_retry_count", sa.Integer, nullable=False, server_default="0"),
    )

    # Add extraction_config column (JSON) for storing parser-specific settings
    op.add_column(
        "stores",
        sa.Column("extraction_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    # Remove the index first
    op.drop_index("ix_stores_health_status", table_name="stores")

    # Remove the columns
    op.drop_column("stores", "extraction_config")
    op.drop_column("stores", "extraction_retry_count")
    op.drop_column("stores", "health_status")
