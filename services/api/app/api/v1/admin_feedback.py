"""
Admin API endpoints for extraction feedback and learning loops.

Endpoints for:
- Manual feedback/ratings from admin UI
- Confidence calibration reports
- Domain pattern analysis
- A/B test result recording
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.feedback_loops import FeedbackLoopService

router = APIRouter(prefix="/feedback", tags=["admin-feedback"])


# ─── Request/Response schemas ─────────────────────────────────────────────

class ManualFeedbackRequest(BaseModel):
    """Submit a manual extraction rating."""
    extraction_id: UUID
    rating: str  # "correct" | "partial" | "wrong"
    reviewer_id: str
    notes: str = ""


class ManualFeedbackResponse(BaseModel):
    """Confirmation of feedback recorded."""
    feedback_id: UUID
    extraction_id: UUID
    rating: str
    created_at: str


class ConfidenceCalibrationItem(BaseModel):
    """One bucket in confidence calibration data."""
    claimed_confidence: float
    actual_accuracy: float
    sample_count: int
    is_calibrated: bool


class ConfidenceCalibrationReport(BaseModel):
    """Confidence calibration report for a prompt version."""
    prompt_version: str
    lookback_days: int
    calibration_data: list[ConfidenceCalibrationItem]
    overall_calibrated: bool


class DomainPatternResponse(BaseModel):
    """Extraction patterns for a domain/store."""
    typical_fields: list[str]
    typical_confidence: float
    common_gaps: list[str]
    error_count: int
    sample_count: int


# ─── Manual feedback endpoint ────────────────────────────────────────────

@router.post("/manual-rating", response_model=ManualFeedbackResponse)
async def submit_manual_rating(
    req: ManualFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a manual extraction rating from admin UI.

    Used for spot-checking extractions to calibrate confidence scores
    and identify systematic issues.

    Args:
        extraction_id: RawExtraction ID being rated
        rating: "correct", "partial", or "wrong"
        reviewer_id: User ID of reviewer
        notes: Optional notes explaining the rating

    Returns:
        Confirmation with feedback ID and timestamp
    """
    if req.rating not in ("correct", "partial", "wrong"):
        raise HTTPException(status_code=400, detail=f"Invalid rating: {req.rating}")

    service = FeedbackLoopService(db)
    feedback = await service.record_manual_rating(
        req.extraction_id,
        req.rating,
        req.reviewer_id,
        req.notes,
    )
    await service.commit()

    return ManualFeedbackResponse(
        feedback_id=feedback.id,
        extraction_id=feedback.raw_extraction_id,
        rating=feedback.rating,
        created_at=feedback.created_at.isoformat(),
    )


# ─── Confidence calibration report ───────────────────────────────────────

