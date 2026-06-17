# Complete Execution Plan: All 4 Steps

## Overview

This document provides the exact commands and procedures to execute all 4 steps of the data quality cleanup and prevention system.

---

## STEP 1: Deploy Code Changes ✅

### Status
**Complete** - Code committed and ready for deployment

### What Was Done
- Added coffee classification to HTML extraction pipeline
- Added coffee classification to schema.org extraction pipeline
- Created SQL cleanup script
- Created comprehensive documentation

### Code Location
```
Commit: 9b20607
Files:
  - services/api/app/services/html/pipeline.py
  - services/api/app/services/schema_org/pipeline.py
  - services/api/scripts/delete-non-coffee.sql
```

### Deploy to Production

**Option 1: Via Railway**
```bash
# Railway automatically deploys from main branch
# Your commit 9b20607 will be deployed on next push
git push origin main
# Monitor deployment: https://railway.app/project/[YOUR_PROJECT_ID]
```

**Option 2: Manual Deployment**
```bash
# If using Docker/Kubernetes
docker build -t coffee-api:latest services/api/
docker push coffee-api:latest
# Then update deployment to use new image
```

**Option 3: Verify Deployment Locally**
```bash
# Verify code changes don't cause syntax errors
cd services/api
python -m py_compile app/services/html/pipeline.py
python -m py_compile app/services/schema_org/pipeline.py
# Should complete with no errors
```

### Deployment Verification

After deployment, verify code is running:

```bash
# Check logs for coffee classification
ssh [railway-instance]
tail -f /var/log/coffee-api.log | grep "Skipping non-coffee"

# Or check Railway dashboard: Settings → Deployments → View Logs
```

---

## STEP 2: Run Cleanup Script 🧹

### Pre-Cleanup: Preview What Will Be Deleted

```bash
# Check count of non-coffee items
psql "$DATABASE_URL" << 'EOF'
SELECT 
  COUNT(*) as total_items_to_delete,
  COUNT(DISTINCT CASE WHEN canonical_name ~* 'subscription' THEN 1 END) as subscriptions,
  COUNT(DISTINCT CASE WHEN canonical_name ~* 'gift|bundle' THEN 1 END) as bundles,
  COUNT(DISTINCT CASE WHEN canonical_name ~* 'grinder|kettle|scale' THEN 1 END) as equipment,
  COUNT(DISTINCT CASE WHEN canonical_name ~* 'matcha|tea|chocolate' THEN 1 END) as non_coffee,
  COUNT(DISTINCT CASE WHEN canonical_name ~* 'pod|capsule' THEN 1 END) as pods
FROM canonical_beans
WHERE canonical_name ~* 'subscription|gift|bundle|grinder|kettle|scale|pod|capsule|matcha|tea|chocolate|course|sticker|poster|mug|cup';
EOF
```

### Execute Cleanup Script

**Important**: This modifies your database. Ensure you have a backup first.

```bash
# Verify you have backup
# Check Railway dashboard: Settings → Backups

# Execute cleanup
psql "$DATABASE_URL" -f services/api/scripts/delete-non-coffee.sql

# Expected output:
# BEGIN
# CREATE TABLE
# DELETE X
# DELETE Y
# ...
# COMMIT
# Cleanup complete | XXX | YYY | ZZZ
```

### Verify Cleanup Success

```bash
# 1. Check no subscriptions remain
psql "$DATABASE_URL" << 'EOF'
SELECT COUNT(*) FROM canonical_beans WHERE canonical_name ~* 'subscription';
EOF
# Expected: 0

# 2. Check no gifts remain
psql "$DATABASE_URL" << 'EOF'
SELECT COUNT(*) FROM canonical_beans WHERE canonical_name ~* 'gift|bundle';
EOF
# Expected: 0

# 3. Check no equipment remain
psql "$DATABASE_URL" << 'EOF'
SELECT COUNT(*) FROM canonical_beans WHERE canonical_name ~* 'grinder|kettle|scale|chemex|aeropress';
EOF
# Expected: 0

# 4. Final summary
psql "$DATABASE_URL" << 'EOF'
SELECT 
  'Canonical Beans' as table_name,
  COUNT(*) as remaining_rows
FROM canonical_beans
UNION ALL
SELECT 'Bean Listings', COUNT(*) FROM bean_listings
UNION ALL
SELECT 'Listing Variants', COUNT(*) FROM listing_variants
UNION ALL
SELECT 'Price History', COUNT(*) FROM price_history;
EOF
```

---

## STEP 3: Monitor Ingestion Logs 📊

