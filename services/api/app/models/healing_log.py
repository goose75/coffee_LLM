"""
Healing Log Model

Tracks autonomous healing attempts for learning and analysis.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, Float, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base
from app.models.mixins import TimestampMixin


class HealingLog(Base, TimestampMixin):
    """
    Record of healing attempts for autonomous healer system.

    Used for:
    - Learning what fixes work for each roaster
    - Tracking healing success rates
    - Identifying patterns in extraction failures
    """

    __tablename__ = "healing_log"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Reference to Store
    store_id = Column(PG_UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False, index=True)

    # Diagnosis information
    error_message = Column(String, nullable=True)  # The error that triggered healing
    root_cause = Column(String, nullable=True)  # LLM diagnosis: root cause
    error_type = Column(String, nullable=True)  # LLM diagnosis: error_type (network|parsing|auth|structure|unknown)
    severity = Column(String, nullable=True)  # LLM diagnosis: severity (critical|high|medium|low)
    confidence = Column(Float, nullable=True)  # LLM confidence score (0.0-1.0)

    # Fix that was applied
    fix_action = Column(String, nullable=False)  # retry_with_backoff|switch_parser_to_schema_org|switch_parser_to_llm|update_headers|discover_source_pages|increase_timeout

    # Outcome
    healing_success = Column(String, default="pending")  # pending|success|failed|in_progress
    result_message = Column(String, nullable=True)  # Details about what happened

    # Full diagnosis JSON (for learning)
    diagnosis_json = Column(JSON, nullable=True)  # Complete LLM diagnosis response

    # Timestamps
    healing_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    healing_completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<HealingLog(store_id={self.store_id}, action={self.fix_action}, success={self.healing_success})>"
