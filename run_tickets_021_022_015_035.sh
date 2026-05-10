#!/bin/bash
# Tickets 021, 022, 015, 035 — Run in order from coffee_LLM root
# Usage: bash run_tickets_021_022_015_035.sh
set -e

echo ""
echo "══════════════════════════════════════════════════════"
echo "  TICKET-021: Import 50 UK roasters"
echo "══════════════════════════════════════════════════════"

# Place the files (run this AFTER copying outputs/ files to correct locations)
mkdir -p services/api/data

# Copy roasters.csv into the container
echo "→ Copying roasters.csv into container..."
docker cp services/api/data/roasters.csv coffee_api:/app/data/roasters.csv

# Run the import
echo "→ Running import..."
docker exec coffee_api python scripts/import_roasters.py

# Verify
echo "→ Verifying..."
docker exec coffee_api python3 -c "
import asyncio
async def check():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as s:
        r = await s.execute(text('SELECT COUNT(*) FROM stores'))
        count = r.scalar()
        print(f'  ✓ stores table: {count} rows')
asyncio.run(check())
"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  TICKET-015: Create IVFFlat index"
echo "══════════════════════════════════════════════════════"

echo "→ Creating IVFFlat index on canonical_beans.embedding_vector..."
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
CREATE INDEX IF NOT EXISTS ix_canonical_beans_embedding
ON canonical_beans
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);
"

echo "→ Verifying index..."
docker exec coffee_postgres psql -U coffee -d coffee_platform -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'canonical_beans'
AND indexname = 'ix_canonical_beans_embedding';
"

echo ""
echo "══════════════════════════════════════════════════════"
echo "  TICKET-035: Run test suites"
echo "══════════════════════════════════════════════════════"

echo "→ Running API test suites..."
docker exec coffee_api python -m pytest \
    tests/test_services/test_extraction.py \
    tests/test_services/test_llm_extraction.py \
    tests/test_services/test_normalisation.py \
    -v --tb=short 2>&1 | tail -40

echo ""
echo "→ Running worker test suite..."
docker exec coffee_worker python -m pytest \
    /app/ingestion_svc/tests/test_worker.py \
    -v --tb=short 2>&1 | tail -30

echo ""
echo "══════════════════════════════════════════════════════"
echo "  TICKET-022: Start ingestion worker"
echo "══════════════════════════════════════════════════════"

echo "→ Starting worker..."
docker compose up -d worker

echo "→ Waiting 15 seconds for worker to connect..."
sleep 15

echo "→ Worker health check..."
curl -sf http://localhost:8001/health && echo " ✓ Worker healthy" || echo " ✗ Worker health check failed"

echo "→ Worker logs (last 30 lines)..."
docker compose logs worker --tail=30

echo ""
echo "→ To monitor the first crawl in real time:"
echo "   docker compose logs worker -f"
echo ""
echo "→ After 5 minutes, verify data is flowing:"
echo "   docker exec coffee_postgres psql -U coffee -d coffee_platform -c 'SELECT COUNT(*) FROM ingestion_runs;'"
echo "   docker exec coffee_postgres psql -U coffee -d coffee_platform -c 'SELECT COUNT(*) FROM bean_listings;'"
