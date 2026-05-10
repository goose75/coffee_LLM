"""
Assistant orchestrator.

Pipeline for one chat turn:
  1. Classify intent (rule-based, instant)
  2. Execute retrieval plan (typed DB queries)
  3. Serialise records into context block
  4. Call Claude with system prompt + context + conversation history
  5. Score hallucination risk
  6. Write to assistant_logs
  7. Return response

Streaming: yields text chunks as they arrive from the Anthropic API.
The caller (FastAPI endpoint) wraps these in an SSE response.

Token budget: context is capped at MAX_CONTEXT_RECORDS records to stay
well within the model's context window.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assistant import AssistantLog
from app.services.assistant import retrieval as ret
from app.services.assistant.grounding import compute_risk
from app.services.assistant.intent import classify, IntentResult, RetrievalCall
from app.services.assistant.prompts.v1 import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    CONTEXT_TEMPLATE,
    EMPTY_CONTEXT,
)

log = logging.getLogger(__name__)

MAX_CONTEXT_RECORDS = 8
MAX_HISTORY_TURNS = 6   # keep last N user/assistant pairs


# ── Tool dispatcher ────────────────────────────────────────────────────────────

async def _execute_tool(
    call: RetrievalCall,
    session: AsyncSession,
) -> list[dict]:
    """Dispatch a RetrievalCall to the correct retrieval function."""
    tool = call.tool
    params = call.params
    try:
        if tool == "search_coffees":
            return await ret.search_coffees(session, **params)
        elif tool == "get_coffee_detail":
            return await ret.get_coffee_detail(session, **params)
        elif tool == "compare_coffees":
            return await ret.compare_coffees(session, **params)
        elif tool == "find_by_brew_method":
            return await ret.find_by_brew_method(session, **params)
        elif tool == "find_by_price_range":
            return await ret.find_by_price_range(session, **params)
        elif tool == "find_similar_taste":
            return await ret.find_similar_taste(session, **params)
        else:
            log.warning("Unknown retrieval tool: %s", tool)
            return []
    except Exception as exc:
        log.error("Retrieval tool %s failed: %s", tool, exc)
        return []


# ── Context serialiser ─────────────────────────────────────────────────────────

def _build_context_block(records: list[dict]) -> str:
    """Render retrieved records as a compact JSON block for the prompt."""
    if not records:
        return EMPTY_CONTEXT

    # Keep only the most relevant fields to save tokens
    slim = []
    for r in records[:MAX_CONTEXT_RECORDS]:
        slim.append({
            "id": r["id"],
            "name": r["name"],
            "origin_country": r.get("origin_country"),
            "origin_region": r.get("origin_region"),
            "process": r.get("process"),
            "roast_level": r.get("roast_level"),
            "flavour_notes": r.get("flavour_notes", []),
            "espresso_suitable": r.get("espresso_suitable"),
            "filter_suitable": r.get("filter_suitable"),
            "decaf": r.get("decaf"),
            "min_price_gbp": r.get("min_price_gbp"),
            "max_price_gbp": r.get("max_price_gbp"),
            "store_count": r.get("store_count", 0),
            "listings": [
                {
                    "store": l.get("store") or l.get("store_name"),
                    "url": l.get("url") or l.get("product_url"),
                    "variants": l.get("variants", []),
                }
                for l in r.get("listings", [])[:3]  # max 3 stores per bean
            ],
        })

    return CONTEXT_TEMPLATE.format(
        context_json=json.dumps(slim, indent=2, default=str),
        retrieved_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )


# ── Conversation history ───────────────────────────────────────────────────────

def _trim_history(history: list[dict]) -> list[dict]:
    """Keep only the last MAX_HISTORY_TURNS user/assistant pairs."""
    trimmed = []
    for msg in history:
        if msg.get("role") in ("user", "assistant"):
            trimmed.append({"role": msg["role"], "content": str(msg["content"])})
    return trimmed[-(MAX_HISTORY_TURNS * 2):]


# ── Main orchestrator ──────────────────────────────────────────────────────────

async def chat(
    *,
    message: str,
    session_id: str,
    history: list[dict],
    db: AsyncSession,
) -> AsyncIterator[str]:
    """
    Main entry point. Yields text chunks suitable for SSE streaming.
    Logs the full interaction to assistant_logs after generation completes.
    """
    if not settings.ANTHROPIC_API_KEY:
        yield "The assistant requires an ANTHROPIC_API_KEY to be configured."
        return

    start_ms = int(time.time() * 1000)

    # ── Step 1: Classify intent ────────────────────────────────────────────────
    intent_result: IntentResult = classify(message)
    log.info("Assistant intent=%s confidence=%.2f session=%s",
             intent_result.intent, intent_result.confidence, session_id)

    if intent_result.intent == "off_topic":
        response_text = "I'm here to help with UK specialty coffee questions — feel free to ask about coffees, prices, origins, or brewing."
        await _write_log(
            db=db, session_id=session_id, message=message,
            intent=intent_result.intent,
            retrieval_calls=[], context=[],
            response=response_text, risk=0.0,
            answered_without_grounding=False,
            duration_ms=int(time.time() * 1000) - start_ms,
        )
        yield response_text
        return

    # ── Step 2: Execute retrieval plan ─────────────────────────────────────────
    all_records: list[dict] = []
    retrieval_log: list[dict] = []

    for call in intent_result.retrieval_plan:
        records = await _execute_tool(call, db)
        retrieval_log.append({"tool": call.tool, "params": call.params, "results": len(records)})
        for r in records:
            if r["id"] not in {x["id"] for x in all_records}:
                all_records.append(r)

    answered_without_grounding = len(all_records) == 0

    # ── Step 3: Build context block ────────────────────────────────────────────
    context_block = _build_context_block(all_records)
    full_system = SYSTEM_PROMPT + context_block

    # ── Step 4: Build message list for Claude ──────────────────────────────────
    trimmed_history = _trim_history(history[:-1])  # exclude current message
    messages = trimmed_history + [{"role": "user", "content": message}]

    # ── Step 5: Stream from Claude ─────────────────────────────────────────────
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    full_response = ""
    prompt_tokens = 0
    completion_tokens = 0
    error_text: str | None = None

    try:
        async with client.messages.stream(
            model=settings.LLM_MODEL,
            max_tokens=1024,
            system=full_system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield text

            # Capture final usage
            final = await stream.get_final_message()
            prompt_tokens = final.usage.input_tokens
            completion_tokens = final.usage.output_tokens

    except anthropic.APIError as exc:
        error_text = str(exc)
        log.error("Anthropic API error in assistant: %s", exc)
        err_msg = "I'm having trouble connecting right now. Please try again in a moment."
        yield err_msg
        full_response = err_msg

    # ── Step 6: Score hallucination risk ──────────────────────────────────────
    risk = compute_risk(full_response, all_records, answered_without_grounding)
    if risk > 0.4:
        log.warning(
            "High hallucination risk %.2f session=%s intent=%s",
            risk, session_id, intent_result.intent,
        )

    # ── Step 7: Write log ──────────────────────────────────────────────────────
    await _write_log(
        db=db,
        session_id=session_id,
        message=message,
        intent=intent_result.intent,
        retrieval_calls=retrieval_log,
        context=all_records,
        response=full_response,
        risk=risk,
        answered_without_grounding=answered_without_grounding,
        duration_ms=int(time.time() * 1000) - start_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        error=error_text,
    )


async def _write_log(
    *,
    db: AsyncSession,
    session_id: str,
    message: str,
    intent: str,
    retrieval_calls: list[dict],
    context: list[dict],
    response: str | None,
    risk: float,
    answered_without_grounding: bool,
    duration_ms: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    error: str | None = None,
) -> None:
    try:
        log_entry = AssistantLog(
            session_id=session_id,
            user_message=message,
            intent=intent,
            retrieval_calls=retrieval_calls,
            retrieved_context=context[:MAX_CONTEXT_RECORDS],
            prompt_tokens=prompt_tokens or None,
            completion_tokens=completion_tokens or None,
            assistant_response=response,
            hallucination_risk=risk,
            answered_without_grounding=answered_without_grounding,
            error=error,
            duration_ms=duration_ms,
            prompt_version=PROMPT_VERSION,
        )
        db.add(log_entry)
        await db.commit()
    except Exception as exc:
        log.error("Failed to write assistant log: %s", exc)
        await db.rollback()
