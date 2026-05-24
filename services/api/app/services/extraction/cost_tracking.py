"""
Cost Tracking for LLM v2.0.0 Extraction

Monitors API costs for LLM-based extraction, generates daily reports,
and triggers alerts for cost overruns scenarios.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.raw_extraction import RawExtraction
from app.models.ingestion_run import IngestionRun


@dataclass
class TokenMetrics:
    """Token usage metrics for a single extraction"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str = "claude-opus-4-1"

    @property
    def cost_usd(self) -> float:
        """Calculate cost in USD using Claude Opus 4.1 pricing"""
        # Pricing: $0.015 per 1M input, $0.060 per 1M output
        input_cost = (self.input_tokens / 1_000_000) * 0.015
        output_cost = (self.output_tokens / 1_000_000) * 0.060
        return round(input_cost + output_cost, 6)


@dataclass
class CostMetrics:
    """Cost metrics for a batch of extractions"""
    extraction_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    avg_tokens_per_extraction: float
    avg_cost_per_extraction: float
    timestamp: datetime

    @classmethod
    def from_token_list(cls, token_metrics: List[TokenMetrics]) -> "CostMetrics":
        """Create CostMetrics from list of TokenMetrics"""
        if not token_metrics:
            return cls(
                extraction_count=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_tokens=0,
                total_cost_usd=0,
                avg_tokens_per_extraction=0,
                avg_cost_per_extraction=0,
                timestamp=datetime.utcnow(),
            )

        input_tokens = sum(t.input_tokens for t in token_metrics)
        output_tokens = sum(t.output_tokens for t in token_metrics)
        total_tokens = input_tokens + output_tokens
        total_cost = sum(t.cost_usd for t in token_metrics)
        count = len(token_metrics)

        return cls(
            extraction_count=count,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 4),
            avg_tokens_per_extraction=round(total_tokens / count, 1),
            avg_cost_per_extraction=round(total_cost / count, 6),
            timestamp=datetime.utcnow(),
        )