### Real-Time Monitoring (First 7 Days)

```bash
# View live logs as ingestions happen
psql "$DATABASE_URL" << 'EOF'
-- Run this query every few hours to monitor rejections
SELECT 
  NOW() as check_time,
  COUNT(*) as rejected_today,
  COUNT(DISTINCT store_id) as stores_affected,
  ARRAY_AGG(DISTINCT warnings->0->>'detail') FILTER (WHERE warnings IS NOT NULL) as rejected_products
FROM ingestion_runs
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND warnings @> '[{"message":"Rejected non-coffee product"}]';
EOF
```

### Daily Monitoring Report

```bash
# Create a cronjob that runs daily
cat > /tmp/daily_qa_report.sh << 'SCRIPT'
#!/bin/bash

echo "=== Data Quality Report - $(date) ===" | mail -s "Coffee LLM Daily QA Report" your-email@example.com << 'SQL'
psql "$DATABASE_URL" << 'EOF'

-- Rejections in last 24 hours
SELECT 'Rejections Last 24h' as metric, COUNT(*)::text FROM ingestion_runs 
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND warnings @> '[{"message":"Rejected non-coffee product"}]'
UNION ALL

-- Total non-coffee products rejected
SELECT 'Total Rejected (Last 7d)', COUNT(*)::text FROM ingestion_runs 
WHERE created_at > NOW() - INTERVAL '7 days'
  AND warnings @> '[{"message":"Rejected non-coffee product"}]'
UNION ALL

-- Breakdown by category
SELECT 'By Category', 
  CONCAT(
    'Subscriptions: ', COUNT(*) FILTER (WHERE warnings->0->>'detail' ~* 'subscription'), ', ',
    'Gifts: ', COUNT(*) FILTER (WHERE warnings->0->>'detail' ~* 'gift'), ', ',
    'Equipment: ', COUNT(*) FILTER (WHERE warnings->0->>'detail' ~* 'grinder')
  )::text
FROM ingestion_runs
WHERE created_at > NOW() - INTERVAL '7 days'
  AND warnings @> '[{"message":"Rejected non-coffee product"}]';

EOF
SCRIPT

chmod +x /tmp/daily_qa_report.sh

# Add to crontab (run daily at 8am)
echo "0 8 * * * /tmp/daily_qa_report.sh" | crontab -
```

### Dashboard Integration

Add to your admin app's data quality dashboard:

```sql
-- Save these as views for dashboard
CREATE OR REPLACE VIEW v_daily_rejections AS
SELECT 
  DATE(created_at) as date,
  COUNT(*) as rejected_count,
  COUNT(DISTINCT store_id) as stores,
  ARRAY_AGG(DISTINCT SUBSTR(warnings->0->>'detail', 1, 50)) as examples
FROM ingestion_runs
WHERE warnings @> '[{"message":"Rejected non-coffee product"}]'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Query for dashboard
SELECT * FROM v_daily_rejections LIMIT 30;
```

---

## STEP 4: Verify Admin App & Data Quality ✓

### Test Checklist

```bash
# 1. Admin app still builds
cd /Users/travisganz/coffee_LLM/apps/admin-app
pnpm build
# Expected: Build succeeds

# 2. Check database integrity
psql "$DATABASE_URL" << 'EOF'
-- No orphaned records
SELECT COUNT(*) as orphaned_listings FROM bean_listings 
WHERE canonical_bean_id NOT IN (SELECT id FROM canonical_beans);
-- Expected: 0

SELECT COUNT(*) as orphaned_variants FROM listing_variants
WHERE bean_listing_id NOT IN (SELECT id FROM bean_listings);
-- Expected: 0
EOF

# 3. Verify data quality
psql "$DATABASE_URL" << 'EOF'
-- Only coffee products remain
SELECT COUNT(*) FROM canonical_beans
WHERE canonical_name ~* 'coffee|bean|origin|espresso|decaf|arabica|roast';
-- Expected: Most of your beans
EOF
```

### Manual Testing

**Test 1: Admin Beans Page**
```
1. Go to admin app: http://localhost:3000/admin/beans
2. Expected: Page loads, shows only coffee products
3. Verify: No subscriptions, gifts, or equipment visible
```

**Test 2: Search Functionality**
```
1. Search for "Ethiopia" → Should show Ethiopian coffees ✓
2. Search for "subscription" → Should show NO results ✓
3. Search for "grinder" → Should show NO results ✓
4. Search for "gift" → Should show NO results ✓
5. Search for "decaf" → Should show decaf coffees ✓
```

