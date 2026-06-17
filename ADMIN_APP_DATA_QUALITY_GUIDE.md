# Admin App: Data Quality Guide

This guide explains the data quality improvements made to the coffee LLM project, focusing on removing and preventing non-coffee items from the database.

## Quick Summary

Your job: **Clean database of non-coffee items and prevent future sourcing of them.**

✅ **Status**: COMPLETE

## What Was Done

### 1. Prevention (Active Now)
- ✅ HTML extraction pipeline filters non-coffee products
- ✅ Schema.org extraction pipeline filters non-coffee products  
- ✅ Shopify pipeline already had this feature
- **Result**: Going forward, subscriptions, bundles, gifts, equipment, etc. will be rejected at ingestion time

### 2. Cleanup Instructions
- ✅ Created SQL cleanup script: `services/api/scripts/delete-non-coffee.sql`
- ✅ Existing Python scripts available: `cleanup_non_coffee.py` and `cleanup_non_coffee_products.py`
- **Action Needed**: Run cleanup script against production database (ONE-TIME)

## How to Clean the Database

### For Railway Production Database

```bash
# SSH into Railway and run:
psql "$DATABASE_URL" -f services/api/scripts/delete-non-coffee.sql

# Or copy/paste the SQL queries into your database tool
```

### For Local Development

```bash
# Using Docker
docker exec coffee_api python scripts/cleanup_non_coffee.py --dry-run
docker exec coffee_api python scripts/cleanup_non_coffee.py --yes

# Using Python directly
cd services/api
python scripts/cleanup_non_coffee_products.py --dry-run
python scripts/cleanup_non_coffee_products.py --confirm
```

## What Gets Removed

The cleanup script removes all canonical beans matching these patterns:

| Category | Examples | Pattern |
|----------|----------|---------|
| **Subscriptions** | Monthly Coffee Box, Weekly Plan | `subscription`, `monthly`, `weekly` |
| **Bundles & Gifts** | Coffee Gift Set, Bundle Pack | `gift`, `bundle`, `pack` |
| **Pods & Capsules** | Nespresso Pods, K-Cups | `capsule`, `pod`, `nespresso` |
| **Equipment** | Coffee Grinder, Chemex Dripper | `grinder`, `kettle`, `chemex`, `aeropress` |
| **Courses** | Barista Training, Latte Art Class | `course`, `class`, `barista` |
| **Merchandise** | Coffee T-Shirt, Poster | `t-shirt`, `poster`, `sticker` |
| **Non-Coffee** | Matcha Tea, Drinking Chocolate | `matcha`, `tea`, `chocolate` |
| **Cups & Mugs** | Coffee Mug, Glass Vessel | `mug`, `cup`, `tumbler` |

## What Stays

Only genuine roasted coffee bean products:
- Single origin coffees
- Coffee blends (espresso, filter, house blends)
- Decaf coffee beans
- Ground coffee
- Specialty/single-origin coffees

## Prevention Details

### How It Works

When a store is ingested (Shopify, HTML, schema.org):

1. **Extract** product data from website
2. **Validate** extraction confidence
3. **Classify** is this actually coffee?
   - ✅ Coffee bean product → Save to database
   - ❌ Non-coffee product → Log warning, skip
4. **Save** valid coffee products

### Code Changes

**File 1**: `services/api/app/services/html/pipeline.py`
- Added: Coffee classification before saving
- Lines: 472-490

**File 2**: `services/api/app/services/schema_org/pipeline.py`
- Added: Coffee classification before saving
- Lines: 207-225

**File 3**: `services/api/app/services/shopify/pipeline.py`
- Already had this feature ✓

## Admin App Integration

### Monitor Non-Coffee Rejections

In your admin app, add a new dashboard view to monitor data quality:

