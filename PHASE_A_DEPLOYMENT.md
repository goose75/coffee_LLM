# Phase A Deployment: HTML Multi-Product Extraction

## Overview

**Goal:** Deploy the HTML extraction fix and verify 17grams extracts products (target: ~700)

**Deployment Steps:**
1. ✅ Code changes implemented (DONE)
2. ⏳ Build Docker image with updated code (THIS STEP)
3. ⏳ Verify container starts
4. ⏳ Test extraction on 17grams
5. ⏳ Verify results in database
6. ⏳ Approve production rollout

**Timeline:** 30-45 minutes

---

## Step 1: Verify Code Changes

### Check that files were modified correctly

```bash
# Verify product_listing_extractor.py exists
ls -lh /Users/travisganz/coffee_LLM/services/api/app/services/html/product_listing_extractor.py

# Verify extractor.py was updated
grep -n "ProductListingExtractor" /Users/travisganz/coffee_LLM/services/api/app/services/html/extractor.py

# Both files should compile
python3 -m py_compile /Users/travisganz/coffee_LLM/services/api/app/services/html/product_listing_extractor.py
python3 -m py_compile /Users/travisganz/coffee_LLM/services/api/app/services/html/extractor.py

echo "✅ Code verification passed"
```

### Expected Output
```
-rw-r--r-- 1 user staff 5.2K May 24 12:34 product_listing_extractor.py
... ProductListingExtractor ...
✅ Code verification passed
```

---

## Step 2: Build Docker Image

### Navigate to API directory and build

```bash
cd /Users/travisganz/coffee_LLM/services/api

# Show current image status
echo "=== CURRENT IMAGE STATUS ==="
docker images | grep coffee_api

# Build the updated image
echo "=== BUILDING NEW IMAGE ==="
docker build -t coffee_api:latest .

# This will:
# - Pull base Python image
# - Install requirements.txt
# - Copy app code (including our changes)
# - Build image (~2-5 minutes)

# Verify build succeeded
echo "=== BUILD VERIFICATION ==="
docker images | grep coffee_api
echo "✅ Image built successfully"
```

### Expected Output
```
REPOSITORY    TAG       IMAGE ID       CREATED        SIZE
coffee_api    latest    abc123def456   x seconds ago   1.2GB
✅ Image built successfully
```

---

## Step 3: Stop Old Container and Start New One

```bash
# Stop the old container
echo "=== STOPPING OLD CONTAINER ==="
docker-compose down coffee_api

# Verify it stopped
sleep 2
docker ps | grep coffee_api && echo "⚠️  Container still running" || echo "✅ Container stopped"

# Start new container with updated image
echo "=== STARTING NEW CONTAINER ==="
docker-compose up -d coffee_api

# Wait for container to be ready
echo "Waiting for API to be ready..."
sleep 10

# Verify it's running
docker ps | grep coffee_api
echo "✅ New container started"

# Check logs for any startup errors
echo "=== CONTAINER LOGS (last 20 lines) ==="
docker logs coffee_api | tail -20
```

### Expected Output
```
✅ Container stopped
✅ New container started
CONTAINER ID  IMAGE              COMMAND           CREATED
abc123def456  coffee_api:latest  "python -m uvic..." 5 seconds ago

(No ERROR messages in logs)
✅ API ready
```

---

## Step 4: Verify API is Responding

```bash
# Test API health endpoint
echo "=== TESTING API HEALTH ==="
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool

# Test that extraction endpoints are accessible
echo ""
echo "=== TESTING EXTRACTION ENDPOINTS ==="
curl -s http://localhost:8000/api/v1/admin/matching/status 2>&1 | head -20
```

### Expected Output
```json
{
  "status": "ok",
  "timestamp": "2026-05-24T..."
}
```

---

## Step 5: Trigger Fresh Ingestion on 17grams

