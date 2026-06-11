"""
Autonomous LLM-Powered Healing System

Continuously monitors roasters for extraction failures and automatically:
1. Reads error logs
2. Uses Ollama to diagnose root causes
3. Applies fixes without manual intervention
4. Re-runs extraction
5. Tracks what works

Philosophy: Extract from EVERY roaster. Zero manual work except approving deactivation.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Store, IngestionRun, HealingLog
from app.schemas.public import CoffeePublic

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "neural-coffee"


class AutonomousHealer:
    """
    Main orchestrator for autonomous roaster healing.

    Runs continuously, identifying and fixing extraction failures.
    """

    def __init__(self):
        self.error_analyzer = ErrorAnalyzer()
        self.fix_applier = None  # Will be created per iteration with fresh session
        self.strategy_selector = StrategySelector()

    async def run_healing_loop(self, interval_seconds: int = 300):
        """
        Main loop: runs every 5 minutes to check and heal roasters.

        Workflow:
        1. Find roasters with recent errors
        2. Analyze errors with LLM
        3. Apply fixes
        4. Re-trigger ingestion
        5. Track results
        """
        logger.info("Starting Autonomous Healing Loop (runs every %d seconds)", interval_seconds)

        while True:
            try:
                # Create a fresh session for this iteration
                from app.core.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    self.session = session
                    self.fix_applier = FixApplier(session=session)

                    # 1. Find roasters that need healing
                    failing_roasters = await self._get_roasters_needing_healing()
                    logger.info(f"Found {len(failing_roasters)} roasters needing healing")

                    # 2. For each roaster, attempt healing
                    for roaster in failing_roasters:
                        try:
                            await self._heal_roaster(roaster)
                        except Exception as e:
                            logger.error(f"Error healing {roaster.name}: {e}")

                # Wait for next cycle
                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Critical error in healing loop: {e}")
                await asyncio.sleep(60)  # Brief wait before retry

    async def _get_roasters_needing_healing(self) -> list[Store]:
        """
        Find roasters with recent extraction failures or never successfully crawled.
        """
        stmt = (
            select(Store)
            .where(Store.active_flag == True)
            .where(
                # Unknown status (never diagnosed)
                (Store.health_status == "unknown")
                # OR failing
                | (Store.health_status == "failing")
                # OR stale (no recent successful crawl)
                | (and_(
                    Store.health_status == "stale",
                    Store.last_successful_crawl_at < datetime.utcnow() - timedelta(hours=24)
                ))
                # OR never crawled
                | (Store.last_successful_crawl_at == None)
            )
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def _heal_roaster(self, roaster: Store) -> bool:
        """
        Attempt to heal a single roaster through LLM-guided diagnosis and fixes.

        Returns: True if healing succeeded, False otherwise
        """
        logger.info(f"Healing roaster: {roaster.name}")

        # 1. Get recent errors
        errors = await self._get_recent_errors(roaster.id)
        if not errors:
            logger.info(f"{roaster.name}: No recent errors, attempting fresh extraction")
            # Try extraction anyway
            return await self._trigger_ingestion(roaster.id)

        # 2. Analyze errors with LLM
        logger.info(f"{roaster.name}: Analyzing {len(errors)} errors with LLM")
        diagnosis = await self.error_analyzer.diagnose_roaster(roaster, errors)

        if not diagnosis:
            logger.warning(f"{roaster.name}: Could not diagnose errors")
            # Log failed diagnosis attempt
            diagnosis_failed = {
                "error_message": errors[0] if errors else "Unknown error",
                "root_cause": "Could not diagnose",
                "error_type": "unknown",
                "severity": "high",
                "confidence": 0.0
            }
            # Still try a default fix
            fix = {"action": "retry_with_backoff"}
            await self._log_healing_attempt(roaster.id, diagnosis_failed, fix, False)
            return False

        logger.info(f"{roaster.name}: Diagnosis - {diagnosis.get('root_cause', 'Unknown')}")

        # Add error message to diagnosis for logging
        diagnosis["error_message"] = errors[0] if errors else "Unknown error"

        # 3. Select and apply fix
        fix = self.fix_applier.select_fix(diagnosis, roaster)
        if not fix:
            logger.warning(f"{roaster.name}: No applicable fix found")
            fix = {"action": "retry_with_backoff"}  # Default fallback

        logger.info(f"{roaster.name}: Applying fix - {fix['action']}")
        fix_success = await self.fix_applier.apply_fix(roaster, fix)

        if not fix_success:
            logger.error(f"{roaster.name}: Fix application failed")
            await self._log_healing_attempt(roaster.id, diagnosis, fix, False)
            return False

        # 4. Re-trigger ingestion
        logger.info(f"{roaster.name}: Re-triggering ingestion after fix")
        result = await self._trigger_ingestion(roaster.id)

        # 5. Log the healing attempt
        await self._log_healing_attempt(roaster.id, diagnosis, fix, result)

        return result

    async def _get_recent_errors(self, store_id: UUID) -> list[dict]:
        """Get error logs from the most recent failed ingestion runs."""
        stmt = (
            select(IngestionRun)
            .where(IngestionRun.store_id == store_id)
            .order_by(IngestionRun.started_at.desc())
            .limit(5)
        )

        result = await self.session.execute(stmt)
        runs = result.scalars().all()

        errors = []
        for run in runs:
            if run.errors and len(run.errors) > 0:
                errors.extend([e["message"] if isinstance(e, dict) else str(e) for e in run.errors])

        return errors

    async def _trigger_ingestion(self, store_id: UUID) -> bool:
        """
        Trigger ingestion for a single roaster via the reingest API endpoint.
        """
        try:
            # Call the existing reingest endpoint
            # This tells the ingestion service to run extraction again
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"http://localhost:8000/api/v1/admin/sources/{store_id}/reingest"
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code in (200, 202):  # Success or Accepted
                    logger.info(f"Successfully triggered ingestion for store {store_id}")
                    return True
                else:
                    logger.error(f"Failed to trigger ingestion for {store_id}: {response.status_code} - {response.text}")
                    return False
        except asyncio.TimeoutError:
            logger.error(f"Timeout triggering ingestion for {store_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to trigger ingestion for {store_id}: {e}")
            return False

    async def _log_healing_attempt(self, store_id: UUID, diagnosis: dict, fix: dict, success: bool):
        """Log healing attempt to database for analysis and learning."""
        try:
            healing_log = HealingLog(
                store_id=store_id,
                error_message=diagnosis.get("error_message", "Unknown"),
                root_cause=diagnosis.get("root_cause"),
                error_type=diagnosis.get("error_type"),
                severity=diagnosis.get("severity"),
                confidence=diagnosis.get("confidence"),
                fix_action=fix.get("action"),
                healing_success="success" if success else "failed",
                result_message=f"Fix applied and re-ingestion triggered" if success else "Fix applied but re-ingestion may have failed",
                diagnosis_json=diagnosis,
                healing_attempt_at=datetime.utcnow(),
                healing_completed_at=datetime.utcnow() if success is not None else None,
            )
            self.session.add(healing_log)
            await self.session.commit()
            logger.info(f"Logged healing attempt for {store_id}: {fix['action']} - {healing_log.healing_success}")
        except Exception as e:
            logger.error(f"Failed to log healing attempt for {store_id}: {e}")


class ErrorAnalyzer:
    """
    Analyzes extraction errors using the local Ollama LLM.

    Converts raw error messages into actionable diagnoses.
    """

    async def diagnose_roaster(self, roaster: Store, errors: list[str]) -> Optional[dict]:
        """
        Use Ollama to analyze error patterns and suggest root cause.
        """
        # Build error context
        error_context = {
            "roaster_name": roaster.name,
            "domain": roaster.domain,
            "parser_strategy": roaster.parser_strategy,
            "recent_errors": errors[:5],  # Last 5 errors
        }

        # Build prompt for Ollama
        prompt = self._build_diagnosis_prompt(error_context)

        try:
            # Query Ollama
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                )
                if response.status_code != 200:
                    logger.error(f"Ollama error: {response.status_code}")
                    return None

                data = response.json()
                diagnosis_text = data.get("response", "")

                # Parse diagnosis
                return self._parse_diagnosis(diagnosis_text)

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return None

    def _build_diagnosis_prompt(self, context: dict) -> str:
        """Build diagnostic prompt for Ollama."""
        return f"""You are a coffee extraction expert. Diagnose why this roaster's extraction is failing.