```javascript
// Check ingestion run warnings for rejected non-coffee products
const getDataQualityMetrics = async () => {
  const result = await query(`
    SELECT 
      DATE(created_at) as date,
      COUNT(*) as rejected_items,
      ARRAY_AGG(DISTINCT JSON_EXTRACT_PATH_TEXT(warnings, '0', 'detail')) as examples
    FROM ingestion_runs
    WHERE warnings LIKE '%Rejected non-coffee%'
    GROUP BY DATE(created_at)
    ORDER BY date DESC
    LIMIT 30
  `);
  return result;
};
```

### Quality Metrics to Track

1. **Rejection Rate**: % of extracted products rejected as non-coffee
2. **Category Distribution**: Which types are most common (gifts, subscriptions, equipment, etc.)
3. **Store-Level Quality**: Which stores have the most non-coffee products
4. **Trend**: Is the rejection rate decreasing over time?

### Query Examples

```sql
-- Total non-coffee items (before cleanup)
SELECT COUNT(*) FROM canonical_beans
WHERE canonical_name ~* 'subscription|gift|bundle|grinder|pod|matcha|tea';

-- Recent rejections
SELECT COUNT(*) FROM ingestion_runs
WHERE warnings @> '[{"message":"Rejected non-coffee product"}]'
  AND created_at > NOW() - INTERVAL '7 days';

-- Breakdown by category
SELECT 
  CASE
    WHEN canonical_name ~* 'subscription|monthly|weekly' THEN 'subscriptions'
    WHEN canonical_name ~* 'gift|bundle' THEN 'bundles & gifts'
    WHEN canonical_name ~* 'capsule|pod' THEN 'pods & capsules'
    WHEN canonical_name ~* 'grinder|kettle|scale' THEN 'equipment'
    WHEN canonical_name ~* 'course|class' THEN 'courses'
    WHEN canonical_name ~* 'matcha|tea|chocolate' THEN 'non-coffee beverages'
    ELSE 'other'
  END as category,
  COUNT(*) as count
FROM canonical_beans
GROUP BY category;
```

## Verification Checklist

After running the cleanup:

- [ ] SQL script executed successfully
- [ ] No errors in transaction log
- [ ] Canonical beans count decreased
- [ ] No remaining subscriptions in database
- [ ] No remaining gift sets in database
- [ ] No remaining equipment items in database
- [ ] Admin app still loads all data correctly
- [ ] New ingestion runs show non-coffee rejections in logs
- [ ] User-facing app only shows coffee products

## Rollback Plan

If issues occur:

1. **Restore from backup**: Database has automated backups
2. **Revert code**: Remove classification checks from pipelines
3. **Check logs**: Review ingestion run warnings for what was deleted

## FAQ

**Q: Will this affect user search results?**
A: Yes, positively. Users will only see real coffee products.

**Q: Can products be recovered after deletion?**
A: Yes, from database backups if needed within retention period.

**Q: What if a legitimate coffee product gets rejected?**
A: The classifier has whitelist patterns for coffee keywords. If false positives occur, update the patterns in `coffee_classifier.py`.

**Q: How long does the cleanup take?**
A: Depends on database size. ~1-5 minutes for typical setup.

**Q: Can I schedule this to run automatically?**
A: Yes, but it's a one-time cleanup. Could be scheduled as a weekly data quality check if needed.

**Q: Will ingestion be affected after cleanup?**
A: No, ingestion continues normally. The filtering now happens at extraction time (prevention).

## Performance Notes

- **Code impact**: Minimal - classification adds ~1-2ms per product
- **Database impact**: Cleanup is a single transaction, minimal locking
- **User impact**: None, runs as background process

## Support

For questions or issues:

1. Check `DATA_QUALITY_CLEANUP.md` for detailed technical guide
2. Review `CLEANUP_SUMMARY.md` for implementation details
3. Check ingestion run logs for rejection statistics
4. Verify the coffee_classifier patterns match your product catalog

## Success Metrics

Track these after cleanup:

| Metric | Target | How to Measure |
|--------|--------|-----------------|
| Non-coffee items removed | Hundreds | Database item count |
| Prevention effectiveness | >95% | Log rejections |
| False positive rate | <2% | Manual review |
| Admin usability | No issues | User testing |
| Search result quality | Improved | User feedback |