```bash
# Get 17grams store ID from database
STORE_ID=$(docker exec coffee_api python3 -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.store import Store
from sqlalchemy import select

async def get_store():
    async with AsyncSessionLocal() as db:
        stmt = select(Store).where(Store.domain == '17grams.co.uk')
        store = (await db.execute(stmt)).scalar_one_or_none()
        if store:
            print(store.id)

asyncio.run(get_store())
" 2>/dev/null)

if [ -z "$STORE_ID" ]; then
    echo "⚠️  Could not find 17grams store ID"
    echo "Using API endpoint instead..."
    
    # Trigger via API endpoint
    echo "=== TRIGGERING FRESH INGESTION ==="
    curl -X POST http://localhost:8000/api/v1/admin/sources/17grams.co.uk/reingest \
      -H "Content-Type: application/json" \
      -w "\n\nHTTP Status: %{http_code}\n" \
      -s
else
    echo "Found 17grams store ID: $STORE_ID"
    echo "=== TRIGGERING FRESH INGESTION ==="
    curl -X POST "http://localhost:8000/api/v1/admin/sources/$STORE_ID/reingest" \
      -H "Content-Type: application/json" \
      -w "\n\nHTTP Status: %{http_code}\n" \
      -s
fi
```

### Expected Output
```json
{
  "status": "queued",
  "message": "Fresh ingestion queued for 17grams.co.uk",
  "total_pages": 46,
  "estimated_products": 700
}

HTTP Status: 200
```

---

## Step 6: Monitor Ingestion Progress

```bash
# Check ingestion status
echo "=== MONITORING INGESTION (check every 10 seconds) ==="

for i in {1..12}; do
    echo ""
    echo "Check $i (at $(date '+%H:%M:%S')):"
    
    docker exec coffee_api python3 << 'PYTHON'
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.ingestion_run import IngestionRun
from app.models.store import Store
from sqlalchemy import select, desc

async def check_status():
    async with AsyncSessionLocal() as db:
        # Find 17grams
        store_stmt = select(Store).where(Store.domain == '17grams.co.uk')
        store = (await db.execute(store_stmt)).scalar_one_or_none()
        
        if not store:
            print("❌ Store not found")
            return
        
        # Get latest ingestion run
        run_stmt = (
            select(IngestionRun)
            .where(IngestionRun.store_id == store.id)
            .order_by(desc(IngestionRun.started_at))
            .limit(1)
        )
        run = (await db.execute(run_stmt)).scalar_one_or_none()
        
        if not run:
            print("⏳ No ingestion runs yet")
            return
        
        print(f"Status: {run.status}")
        print(f"Pages fetched: {run.pages_fetched}")
        print(f"Pages failed: {run.pages_failed}")
        print(f"Records seen: {run.records_seen}")
        print(f"Records created: {run.records_created}")
        print(f"Records updated: {run.records_updated}")
        print(f"Records unchanged: {run.records_unchanged}")
        
        if run.records_created > 0:
            print(f"✅ SUCCESS: {run.records_created} products extracted!")
        elif run.status == "completed" and run.records_created == 0:
            print(f"⚠️  ISSUE: Pages processed but 0 products extracted")
            if run.errors:
                print(f"Errors: {run.errors[:2]}")
        elif run.status == "running":
            print("⏳ Still running...")

asyncio.run(check_status())
PYTHON
    
    # Stop monitoring if extraction is done
    STATUS=$(docker exec coffee_api python3 -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.ingestion_run import IngestionRun
from app.models.store import Store
from sqlalchemy import select, desc

async def check():
    async with AsyncSessionLocal() as db:
        store_stmt = select(Store).where(Store.domain == '17grams.co.uk')
        store = (await db.execute(store_stmt)).scalar_one_or_none()
        if store:
            run_stmt = select(IngestionRun).where(IngestionRun.store_id == store.id).order_by(desc(IngestionRun.started_at)).limit(1)
            run = (await db.execute(run_stmt)).scalar_one_or_none()
            if run and run.status in ('completed', 'partial', 'failed'):
                print(run.status)

asyncio.run(check())
" 2>/dev/null)
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "partial" ] || [ "$STATUS" = "failed" ]; then
        echo ""
        echo "✅ Ingestion completed!"
        break
    fi
    
    if [ $i -lt 12 ]; then
        sleep 10
    fi
done
```

