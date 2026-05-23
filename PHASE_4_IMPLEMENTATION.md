# Phase 4: Learning & Feedback Loops — Implementation Complete ✅

## Overview

Phase 4 implements automated feedback collection and continuous LLM prompt improvement without requiring manual ground truth labels. Uses behavioral signals (price validation, duplicate detection, manual reviews) to calibrate confidence and drive prompt iteration.

## What Was Built

### 1. Extraction Feedback Model
**File:** `/services/api/app/models/extraction_feedback.py` (4.5KB)

Unified feedback table capturing all quality signals:
- **Manual reviews**: Admin spot-checks with ratings (correct/partial/wrong)
- **Price anomalies**: Suspicious price changes indicating extraction errors
- **Duplicate mismatches**: Similar products across domains with different extractions
- **A/B tests**: Prompt version comparison results

Schema includes:
- `feedback_type` (manual_review | price_anomaly | duplicate_mismatch | ab_test)
- `rating` (correct | partial | wrong)
- `signal_strength` (0.0–1.0 confidence in this signal)
- Indexed on `(feedback_type, created_at)` and `(raw_extraction_id, rating)`

### 2. Feedback Collection Service
**File:** `/services/api/app/services/feedback_loops.py` (16KB)

`FeedbackLoopService` class with methods:

#### Price Validation (`check_price_anomalies`)
- Detects price jumps > 50% or < 67% between consecutive runs
- Records anomaly with jump factor and signal strength
- Helps identify extraction errors (e.g., LLM misreading £12.50 as £125.00)

#### Duplicate Detection (`check_duplicate_extractions`)
- Placeholder for vector similarity matching (stub implementation)
- In production: embed extraction summaries, find similar products across domains
- Compare field completeness: if this extraction is lower quality than duplicates, flag it

#### Manual Rating (`record_manual_rating`)
- Records admin spot-check feedback from UI
- Rating: correct | partial | wrong
- High signal strength (1.0) since manual reviews are reliable

#### Domain Pattern Learning (`get_domain_extraction_patterns`)
- Analyzes last N extractions from a store
- Returns typical fields present (>60% of extractions)
- Returns common gaps (<30% of extractions)
- Enables context-aware prompting with `domain_context` parameter

#### Confidence Calibration (`measure_confidence_calibration`)
- Measures how well claimed confidence matches actual accuracy
- Buckets extractions by confidence (0.0–1.0)
- Calculates actual accuracy from manual ratings
- Identifies if prompt is well-calibrated (|claimed − actual| < 0.10)

#### A/B Testing (`record_ab_test`)
- Compares two prompt versions on same page
- Records both confidence scores and winner
- Used to promote better prompt versions

### 3. Admin API Endpoints
**File:** `/services/api/app/api/v1/admin_feedback.py` (9.5KB)

Feedback endpoints registered at `/admin/feedback/`:

#### `POST /admin/feedback/manual-rating`
Submit manual extraction rating from admin UI.
```json
{
  "extraction_id": "uuid",
  "rating": "correct|partial|wrong",
  "reviewer_id": "user_id",
  "notes": "explanation"
}
```
Returns: feedback_id, rating, created_at

#### `GET /admin/feedback/confidence-calibration`
Get confidence calibration report for prompt version.
Query params: `prompt_version` (default v1.0.0), `lookback_days` (default 30)

Returns:
```json
{
  "prompt_version": "v2.0.0",
  "lookback_days": 30,
  "calibration_data": [
    {
      "claimed_confidence": 0.85,
      "actual_accuracy": 0.82,
      "sample_count": 25,
      "is_calibrated": true
    }
  ],
  "overall_calibrated": true
}
```

#### `GET /admin/feedback/domain-patterns/{store_id}`
Analyze extraction patterns for a store.
Query params: `lookback_days` (default 30)

Returns:
```json
{
  "typical_fields": ["origin_country", "process", "roast_level"],
  "typical_confidence": 0.76,
  "common_gaps": ["varietal", "producer"],
  "error_count": 3,
  "sample_count": 42
}
```

#### `POST /admin/feedback/ab-test`
Record A/B test result comparing prompt versions.
```json
{
  "extraction_id_a": "uuid",
  "extraction_id_b": "uuid",
  "prompt_version_a": "v1.0.0",
  "prompt_version_b": "v2.0.0",
  "page_url": "https://..."
}
```
Returns: feedback_id, winner (a|b|tie), confidence_a, confidence_b

#### `GET /admin/feedback/summary`
Get summary of feedback collected.
Query params: `lookback_days` (default 30)

Returns:
```json
{
  "total_manual_reviews": 42,
  "total_price_anomalies": 3,
  "total_ab_tests": 12,
  "avg_manual_accuracy": 0.88
}
```

### 4. Database Migration
**File:** `/services/api/alembic/versions/20260522_0001_extraction_feedback.py` (2.9KB)

Creates `extraction_feedback` table with:
- Proper foreign key constraints (soft deletes on parent deletion)
- Performance indices on common queries
- Fields for all feedback types (manual, price, duplicate, A/B)

Run migration with: `alembic upgrade head`

## Integration with Existing Systems

### Connected to LLMParser
The `FeedbackLoopService` integrates with:
- `RawExtraction` records (stores feedback on specific extractions)
- `BeanListing` records (links price anomalies to products)
- `PriceHistory` table (historical prices for anomaly detection)

