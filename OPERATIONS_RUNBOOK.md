# Grounds — Operations Runbook

Quick reference for common operational tasks.

---

## Triggering crawls manually (T-038)

The ingestion worker processes jobs from the Redis queue automatically on a schedule.
To trigger a crawl immediately for a specific store, use the admin UI or the worker CLI:

### Via admin UI
1. Go to **http://localhost:3001/sources**
2. Find the store
3. Click **Trigger crawl** on the row

### Via terminal (worker CLI)
```bash
# Trigger a single store crawl immediately
docker exec coffee_worker python3 -c "
import asyncio, sys
sys.path.insert(0, '/app/services/api')
from ingestion.queue import JobQueue, IngestionJob
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def enqueue(domain, strategy='shopify'):
    q = JobQueue('redis://redis:6379/0')
    await q.connect()
    async with AsyncSessionLocal() as s:
        r = await s.execute(text(f\"SELECT id FROM stores WHERE domain='{domain}'\"))
        row = r.fetchone()
        if not row:
            print(f'Store {domain} not found in DB')
            return
        job = IngestionJob(store_id=str(row[0]), store_domain=domain,
                           parser_strategy=strategy, priority=10)
        await q.enqueue(job)
        print(f'Enqueued {domain}')
    await q.close()

asyncio.run(enqueue('www.ravecoffee.co.uk'))
"
```

Replace `www.ravecoffee.co.uk` and the strategy with any store domain in your DB.

### Check queue depth
```bash
docker exec coffee_redis redis-cli llen QUEUE_SCHEDULED
docker exec coffee_redis redis-cli llen QUEUE_PROCESSING
docker exec coffee_redis redis-cli llen QUEUE_DEAD
```

### View worker logs live
```bash
docker compose logs worker -f --tail=50
```

---

## Running source detection (T-023)

Source detection probes each store's domain to determine the correct parser strategy
(shopify, schema_org, html). Run it after importing new roasters.

### Trigger via admin UI
1. Go to **http://localhost:3001/sources**
2. Click **Rescan** on any store row to re-detect that store's strategy

### Run for all stores without a strategy
```bash
docker exec coffee_api python3 -c "
import asyncio
async def rescan_all():
    from app.core.database import AsyncSessionLocal
    from app.models.store import Store
    from app.services.source_inventory.importer import SourceInventoryImporter
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        importer = SourceInventoryImporter(session)
        result = await session.execute(
            select(Store).where(Store.active_flag == True)
        )
        stores = result.scalars().all()
        print(f'Rescanning {len(stores)} stores...')
        for store in stores:
            try:
                summary = await importer.rescan_store(store)
                print(f'  {store.domain}: {summary[\"parser_strategy\"]} (reachable={summary[\"reachable\"]})')
            except Exception as e:
                print(f'  {store.domain}: ERROR {e}')
        await session.commit()
asyncio.run(rescan_all())
"
```

---

## Running entity resolution (T-024)

Entity resolution links ingested listings to canonical beans.
Run after ingestion completes to make new coffees appear on the public site.

```bash
# Process 500 unlinked listings (safe to run multiple times)
docker exec coffee_api python scripts/run_entity_resolution.py

# Process 100 listings (faster test)
docker exec coffee_api python scripts/run_entity_resolution.py --limit 100

# Dry run — see what would happen without writing
docker exec coffee_api python scripts/run_entity_resolution.py --dry-run
```

After running, check how many listings are now linked:
```bash
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
SELECT
  COUNT(*) as total,
  COUNT(canonical_bean_id) as linked,
  COUNT(*) - COUNT(canonical_bean_id) as unlinked
FROM bean_listings;
"
```

---

## Reviewing match proposals (T-025)

After entity resolution runs, low-confidence matches go to the review queue.

1. Go to **http://localhost:3001/review/matches**
2. Set filter to **Pending**
3. For each match:
   - Compare the **raw listing** (left) against the **proposed canonical bean** (right)
   - Check the confidence signals (exact match, fuzzy score, embedding score)
   - Click **Accept** to link them, or **Reject** to create a new canonical bean
4. Accepted matches will appear on the public site within seconds

### Check review queue size
```bash
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
SELECT review_status, COUNT(*) FROM canonical_matches GROUP BY review_status;
"
```

### Auto-run entity resolution + check results
```bash
docker exec coffee_api python scripts/run_entity_resolution.py --limit 200
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
SELECT review_status, COUNT(*) FROM canonical_matches GROUP BY review_status;
"
```

---

## Monitoring ingestion health

### Check recent ingestion runs
```bash
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
SELECT s.name, ir.status, ir.records_created, ir.records_updated, ir.completed_at
FROM ingestion_runs ir
JOIN stores s ON s.id = ir.store_id
ORDER BY ir.started_at DESC
LIMIT 20;
"
```

### Check total listings and canonical beans
```bash
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
SELECT
  (SELECT COUNT(*) FROM bean_listings) as listings,
  (SELECT COUNT(*) FROM canonical_beans) as canonical_beans,
  (SELECT COUNT(*) FROM bean_listings WHERE canonical_bean_id IS NULL) as unlinked,
  (SELECT COUNT(*) FROM stores WHERE active_flag = true) as active_stores;
"
```

### Check dead letter queue (failed jobs)
```bash
docker exec coffee_redis redis-cli lrange QUEUE_DEAD 0 -1 | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        j = json.loads(line.strip())
        print(f\"{j.get('store_domain', '?')} — {j.get('error', '?')[:80]}\")
    except: pass
"
```

---

## Reset and restart

### Restart all services
```bash
docker compose restart api worker
```

### Full reset (WARNING: deletes all data)
```bash
docker compose down -v
docker compose up -d postgres redis
# wait 20 seconds
docker compose up -d api
docker exec coffee_api python scripts/seed.py
docker exec coffee_api python scripts/seed_extended.py
docker exec coffee_api alembic stamp head
docker compose up -d worker
```