### Expected Output (Success Case)
```
Check 1 (at 12:30:45):
⏳ Still running...

Check 2 (at 12:30:55):
Status: running
Pages fetched: 15
Records seen: 120
Records created: 45

...

Check 5 (at 12:31:35):
Status: completed
Pages fetched: 46
Pages failed: 0
Records seen: 736
Records created: 650
Records updated: 86
Records unchanged: 0
✅ SUCCESS: 650 products extracted!

✅ Ingestion completed!
```

---

## Step 7: Verify Results in Database

```bash
# Get detailed statistics
docker exec coffee_api python3 << 'PYTHON'
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.store import Store
from app.models.bean_listing import BeanListing
from sqlalchemy import select, func

async def verify():
    async with AsyncSessionLocal() as db:
        # Find 17grams
        store_stmt = select(Store).where(Store.domain == '17grams.co.uk')
        store = (await db.execute(store_stmt)).scalar_one_or_none()
        
        if not store:
            print("❌ Store not found")
            return
        
        # Get product statistics
        listings_stmt = select(func.count()).select_from(BeanListing).where(BeanListing.store_id == store.id)
        total = (await db.execute(listings_stmt)).scalar()
        
        # Get confidence statistics
        confidence_stmt = (
            select(
                func.avg(BeanListing.confidence).label('avg_confidence'),
                func.min(BeanListing.confidence).label('min_confidence'),
                func.max(BeanListing.confidence).label('max_confidence'),
            )
            .where(BeanListing.store_id == store.id)
        )
        stats = (await db.execute(confidence_stmt)).first()
        
        print("=" * 60)
        print("17GRAMS EXTRACTION RESULTS")
        print("=" * 60)
        print(f"Total products extracted: {total}")
        print(f"Average confidence: {stats[0]:.2f}" if stats[0] else "N/A")
        print(f"Min confidence: {stats[1]:.2f}" if stats[1] else "N/A")
        print(f"Max confidence: {stats[2]:.2f}" if stats[2] else "N/A")
        print("")
        
        if total > 100:
            print("✅ SUCCESS: Phase A extraction is working!")
            print(f"   Extracted {total} products (target: ~700)")
            print(f"   Avg confidence: {stats[0]:.2f} (target: ≥ 0.4)")
        elif total > 0:
            print("⚠️  PARTIAL SUCCESS: Some products extracted")
            print(f"   Got {total}, expected ~700")
            print(f"   May need HTML selector tuning")
        else:
            print("❌ NO PRODUCTS EXTRACTED")
            print(f"   Listing extractor may not be detecting containers")

asyncio.run(verify())
PYTHON
```

### Expected Output (Success)
```
============================================================
17GRAMS EXTRACTION RESULTS
============================================================
Total products extracted: 650
Average confidence: 0.62
Min confidence: 0.35
Max confidence: 0.85

✅ SUCCESS: Phase A extraction is working!
   Extracted 650 products (target: ~700)
   Avg confidence: 0.62 (target: ≥ 0.4)
```

---

## Step 8: Check Auto-Matching Status

```bash
# Trigger auto-matching for the newly extracted products
echo "=== TRIGGERING AUTO-MATCHING ==="
curl -X POST "http://localhost:8000/api/v1/admin/matching/auto-match-new-listings?limit=1000" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -s | python3 -m json.tool

# Expected:
# - status: "queued"
# - total_unmatched: 650+ (17grams new products)
# - background_task_queued: true
```

---

## Step 9: Final Verification

