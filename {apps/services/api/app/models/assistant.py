"""
AssistantLog model — append-only record of every assistant interaction.

Used for:
  - Hallucination risk monitoring
  - Intent distribution analytics
  - Failure investigation
  - Prompt regression testing
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import UUIDMixin


class AssistantLog(UUIDMixin, Base):
    """One row per assistant chat turn. Never updated or deleted."""

    __tablename__ = "assistant_logs"

    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # JSONB: list of {tool: str, params: dict} — retrieval calls made
    retrieval_calls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # JSONB: list of serialised DB records injected as context
    retrieved_context: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    assistant_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 0.0–1.0 heuristic risk score
    hallucination_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    answered_without_grounding: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    prompt_version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="assistant-v1.0.0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<AssistantLog intent={self.intent} risk={self.hallucination_risk:.2f}>"
