# Step 3: Monitoring Ingestion Logs

## Real-Time Monitoring Queries

### Monitor Non-Coffee Rejections (Last 24 Hours)

```sql
-- Count non-coffee products rejected in last 24 hours
SELECT 
  COUNT(*) as total_rejected,
  COUNT(DISTINCT store_id) as stores_affected,
  EXTRACT(HOUR FROM created_at) as hour,
  COUNT(*) as count_in_hour
FROM ingestion_runs
WHERE created_at > NOW() - INTERVAL '24 hours'
  AND warnings @> '[{"message":"Rejected non-coffee product"}]'
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY hour DESC;
```

### Rejected Products by Category

```sql
-- Break down rejections by product type
SELECT 
  CASE
    WHEN warnings->0->>'detail' ~* 'subscription' THEN 'Subscriptions'
    WHEN warnings->0->>'detail' ~* 'gift|bundle' THEN 'Bundles & Gifts'
    WHEN warnings->0->>'detail' ~* 'capsule|pod' THEN 'Pods & Capsules'
    WHEN warnings->0->>'detail' ~* 'grinder|kettle|scale' THEN 'Equipment'
    WHEN warnings->0->>'detail' ~* 'course|class' THEN 'Courses'
    WHEN warnings->0->>'detail' ~* 'matcha|tea|chocolate' THEN 'Non-Coffee'
    ELSE 'Other'
  END as category,
  COUNT(*) as rejected_count,
  ARRAY_AGG(DISTINCT warnings->0->>'detail') as examples
FROM ingestion_runs
WHERE created_at > NOW() - INTERVAL '7 days'
  AND warnings @> '[{"message":"Rejected non-coffee product"}]'
GROUP BY category
ORDER BY rejected_count DESC;
```

### Rejection Rate by Store

```sql
-- Show rejection rates per store
SELECT 
  s.domain,
  COUNT(ir.id) as total_runs,
  COUNT(DISTINCT ir.id) FILTER (WHERE ir.warnings @> '[{"message":"Rejected non-coffee product"}]') as runs_with_rejections,
  ROUND(100.0 * COUNT(DISTINCT ir.id) FILTER (WHERE ir.warnings @> '[{"message":"Rejected non-coffee product"}]') / COUNT(ir.id), 1) as rejection_rate_pct
FROM stores s
LEFT JOIN ingestion_runs ir ON s.id = ir.store_id
WHERE ir.created_at > NOW() - INTERVAL '7 days'
GROUP BY s.domain
ORDER BY rejection_rate_pct DESC;
```

### Examples of Rejected Products

```sql
-- Show actual product names that were rejected
SELECT DISTINCT
  (ir.warnings->0->>'detail') as rejected_product_name,
  ir.warnings->0->>'message' as rejection_reason,
  COUNT(*) as times_seen,
  MAX(ir.created_at) as last_seen
FROM ingestion_runs ir
WHERE ir.warnings @> '[{"message":"Rejected non-coffee product"}]'
  AND ir.created_at > NOW() - INTERVAL '7 days'
GROUP BY rejected_product_name, rejection_reason
ORDER BY times_seen DESC
LIMIT 50;
```

## Dashboard Setup (for Admin App)

### Key Metrics to Track

1. **Daily Rejection Count**
   - Should be increasing as more stores use new pipelines
   - Indicates classifier is working

2. **Rejection Rate Trend**
   - Plot over time
   - Should stabilize after initial spike

3. **Category Distribution**
   - Which types are most rejected
   - Help validate classifier effectiveness

4. **False Positive Rate**
   - Monitor for coffee products incorrectly rejected
   - Should be < 2%

### SQL Views for Admin Dashboard

Create these views for easy dashboard queries:

```sql
-- Create view for rejection statistics
CREATE OR REPLACE VIEW v_non_coffee_rejections AS
SELECT 
  DATE(created_at) as rejection_date,
  COUNT(*) as daily_count,
  COUNT(DISTINCT store_id) as stores_affected,
  ARRAY_AGG(DISTINCT SUBSTR(warnings->0->>'detail', 1, 50)) as examples
FROM ingestion_runs
WHERE warnings @> '[{"message":"Rejected non-coffee product"}]'
GROUP BY DATE(created_at)
ORDER BY rejection_date DESC;

-- Create view for category breakdown
CREATE OR REPLACE VIEW v_rejected_by_category AS
SELECT 
  CASE
    WHEN warnings->0->>'detail' ~* 'subscription' THEN 'Subscriptions'
    WHEN warnings->0->>'detail' ~* 'gift|bundle' THEN 'Bundles & Gifts'
    WHEN warnings->0->>'detail' ~* 'capsule|pod' THEN 'Pods & Capsules'
    WHEN warnings->0->>'detail' ~* 'grinder|kettle|scale' THEN 'Equipment'
    WHEN warnings->0->>'detail' ~* 'course|class' THEN 'Courses'
    WHEN warnings->0->>'detail' ~* 'matcha|tea|chocolate' THEN 'Non-Coffee Beverages'
    WHEN warnings->0->>'detail' ~* 'cup|mug|tumbler' THEN 'Cups & Vessels'
    ELSE 'Other'
  END as category,
  COUNT(*) as rejected_count
FROM ingestion_runs
WHERE warnings @> '[{"message":"Rejected non-coffee product"}]'
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY category
ORDER BY rejected_count DESC;

-- Check the views
SELECT * FROM v_non_coffee_rejections LIMIT 30;
SELECT * FROM v_rejected_by_category;
```

## Alert Thresholds

### Critical Alerts (Action Required)

**High False Positive Rate**: > 5% of rejections are coffee products
```sql
SELECT COUNT(*) FROM canonical_beans
WHERE canonical_name ~* 'coffee|bean|origin'
  AND created_at > NOW() - INTERVAL '1 day'
LIMIT 20;
```

**No Rejections for 24 Hours**: May indicate pipeline is broken
```sql
SELECT COUNT(*) FROM ingestion_runs
WHERE warnings @> '[{"message":"Rejected non-coffee product"}]'
  AND created_at > NOW() - INTERVAL '24 hours';
```

### Warnings (Monitor)

**Rejection Rate > 50%**: More than half of products being rejected
```sql
SELECT 
  s.domain,
  COUNT(*) FILTER (WHERE ir.warnings @> '[{"message":"Rejected non-coffee product"}]')::FLOAT / COUNT(*) as rejection_rate
FROM stores s
LEFT JOIN ingestion_runs ir ON s.id = ir.store_id
WHERE ir.created_at > NOW() - INTERVAL '7 days'
GROUP BY s.domain
HAVING COUNT(*) > 0
  AND COUNT(*) FILTER (WHERE ir.warnings @> '[{"message":"Rejected non-coffee product"}]')::FLOAT / COUNT(*) > 0.5;
```

## Logging Best Practices

The system automatically logs:
- ✅ Product name being rejected
- ✅ URL where found
- ✅ Rejection reason (which pattern matched)
- ✅ Timestamp
- ✅ Store domain

All visible in `ingestion_runs.warnings` JSON column.

## Alerting Setup (Optional)

### Email Alert on High Rejection Rate

```sql
-- Check for alert conditions and send notification
SELECT 
  CASE 
    WHEN (SELECT COUNT(*) FROM ingestion_runs WHERE warnings @> '[{"message":"Rejected non-coffee product"}]' AND created_at > NOW() - INTERVAL '24 hours') = 0
    THEN 'WARNING: No non-coffee rejections in 24 hours - pipeline may be broken'
    
    WHEN (SELECT COUNT(*) FILTER (WHERE canonical_name ~* 'coffee|bean') FROM canonical_beans WHERE created_at > NOW() - INTERVAL '1 day') > 100
    THEN 'ALERT: High rate of coffee products - check for false positives'
    
    ELSE 'OK - Monitoring active'
  END as alert_status;
```

---

**Monitoring Setup**: ✅ COMPLETE

See queries above to integrate into admin dashboard.