Roaster: {context['roaster_name']}
Domain: {context['domain']}
Parser: {context['parser_strategy']}

Recent Errors:
{chr(10).join(f'- {e}' for e in context['recent_errors'])}

Provide a JSON response with:
{{
  "root_cause": "primary reason for failure",
  "error_type": "network|parsing|authentication|data_structure|unknown",
  "severity": "critical|high|medium|low",
  "recommended_actions": ["action1", "action2"],
  "confidence": 0.0-1.0
}}"""

    def _parse_diagnosis(self, response: str) -> Optional[dict]:
        """Parse LLM diagnosis response."""
        try:
            import json

            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                return None

            diagnosis_json = response[json_start:json_end]
            return json.loads(diagnosis_json)

        except Exception as e:
            logger.error(f"Failed to parse diagnosis: {e}")
            return None


class FixApplier:
    """
    Applies fixes automatically based on diagnosed root causes.

    Doesn't require manual intervention except for final deactivation approval.
    """

    def __init__(self, session: AsyncSession = None):
        self.session = session

    def select_fix(self, diagnosis: dict, roaster: Store) -> Optional[dict]:
        """
        Select the best fix to apply based on LLM diagnosis.
        """
        if not diagnosis:
            return None

        recommended_actions = diagnosis.get("recommended_actions", [])
        if not recommended_actions:
            # No recommendations, try default fixes based on error type
            error_type = diagnosis.get("error_type", "unknown")
            if error_type == "authentication":
                return {"action": "update_headers"}
            elif error_type == "parsing":
                return {"action": "switch_parser_to_schema_org"}
            elif error_type == "data_structure":
                return {"action": "switch_parser_to_llm"}
            else:
                return {"action": "retry_with_backoff"}

        # Map first recommended action to a fix
        first_action = recommended_actions[0] if recommended_actions else None

        action_map = {
            "retry_with_backoff": "retry_with_backoff",
            "switch_parser_to_schema_org": "switch_parser_to_schema_org",
            "switch_parser_to_llm": "switch_parser_to_llm",
            "update_headers": "update_headers",
            "discover_source_pages": "discover_source_pages",
            "increase_timeout": "increase_timeout",
        }

        fix_action = action_map.get(first_action, "retry_with_backoff")
        return {
            "action": fix_action,
            "confidence": diagnosis.get("confidence", 0.0),
            "reason": f"LLM recommended: {first_action}"
        }

    async def apply_fix(self, roaster: Store, fix: dict) -> bool:
        """
        Apply the recommended fix to a roaster.

        Returns True if fix was successfully applied (roaster state changed).
        Note: This doesn't mean extraction will succeed - just that we applied the fix.
        """
        action = fix.get("action")

        try:
            # Map fix actions to implementations
            if action == "retry_with_backoff":
                return await self._retry_with_backoff(roaster)
            elif action == "switch_parser_to_schema_org":
                return await self._switch_parser(roaster, "schema_org")
            elif action == "switch_parser_to_llm":
                return await self._switch_parser(roaster, "llm")
            elif action == "update_headers":
                return await self._update_extraction_headers(roaster)
            elif action == "discover_source_pages":
                return await self._discover_source_pages(roaster)
            elif action == "increase_timeout":
                return await self._adjust_timeout(roaster, increase=True)
            else:
                logger.warning(f"Unknown action: {action}")
                return False
        except Exception as e:
            logger.error(f"Error applying fix {action} to {roaster.name}: {e}")
            return False

    async def _retry_with_backoff(self, roaster: Store) -> bool:
        """
        Retry extraction with exponential backoff.
        This is a flag that will be picked up by the ingestion pipeline.
        """
        logger.info(f"Marking {roaster.name} for retry with backoff")
        if not self.session:
            return False

        try:
            # Update roaster to enable retry logic (stored as config)
            stmt = update(Store).where(Store.id == roaster.id).values(
                extraction_retry_count=0,  # Reset retry counter
                extraction_config={
                    **(roaster.extraction_config or {}),
                    "retry_backoff_enabled": True,
                    "retry_backoff_base": 1,  # 1 second initial wait
                    "retry_backoff_max": 30,  # Cap at 30 seconds
                }
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info(f"Enabled backoff retry for {roaster.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable backoff retry for {roaster.name}: {e}")
            return False

    async def _switch_parser(self, roaster: Store, new_parser: str) -> bool:
        """
        Switch parser strategy to alternative.
        This updates parser_strategy which will be picked up by next ingestion run.
        """
        logger.info(f"Switching parser for {roaster.name} from {roaster.parser_strategy} to {new_parser}")
        if not self.session:
            return False

        try:
            # Validate the new parser
            valid_parsers = ["html", "schema_org", "llm", "shopify"]
            if new_parser not in valid_parsers:
                logger.warning(f"Invalid parser: {new_parser}")
                return False

            # Update parser strategy
            stmt = update(Store).where(Store.id == roaster.id).values(
                parser_strategy=new_parser,
                extraction_config={
                    **(roaster.extraction_config or {}),
                    "previous_parser": roaster.parser_strategy,
                    "parser_switched_at": datetime.utcnow().isoformat(),
                    "parser_switch_reason": "autonomous_healing"
                }
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info(f"Switched parser for {roaster.name} to {new_parser}")
            return True
        except Exception as e:
            logger.error(f"Failed to switch parser for {roaster.name}: {e}")
            return False

    async def _update_extraction_headers(self, roaster: Store) -> bool:
        """
        Update HTTP headers to be more browser-like.
        Adds Referer, Sec-Fetch-*, and other anti-bot detection headers.
        """
        logger.info(f"Updating extraction headers for {roaster.name}")
        if not self.session:
            return False

        try:
            # Browser-like headers for bot detection bypass
            headers = {
                **(roaster.extraction_config or {}).get("custom_headers", {}),
                "Referer": roaster.domain or "",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }

            stmt = update(Store).where(Store.id == roaster.id).values(
                extraction_config={
                    **(roaster.extraction_config or {}),
                    "custom_headers": headers,
                    "headers_updated_at": datetime.utcnow().isoformat(),
                }
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info(f"Updated extraction headers for {roaster.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to update headers for {roaster.name}: {e}")
            return False

    async def _discover_source_pages(self, roaster: Store) -> bool:
        """
        Discover product pages from roaster homepage.
        This sets a flag for the ingestion pipeline to crawl and discover pages.
        """
        logger.info(f"Marking {roaster.name} for source page discovery")
        if not self.session:
            return False

        try:
            stmt = update(Store).where(Store.id == roaster.id).values(
                extraction_config={
                    **(roaster.extraction_config or {}),
                    "discover_source_pages": True,
                    "discovery_requested_at": datetime.utcnow().isoformat(),
                }
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info(f"Marked {roaster.name} for source page discovery")
            return True
        except Exception as e:
            logger.error(f"Failed to mark source page discovery for {roaster.name}: {e}")
            return False

    async def _adjust_timeout(self, roaster: Store, increase: bool = False) -> bool:
        """Adjust extraction timeout."""
        logger.info(f"Adjusting timeout for {roaster.name} (increase={increase})")
        if not self.session:
            return False

        try:
            # Current timeout default is 30 seconds
            current_timeout = (roaster.extraction_config or {}).get("request_timeout_seconds", 30)
            new_timeout = current_timeout * 1.5 if increase else max(10, current_timeout / 1.5)
            new_timeout = int(new_timeout)

            stmt = update(Store).where(Store.id == roaster.id).values(
                extraction_config={
                    **(roaster.extraction_config or {}),
                    "request_timeout_seconds": new_timeout,
                    "timeout_adjusted_at": datetime.utcnow().isoformat(),
                }
            )
            await self.session.execute(stmt)
            await self.session.commit()
            logger.info(f"Adjusted timeout for {roaster.name} to {new_timeout}s")
            return True
        except Exception as e:
            logger.error(f"Failed to adjust timeout for {roaster.name}: {e}")
            return False


class StrategySelector:
    """
    Intelligent strategy selection based on roaster history and error patterns.

    Learns what works for each roaster and suggests next strategy if current fails.
    """

    async def select_next_strategy(self, roaster: Store, failed_strategy: str) -> Optional[str]:
        """Select next parser strategy to try."""
        # Priority order for fallback
        strategy_priority = {
            "shopify": ["html", "schema_org", "llm"],
            "html": ["schema_org", "llm"],
            "schema_org": ["html", "llm"],
            "llm": ["html", "schema_org"],
        }

        if failed_strategy not in strategy_priority:
            return None

        # Get list of alternatives
        alternatives = strategy_priority[failed_strategy]

        # Could add ML here to predict best next strategy
        # For now, use simple priority

        return alternatives[0] if alternatives else None


# Global healer instance (started by async app startup)
_healer_task: Optional[asyncio.Task] = None


async def start_autonomous_healer(session: AsyncSession = None):
    """
    Start the autonomous healer in background.

    The session parameter is ignored; the healer creates its own sessions internally.
    It's kept for API compatibility.
    """
    global _healer_task

    if _healer_task is not None:
        logger.warning("Healer already running")
        return

    healer = AutonomousHealer()
    _healer_task = asyncio.create_task(healer.run_healing_loop(interval_seconds=300))
    logger.info("Autonomous Healer started")


async def stop_autonomous_healer():
    """Stop the autonomous healer."""
    global _healer_task

    if _healer_task is None:
        return

    _healer_task.cancel()
    try:
        await _healer_task
    except asyncio.CancelledError:
        pass

    _healer_task = None
    logger.info("Autonomous Healer stopped")
