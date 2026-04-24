"""Pydantic v2 schemas for the assistant API."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class AssistantLogItem(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    session_id: str
    user_message: str
    intent: str | None
    retrieval_calls: list
    retrieved_context: list
    prompt_tokens: int | None
    completion_tokens: int | None
    assistant_response: str | None
    hallucination_risk: float | None
    answered_without_grounding: bool
    error: str | None
    duration_ms: int | None
    flagged: bool
    flag_reason: str | None
    prompt_version: str
    created_at: datetime


class PaginatedLogs(BaseModel):
    data: list[AssistantLogItem]
    total: int
    page: int
    page_size: int
    has_next: bool


class FlagRequest(BaseModel):
    flagged: bool
    reason: str | None = None


class IntentCount(BaseModel):
    intent: str
    count: int


class AssistantStats(BaseModel):
    days: int
    total_interactions: int
    high_risk_count: int
    ungrounded_count: int
    flagged_count: int
    avg_hallucination_risk: float
    avg_duration_ms: float
    intent_distribution: list[IntentCount]
