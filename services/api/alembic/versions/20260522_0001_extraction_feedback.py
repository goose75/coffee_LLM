"""Create extraction_feedback table for Phase 4 learning loops.

Revision ID: 20260522_0001
Revises: 20250502_0001
Create Date: 2026-05-22 23:30:00.000000

Adds table for collecting feedback signals on extraction quality:
- Manual ratings from admin UI
- Price validation anomalies
- Duplicate detection mismatches
- A/B test results
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260522_0001'
down_revision = '20250502_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extraction_feedback table
    op.create_table(
        'extraction_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_extraction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('reviewed_by_user_id', sa.String(255), nullable=True),
        sa.Column('rating', sa.String(20), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('price_previous_gbp', sa.Float(), nullable=True),
        sa.Column('price_current_gbp', sa.Float(), nullable=True),
        sa.Column('price_jump_factor', sa.Float(), nullable=True),
        sa.Column('matching_listing_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('duplicate_domain', sa.String(255), nullable=True),
        sa.Column('prompt_version_a', sa.String(20), nullable=True),
        sa.Column('prompt_version_b', sa.String(20), nullable=True),
        sa.Column('confidence_a', sa.Float(), nullable=True),
        sa.Column('confidence_b', sa.Float(), nullable=True),
        sa.Column('winner', sa.String(5), nullable=True),
        sa.Column('signal_strength', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['raw_extraction_id'], ['raw_extractions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['matching_listing_id'], ['bean_listings.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indices for common queries
    op.create_index('idx_feedback_type_created', 'extraction_feedback', ['feedback_type', 'created_at'])
    op.create_index('idx_feedback_extraction_rating', 'extraction_feedback', ['raw_extraction_id', 'rating'])
    op.create_index('idx_feedback_raw_extraction', 'extraction_feedback', ['raw_extraction_id'])
    op.create_index('idx_feedback_created', 'extraction_feedback', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_feedback_created', table_name='extraction_feedback')
    op.drop_index('idx_feedback_raw_extraction', table_name='extraction_feedback')
    op.drop_index('idx_feedback_extraction_rating', table_name='extraction_feedback')
    op.drop_index('idx_feedback_type_created', table_name='extraction_feedback')
    op.drop_table('extraction_feedback')
