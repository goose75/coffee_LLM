"""Health check endpoints."""

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import settings

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Basic liveness probe — no DB required."""
    return {
        "status": "ok",
        "service": "coffee-platform-api",
        "version": "0.1.0",
        "env": settings.APP_ENV,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe — checks DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "checks": {
            "database": db_status,
        },
    }