class CostTracker:
    """Tracks and reports on LLM extraction costs"""

    # Cost alert thresholds
    ALERT_COST_PER_EXTRACTION = 0.025  # Alert if > $0.025 per extraction
    ALERT_DAILY_COST = 50.00  # Alert if > $50/day
    ALERT_WEEKLY_COST = 350.00  # Alert if > $350/week

    def __init__(self):
        self.daily_metrics: Dict[str, CostMetrics] = {}
        self.alerts: List[str] = []

    async def get_daily_cost_report(
        self,
        session: AsyncSession,
        date: Optional[datetime] = None,
    ) -> Dict:
        """
        Generate cost report for a specific day.

        Args:
            session: Database session
            date: Date to report on (default: today)

        Returns:
            dict: Daily cost metrics and trends
        """
        if date is None:
            date = datetime.utcnow().date()

        # Query extractions from specified date with v2.0.0
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)

        stmt = (
            select(RawExtraction)
            .where(
                and_(
                    RawExtraction.created_at >= start_of_day,
                    RawExtraction.created_at < end_of_day,
                    RawExtraction.extraction_method == "llm",
                    RawExtraction.metadata.isnot(None),
                )
            )
        )

        result = await session.execute(stmt)
        extractions = result.scalars().all()

        # Extract token metrics
        token_metrics = []
        for extraction in extractions:
            metadata = extraction.metadata or {}
            if "tokens" in metadata:
                tokens = metadata["tokens"]
                token_metrics.append(
                    TokenMetrics(
                        input_tokens=int(tokens.get("input_tokens", 0)),
                        output_tokens=int(tokens.get("output_tokens", 0)),
                        total_tokens=int(tokens.get("total_tokens", 0)),
                    )
                )

        # Calculate metrics
        cost_metrics = CostMetrics.from_token_list(token_metrics)

        # Check for alerts
        alerts = self._check_alerts(cost_metrics)

        return {
            "date": date.isoformat(),
            "extraction_count": cost_metrics.extraction_count,
            "total_tokens": cost_metrics.total_tokens,
            "avg_tokens_per_extraction": cost_metrics.avg_tokens_per_extraction,
            "total_cost_usd": cost_metrics.total_cost_usd,
            "avg_cost_per_extraction": cost_metrics.avg_cost_per_extraction,
            "alerts": alerts,
            "status": "⚠️ ALERT" if alerts else "✅ OK",
        }

    async def get_weekly_cost_report(
        self,
        session: AsyncSession,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Generate cost report for the past 7 days.

        Args:
            session: Database session
            end_date: End date for week (default: today)

        Returns:
            dict: Weekly cost metrics with daily breakdown
        """
        if end_date is None:
            end_date = datetime.utcnow().date()

        start_date = end_date - timedelta(days=7)

        # Query week's extractions
        start_of_week = datetime.combine(start_date, datetime.min.time())
        end_of_week = datetime.combine(end_date, datetime.max.time())

        stmt = (
            select(RawExtraction)
            .where(
                and_(
                    RawExtraction.created_at >= start_of_week,
                    RawExtraction.created_at < end_of_week,
                    RawExtraction.extraction_method == "llm",
                )
            )
        )

        result = await session.execute(stmt)
        extractions = result.scalars().all()

        # Group by day
        daily_breakdown = {}
        total_cost = 0

        for extraction in extractions:
            date_key = extraction.created_at.date().isoformat()

            if date_key not in daily_breakdown:
                daily_breakdown[date_key] = {"count": 0, "cost": 0}

            daily_breakdown[date_key]["count"] += 1

            # Calculate cost (simple estimate if tokens not available)
            if extraction.metadata and "cost_usd" in extraction.metadata:
                cost = float(extraction.metadata["cost_usd"])
                daily_breakdown[date_key]["cost"] += cost
                total_cost += cost
            else:
                # Estimate: ~1,250 tokens average, $0.01 per extraction
                daily_breakdown[date_key]["cost"] += 0.01
                total_cost += 0.01

        # Calculate week's total metrics
        extraction_count = sum(d["count"] for d in daily_breakdown.values())
        avg_cost_per_extraction = (
            total_cost / extraction_count if extraction_count > 0 else 0
        )

        # Check alerts
        alerts = []
        if total_cost > self.ALERT_WEEKLY_COST:
            alerts.append(
                f"⚠️ Weekly cost ${total_cost:.2f} exceeds threshold ${self.ALERT_WEEKLY_COST}"
            )

        return {
            "week_start": start_date.isoformat(),
            "week_end": end_date.isoformat(),
            "total_extraction_count": extraction_count,
            "total_cost_usd": round(total_cost, 2),
            "avg_cost_per_extraction": round(avg_cost_per_extraction, 4),
            "daily_breakdown": daily_breakdown,
            "alerts": alerts,
            "status": "⚠️ ALERT" if alerts else "✅ OK",
        }

    def _check_alerts(self, metrics: CostMetrics) -> List[str]:
        """Check for cost-related alerts"""
        alerts = []

        if metrics.avg_cost_per_extraction > self.ALERT_COST_PER_EXTRACTION:
            alerts.append(
                f"⚠️ Cost per extraction ${metrics.avg_cost_per_extraction:.4f} "
                f"exceeds threshold ${self.ALERT_COST_PER_EXTRACTION}"
            )

        if metrics.total_cost_usd > self.ALERT_DAILY_COST:
            alerts.append(
                f"⚠️ Daily cost ${metrics.total_cost_usd:.2f} exceeds threshold ${self.ALERT_DAILY_COST}"
            )

        return alerts

    def format_cost_report(self, report: Dict) -> str:
        """Format cost report for display/logging"""
        lines = []
        lines.append("=" * 60)
        lines.append("💰 LLM Extraction Cost Report")
        lines.append("=" * 60)

        if "week_start" in report:
            lines.append(f"Period: {report['week_start']} to {report['week_end']}")
        else:
            lines.append(f"Date: {report['date']}")

        lines.append(f"Status: {report['status']}")
        lines.append("")
        lines.append("📊 Metrics:")
        lines.append(f"  Extractions: {report['extraction_count']}")
        lines.append(f"  Total cost: ${report['total_cost_usd']}")
        lines.append(f"  Avg per extraction: ${report['avg_cost_per_extraction']:.4f}")

        if "avg_tokens_per_extraction" in report:
            lines.append(f"  Avg tokens: {report['avg_tokens_per_extraction']:.0f}")

        if report.get("alerts"):
            lines.append("")
            lines.append("🚨 Alerts:")
            for alert in report["alerts"]:
                lines.append(f"  {alert}")

        lines.append("=" * 60)
        return "\n".join(lines)


# Global cost tracker instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get or create global cost tracker instance"""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


# Example usage in worker:
#
# async def track_extraction_cost(extraction: RawExtraction):
#     """Log cost metrics for an extraction"""
#     if extraction.metadata and "cost_usd" in extraction.metadata:
#         cost = extraction.metadata["cost_usd"]
#         tokens = extraction.metadata.get("tokens", {})
#         logger.info(
#             f"Extraction cost: ${cost:.4f} "
#             f"({tokens.get('total_tokens', 0)} tokens)"
#         )
#
# async def generate_daily_cost_report(session: AsyncSession):
#     """Generate and log daily cost report"""
#     tracker = get_cost_tracker()
#     report = await tracker.get_daily_cost_report(session)
#     logger.info(tracker.format_cost_report(report))