@router.get("/confidence-calibration", response_model=ConfidenceCalibrationReport)
async def get_confidence_calibration(
    prompt_version: str = Query("v1.0.0", description="Prompt version to analyze"),
    lookback_days: int = Query(30, ge=7, le=365, description="Days of data to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get confidence calibration report for a prompt version.

    Measures how well claimed confidence matches actual quality by:
    1. Grouping extractions by confidence bucket (0.0–1.0)
    2. Measuring actual accuracy from manual ratings
    3. Comparing claimed vs actual confidence

    Well-calibrated prompt: actual ≈ claimed (|difference| < 0.10)

    Returns:
        Calibration data with one row per confidence bucket
    """
    service = FeedbackLoopService(db)
    calibration = await service.measure_confidence_calibration(
        prompt_version,
        lookback_days,
    )

    # Determine if overall calibrated
    if not calibration:
        overall_calibrated = False
    else:
        # If >80% of buckets are well-calibrated, consider prompt well-calibrated
        calibrated_count = sum(1 for c in calibration if c["is_calibrated"])
        overall_calibrated = (calibrated_count / len(calibration)) > 0.8

    return ConfidenceCalibrationReport(
        prompt_version=prompt_version,
        lookback_days=lookback_days,
        calibration_data=[
            ConfidenceCalibrationItem(**data) for data in calibration
        ],
        overall_calibrated=overall_calibrated,
    )


# ─── Domain pattern analysis ──────────────────────────────────────────────

@router.get("/domain-patterns/{store_id}", response_model=DomainPatternResponse)
async def get_domain_patterns(
    store_id: UUID,
    lookback_days: int = Query(30, ge=7, le=365, description="Days of data to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze extraction patterns for a domain/store.

    Returns which fields are typically present, which are commonly missing,
    and average confidence. Used to inform prompt context injection.

    Returns:
        Pattern analysis with typical fields, gaps, and error rates
    """
    service = FeedbackLoopService(db)
    patterns = await service.get_domain_extraction_patterns(
        store_id,
        lookback_days,
    )

    return DomainPatternResponse(**patterns)


# ─── A/B test recording ────────────────────────────────────────────────

class ABTestRequest(BaseModel):
    """Record result of A/B test comparing two prompt versions."""
    extraction_id_a: UUID
    extraction_id_b: UUID
    prompt_version_a: str
    prompt_version_b: str
    page_url: str


class ABTestResponse(BaseModel):
    """A/B test result."""
    feedback_id: UUID
    winner: str  # "a" | "b" | "tie"
    confidence_a: float
    confidence_b: float


@router.post("/ab-test", response_model=ABTestResponse)
async def record_ab_test(
    req: ABTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record A/B test result comparing two prompt versions on same page.

    Used to evaluate prompt improvements in production.
    If version B consistently wins, it can be promoted to default.

    Returns:
        Test result with winner and confidence scores
    """
    service = FeedbackLoopService(db)
    feedback = await service.record_ab_test(
        req.extraction_id_a,
        req.extraction_id_b,
        req.prompt_version_a,
        req.prompt_version_b,
        req.page_url,
    )

    if not feedback:
        raise HTTPException(status_code=404, detail="Could not find both extractions")

    await service.commit()

    return ABTestResponse(
        feedback_id=feedback.id,
        winner=feedback.winner,
        confidence_a=feedback.confidence_a or 0.0,
        confidence_b=feedback.confidence_b or 0.0,
    )


# ─── Feedback summary ──────────────────────────────────────────────────

class FeedbackSummary(BaseModel):
    """Summary of feedback collected."""
    total_manual_reviews: int
    total_price_anomalies: int
    total_ab_tests: int
    avg_manual_accuracy: float


@router.get("/summary", response_model=FeedbackSummary)
async def get_feedback_summary(
    lookback_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of feedback signals collected.

    Returns counts and aggregate metrics useful for monitoring
    feedback loop health.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select, and_
    from app.models.extraction_feedback import ExtractionFeedback

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    # Get manual reviews
    manual_stmt = (
        select(ExtractionFeedback)
        .where(
            and_(
                ExtractionFeedback.feedback_type == "manual_review",
                ExtractionFeedback.created_at >= cutoff,
            )
        )
    )
    manual_reviews = (await db.execute(manual_stmt)).scalars().all()

    # Calculate accuracy
    if manual_reviews:
        correct_count = sum(1 for r in manual_reviews if r.rating == "correct")
        avg_accuracy = correct_count / len(manual_reviews)
    else:
        avg_accuracy = 0.0

    # Get price anomalies
    price_stmt = (
        select(ExtractionFeedback)
        .where(
            and_(
                ExtractionFeedback.feedback_type == "price_anomaly",
                ExtractionFeedback.created_at >= cutoff,
            )
        )
    )
    price_anomalies = (await db.execute(price_stmt)).scalars().all()

    # Get A/B tests
    ab_stmt = (
        select(ExtractionFeedback)
        .where(
            and_(
                ExtractionFeedback.feedback_type == "ab_test",
                ExtractionFeedback.created_at >= cutoff,
            )
        )
    )
    ab_tests = (await db.execute(ab_stmt)).scalars().all()

    return FeedbackSummary(
        total_manual_reviews=len(manual_reviews),
        total_price_anomalies=len(price_anomalies),
        total_ab_tests=len(ab_tests),
        avg_manual_accuracy=round(avg_accuracy, 2),
    )
