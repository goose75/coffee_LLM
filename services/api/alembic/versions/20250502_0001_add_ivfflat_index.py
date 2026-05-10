"""
Add IVFFlat index on canonical_beans.embedding_vector

Revision ID: 20250502_0001
Revises: 20250101_0000_001_initial_schema
Create Date: 2025-05-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20250502_0001"
down_revision = "003_assistant_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IVFFlat approximate nearest-neighbour index for pgvector cosine similarity.
    # lists=100 is appropriate for up to ~1M rows; increase for larger datasets.
    # CONCURRENTLY means no table lock during index creation.
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_canonical_beans_embedding
        ON canonical_beans
        USING ivfflat (embedding_vector vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_canonical_beans_embedding")