**Test 3: Filter Options**
```
1. Filter by Process (washed, natural, etc.) → Works ✓
2. Filter by Roast Level (light, medium, dark) → Works ✓
3. Pagination through results → Works ✓
4. Bulk enhance feature → Available ✓
```

**Test 4: Public Site**
```
1. Go to public site: http://localhost:3000
2. Search for coffee → See only products
3. No subscriptions/gifts in results
4. Search for "equipment" → NO results
```

### Performance Check

```javascript
// Run in browser console on admin app
fetch('/api/beans?page=1&page_size=50')
  .then(r => r.json())
  .then(data => {
    console.log(`✓ Loaded ${data.data.length} items`);
    console.log(`✓ Total items: ${data.total}`);
    console.log(`✓ API response time acceptable`);
  });
```

### Final Verification Query

```sql
-- Run this comprehensive check
SELECT 
  'Cleanup Status' as check_type,
  CASE 
    WHEN (SELECT COUNT(*) FROM canonical_beans WHERE canonical_name ~* 'subscription|gift|bundle|grinder|pod|matcha|tea') = 0
    THEN '✓ PASS: No non-coffee items'
    ELSE '✗ FAIL: Non-coffee items remain'
  END as status
UNION ALL
SELECT 'Data Integrity',
  CASE 
    WHEN (SELECT COUNT(*) FROM bean_listings WHERE canonical_bean_id NOT IN (SELECT id FROM canonical_beans)) = 0
    THEN '✓ PASS: No orphaned listings'
    ELSE '✗ FAIL: Orphaned listings found'
  END
UNION ALL
SELECT 'Rejection Logging',
  CASE
    WHEN (SELECT COUNT(*) FROM ingestion_runs WHERE warnings @> '[{"message":"Rejected non-coffee product"}]' AND created_at > NOW() - INTERVAL '7 days') > 0
    THEN '✓ PASS: Rejections being logged'
    ELSE '⚠ WARNING: No recent rejections logged'
  END;
```

---

## Execution Timeline

### Day 1
- [ ] Deploy code (Step 1)
- [ ] Run cleanup script (Step 2)
- [ ] Verify cleanup success

### Days 2-7
- [ ] Monitor ingestion logs daily (Step 3)
- [ ] Check for false positives
- [ ] Verify admin app stability (Step 4)

### Week 2+
- [ ] Ongoing monitoring
- [ ] Track data quality metrics
- [ ] Adjust classifier if needed

---

## Rollback Procedures

### If Code Deployment Has Issues

```bash
# Revert code to previous version
git revert 9b20607
git push origin main
# Railway will auto-deploy reverted code
```

### If Cleanup Causes Problems

```bash
# Restore from backup
# Via Railway: Settings → Backups → Restore
# Then re-run ingestion for affected stores
```

### If Admin App Breaks

```bash
# Clear cache
rm -rf apps/admin-app/.next
pnpm build
pnpm start

# Or revert code and redeploy
```

---

## Success Criteria Summary

### ✅ Deployment Success
- [ ] Code deploys without errors
- [ ] No syntax errors in logs
- [ ] API continues running

### ✅ Cleanup Success
- [ ] Script executes successfully
- [ ] Zero non-coffee items remain
- [ ] No orphaned records
- [ ] Data integrity verified

### ✅ Monitoring Success
- [ ] Non-coffee rejections logged
- [ ] Rejection rate tracked
- [ ] Trends visible

### ✅ Verification Success
- [ ] Admin app loads
- [ ] All searches work correctly
- [ ] All filters work
- [ ] No false positives
- [ ] Performance acceptable

---

## Support & Troubleshooting

### Common Issues

**Issue**: Cleanup script times out
```bash
# Solution: Run with higher timeout
psql -c "SET statement_timeout = 300000" -f services/api/scripts/delete-non-coffee.sql
```

**Issue**: No rejections in logs
```bash
# Solution: Check if pipelines are being used
# Verify stores are using html or schema_org strategies
psql "$DATABASE_URL" << 'EOF'
SELECT DISTINCT parser_strategy FROM source_pages LIMIT 10;
EOF
```

**Issue**: Admin app shows stale data
```bash
# Solution: Clear API cache
psql "$DATABASE_URL" << 'EOF'
TRUNCATE raw_extractions;
EOF
# Then re-run ingestion
```

---

**Status**: ✅ ALL 4 STEPS READY FOR EXECUTION

**Next Action**: Run Step 1 (Deploy) → Step 2 (Cleanup) → Step 3 (Monitor) → Step 4 (Verify)
