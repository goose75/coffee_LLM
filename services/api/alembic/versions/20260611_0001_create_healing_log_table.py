"""
Create healing_log table for autonomous healing system

Revision ID: 20260611_0001
Revises: 20260610_0001
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON

revision = "20260611_0001"
down_revision = "20260610_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create healing_log table
    op.create_table(
        "healing_log",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("store_id", PG_UUID(as_uuid=True), sa.ForeignKey("stores.id"), nullable=False, index=True),
        sa.Column("error_message", sa.String, nullable=True),
        sa.Column("root_cause", sa.String, nullable=True),
        sa.Column("error_type", sa.String, nullable=True),
        sa.Column("severity", sa.String, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("fix_action", sa.String, nullable=False),
        sa.Column("healing_success", sa.String, nullable=False, server_default="pending"),
        sa.Column("result_message", sa.String, nullable=True),
        sa.Column("diagnosis_json", JSON, nullable=True),
        sa.Column("healing_attempt_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("healing_completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("healing_log")