```bash
# Check logs for any errors
echo "=== CHECKING LOGS FOR ERRORS ==="
docker logs coffee_api 2>&1 | grep -i "error\|exception" | tail -10

# If clean logs, Phase A is successful
docker logs coffee_api 2>&1 | tail -20 | grep -q "error" && echo "⚠️  Errors found" || echo "✅ Logs clean"
```

---

## Success Criteria

Phase A deployment is **SUCCESSFUL** when:

| Metric | Target | Status |
|--------|--------|--------|
| API starts without errors | ✅ | Check step 3 |
| 17grams ingestion completes | ✅ | Check step 6 |
| Products extracted | > 100 | Check step 7 |
| Average confidence | ≥ 0.4 | Check step 7 |
| Auto-matching queued | 100+ listings | Check step 8 |
| No critical errors | 0 errors | Check step 9 |

**If all ✅:** Phase A is DEPLOYED

**If any ❌:** Debug before proceeding to Phase B

---

## Troubleshooting Guide

### Issue: "Products extracted but confidence too low (< 0.4)"

**Cause:** HTML selectors not matching 17grams page structure

**Solution:**
1. Manually check a 17grams product page structure
2. Update `PRODUCT_CONTAINER_SELECTORS` in `product_listing_extractor.py`
3. Add site-specific selectors if needed
4. Rebuild image and retry

### Issue: "0 products extracted"

**Cause:** Listing containers not being detected

**Check:**
```python
# Test container detection
from app.services.html.product_listing_extractor import ProductListingExtractor

extractor = ProductListingExtractor()
# Fetch 17grams page and test
```

**Solution:**
1. Verify Elementor selectors are in the list
2. Add custom selectors for 17grams if needed
3. Check if page uses different markup

### Issue: "API won't start"

**Cause:** Syntax error in code or missing import

**Check:**
```bash
# Check Python syntax
python3 -m py_compile /path/to/file.py

# Check import
python3 -c "from app.services.html.product_listing_extractor import ProductListingExtractor"

# Check container logs
docker logs coffee_api | grep -i "error"
```

### Issue: "Ingestion hangs (> 5 minutes)"

**Cause:** Timeout or infinite loop in extractor

**Solution:**
1. Kill ingestion: `docker restart coffee_api`
2. Check for infinite loops in `ProductListingExtractor`
3. Reduce container count in test

---

## Deployment Checklist

- [ ] **Pre-Deployment**
  - [ ] Code files verified to exist
  - [ ] Python syntax check passed
  - [ ] Docker image exists or can build

- [ ] **Deployment**
  - [ ] Old container stopped
  - [ ] New image built successfully
  - [ ] New container started
  - [ ] API health check passed

- [ ] **Testing**
  - [ ] 17grams ingestion triggered
  - [ ] Products extracted (> 100)
  - [ ] Confidence >= 0.4
  - [ ] Auto-matching queued

- [ ] **Verification**
  - [ ] Database shows new products
  - [ ] No critical errors in logs
  - [ ] All metrics meet targets

- [ ] **Post-Deployment**
  - [ ] Document results
  - [ ] Update status in production
  - [ ] Monitor for 1 hour
  - [ ] Proceed to Phase B if successful

---

## Rollback Plan (If Issues Found)

If Phase A deployment has critical issues:

```bash
# Stop current container
docker-compose down coffee_api

# Revert to previous image (if saved)
docker tag coffee_api:previous coffee_api:latest

# Restart with old image
docker-compose up -d coffee_api

# Verify old version is working
curl http://localhost:8000/api/v1/health
```

---

## Next: Phase B Planning

Once Phase A is confirmed successful:
1. ✅ Verify 17grams extraction working
2. ✅ Confirm auto-matching active
3. 🟡 Move to Phase B: Schema.org activation
   - Identify pilot stores
   - Begin Week 1 testing
   - Follow 7-week rollout timeline

**Estimated Phase A time:** 45 minutes  
**Estimated Phase B start:** After Phase A verification

---

**Document Version:** 1.0  
**Status:** READY FOR DEPLOYMENT  
**Created:** May 24, 2026