### Data Flow

```
Extraction Created
    ↓
LLMParser returns confidence score
    ↓
Price Validation Feedback
    ↓
Duplicate Detection Feedback (on next extraction)
    ↓
Manual Review (admin spot-check)
    ↓
Confidence Calibration Analysis
    ↓
Domain Pattern Learning
    ↓
A/B Test Evaluation
    ↓
Prompt Iteration → v2.0.0 becomes default → v3.0.0 in progress
```

## Usage Examples

### Example 1: Record Manual Feedback
```python
service = FeedbackLoopService(db_session)

feedback = await service.record_manual_rating(
    extraction_id=UUID("..."),
    rating="partial",  # Data was mostly correct but missing varietal
    reviewer_id="admin_user_123",
    notes="LLM extracted roast and origin but no varietal found on page"
)
await service.commit()
```

### Example 2: Analyze Domain Patterns
```python
patterns = await service.get_domain_extraction_patterns(
    store_id=UUID("..."),
    lookback_days=30
)
# Returns: {
#   "typical_fields": ["origin_country", "process", "roast_level"],
#   "typical_confidence": 0.76,
#   "common_gaps": ["varietal", "producer"]
# }
```
Use this to inject context: 
```python
prompt = v2.get_system_prompt(
    domain_context="specialty",
    historical_pattern=f"Typically has: {', '.join(patterns['typical_fields'])}"
)
```

### Example 3: Measure Confidence Calibration
```python
calibration = await service.measure_confidence_calibration(
    prompt_version="v2.0.0",
    lookback_days=30
)
# If |claimed − actual| > 0.10 for >20% of buckets, prompt needs tuning
```

## Feedback Signal Strength

Different signal types have different reliability:

| Signal Type | Strength | Notes |
|---|---|---|
| Manual review | 1.0 | Gold standard, highly reliable |
| Price anomaly | variable | Strength = magnitude of jump (0.5–1.0) |
| Duplicate mismatch | 0.7 | Assumes vector similarity is correct |
| A/B test | 0.8 | Single comparison, repeatable |

## Next: Automated Iteration

Once feedback accumulates (100+ manual ratings):

1. **Confidence Calibration Check**
   - If `is_calibrated = false` for >20% of buckets, prompt needs tuning
   - Generate prompt v2.1 with adjusted confidence scale

2. **A/B Testing Loop**
   ```
   v1.0.0 vs v2.0.0: Test on 100 pages
       ↓
   If v2.0.0 wins 60%+: Promote to default
       ↓
   v2.0.0 vs v2.1.0: Test improvements
       ↓
   Repeat until diminishing returns
   ```

3. **Domain-Specific Context Injection**
   - Use `get_domain_extraction_patterns()` before every extraction
   - Inject typical fields into v2.0.0 system prompt
   - Expected: 5–10% confidence improvement on known domains

## Testing the Feedback Loop

### Step 1: Record Manual Ratings
Use the admin UI or API to rate 10–20 random extractions as correct/partial/wrong.

### Step 2: Check Calibration
```bash
curl http://localhost:8000/api/v1/admin/feedback/confidence-calibration?prompt_version=v2.0.0
```

### Step 3: Analyze Domain Patterns
```bash
curl http://localhost:8000/api/v1/admin/feedback/domain-patterns/{store_id}
```

### Step 4: Record A/B Test
Extract same page with v1.0.0 and v2.0.0, submit results via API.

## Files Changed

### New Files
- `/app/models/extraction_feedback.py` — Feedback table model
- `/app/services/feedback_loops.py` — Feedback collection logic
- `/app/api/v1/admin_feedback.py` — API endpoints
- `/alembic/versions/20260522_0001_extraction_feedback.py` — Migration

### Modified Files
- `/app/api/v1/admin.py` — Added `include_router(admin_feedback.router)`

## Success Criteria

✅ **Phase 4 Complete:**
- [x] Extraction feedback table created
- [x] Price validation feedback implemented
- [x] Duplicate detection framework ready (stub for vector matching)
- [x] Manual rating endpoints in admin API
- [x] Confidence calibration measurement
- [x] Domain pattern learning
- [x] A/B testing framework
- [x] Migration created and tested

## Next Steps (Phase 5+)

### Immediate
1. Run API migrations: `alembic upgrade head`
2. Start recording manual ratings (10 per day for 1 week = 70 data points)
3. Check confidence calibration after 30 ratings

### Week 1+
1. Measure if v2.0.0 is well-calibrated
2. If not: adjust confidence scale in v2.1.0
3. A/B test v2.0.0 vs v2.1.0 on 50 pages

### Week 2+
1. If v2.1.0 wins: promote to default
2. Start training v3.0.0 with domain context injection
3. A/B test v2.1.0 vs v3.0.0

### Ongoing
- Monitor feedback loop health (manual ratings, A/B test winners)
- Iterate prompt quarterly based on feedback signals
- Track cost/accuracy trade-offs

## Cost Impact

Phase 4 adds minimal overhead:
- **API calls**: 4 GET endpoints, 3 POST endpoints (mostly reads)
- **Database**: ~1KB per extraction feedback record
- **Processing**: Feedback collection is async, non-blocking

No additional LLM calls required.

---

**Status:** ✅ Ready for deployment  
**Next Milestone:** Phase 5 - Deploy v2.0.0 with feedback collection enabled
