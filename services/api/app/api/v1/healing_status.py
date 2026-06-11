"""
Healing Status Monitoring Endpoints

Shows real-time status of the autonomous healing system.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Store, IngestionRun, HealingLog
from pydantic import BaseModel

router = APIRouter(prefix="/healing", tags=["healing"])


class HealingStatus(BaseModel):
    """Real-time healing system status"""

    total_roasters: int
    roasters_needing_healing: int
    healed_this_hour: int
    healed_this_day: int
    success_rate_percent: float
    unknown_status_count: int
    never_crawled_count: int
    extraction_success_rate_percent: float
    status: str  # "healthy", "critical", "degraded"


@router.get("/status", response_model=HealingStatus)
async def get_healing_status(session: AsyncSession = Depends(get_db)) -> HealingStatus:
    """
    Get real-time status of the autonomous healing system.

    Shows how many roasters are being healed and success rates.
    """

    # Total roasters
    total = await session.scalar(select(func.count(Store.id)))

    # Roasters needing healing
    needing_healing = await session.scalar(
        select(func.count(Store.id)).where(
            (Store.health_status.in_(["unknown", "failing", "stale"]))
            | (Store.last_successful_crawl_at == None)
        )
    )

    # Extraction success rate
    total_runs = await session.scalar(select(func.count(IngestionRun.id)))
    successful_runs = await session.scalar(
        select(func.count(IngestionRun.id)).where(
            (IngestionRun.records_created > 0) | (IngestionRun.records_updated > 0)
        )
    )

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    # Never crawled
    never_crawled = await session.scalar(
        select(func.count(Store.id)).where(Store.last_successful_crawl_at == None)
    )

    # Unknown status
    unknown = await session.scalar(
        select(func.count(Store.id)).where(Store.health_status == "unknown")
    )

    # Healed this hour (successful healing attempts)
    now = datetime.utcnow()
    healed_this_hour = await session.scalar(
        select(func.count(HealingLog.id)).where(
            and_(
                HealingLog.healing_completed_at >= (now - timedelta(hours=1)),
                HealingLog.healing_success == "success"
            )
        )
    ) or 0

    # Healed this day (successful healing attempts)
    healed_this_day = await session.scalar(
        select(func.count(HealingLog.id)).where(
            and_(
                HealingLog.healing_completed_at >= (now - timedelta(days=1)),
                HealingLog.healing_success == "success"
            )
        )
    ) or 0

    # Determine overall status
    if success_rate > 80:
        status = "healthy"
    elif success_rate > 50:
        status = "degraded"
    else:
        status = "critical"

    return HealingStatus(
        total_roasters=total,
        roasters_needing_healing=needing_healing,
        healed_this_hour=healed_this_hour,
        healed_this_day=healed_this_day,
        success_rate_percent=success_rate,
        unknown_status_count=unknown,
        never_crawled_count=never_crawled,
        extraction_success_rate_percent=success_rate,
        status=status,
    )


class RoasterHealingStatus(BaseModel):
    """Status of a single roaster being healed"""

    roaster_id: str
    roaster_name: str
    current_status: str
    parser_strategy: str
    last_error: str | None
    healing_attempts: int
    last_heal_attempt: str | None
    extraction_records: int


@router.get("/roasters/{roaster_id}", response_model=RoasterHealingStatus)
async def get_roaster_healing_status(
    roaster_id: str, session: AsyncSession = Depends(get_db)
) -> RoasterHealingStatus:
    """
    Get detailed healing status for a specific roaster.
    """

    # Get roaster
    stmt = select(Store).where(Store.id == roaster_id)
    roaster = await session.scalar(stmt)

    if not roaster:
        raise ValueError(f"Roaster {roaster_id} not found")

    # Get last run
    last_run_stmt = (
        select(IngestionRun)
        .where(IngestionRun.store_id == roaster_id)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    last_run = await session.scalar(last_run_stmt)

    last_error = None
    if last_run and last_run.errors:
        last_error = last_run.errors[0].get("message") if last_run.errors else None

    return RoasterHealingStatus(
        roaster_id=str(roaster.id),
        roaster_name=roaster.name,
        current_status=roaster.health_status,
        parser_strategy=roaster.parser_strategy,
        last_error=last_error,
        healing_attempts=0,  # Would track from healing_log
        last_heal_attempt=None,
        extraction_records=last_run.records_created + last_run.records_updated if last_run else 0,
    )


class RoastersNeedingHealing(BaseModel):
    """List of roasters that need healing"""

    count: int
    roasters: list[dict]


@router.get("/roasters-needing-healing", response_model=RoastersNeedingHealing)
async def get_roasters_needing_healing(
    limit: int = 20, session: AsyncSession = Depends(get_db)
) -> RoastersNeedingHealing:
    """
    Get list of roasters that the autonomous healer will process next.

    This shows which roasters are in the healing queue and why.
    """

    # Get roasters needing healing
    stmt = (
        select(Store)
        .where(
            (Store.health_status.in_(["unknown", "failing", "stale"]))
            | (Store.last_successful_crawl_at == None)
        )
        .where(Store.active_flag == True)
        .order_by(Store.updated_at.desc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    roasters = result.scalars().all()

    return RoastersNeedingHealing(
        count=len(roasters),
        roasters=[
            {
                "id": str(r.id),
                "name": r.name,
                "status": r.health_status,
                "parser": r.parser_strategy,
                "never_crawled": r.last_successful_crawl_at is None,
                "last_update": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in roasters
        ],
    )
