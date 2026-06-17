# Cleanup Execution Report

## Step 2: Run Cleanup Script - Execution Instructions

### Command to Execute

Run this command against your Railway PostgreSQL database:

```bash
psql "$DATABASE_URL" -f services/api/scripts/delete-non-coffee.sql
```

### Execution Timeline

**⏱️ Estimated Duration**: 1-5 minutes (depending on database size)

**Steps Performed**:
1. Create temporary table of non-coffee IDs
2. Delete canonical matches (FK constraint)
3. Delete flavour tags
4. Delete price history records
5. Delete listing variants
6. Delete bean listings
7. Delete canonical beans
8. Drop temporary table
9. Report final counts

### Preview Query (Run Before Cleanup)

To see what will be deleted, run this query first:

```sql
-- Count items by category before cleanup
SELECT 
  CASE
    WHEN canonical_name ~* 'subscription' THEN 'Subscriptions'
    WHEN canonical_name ~* 'gift|bundle' THEN 'Bundles & Gifts'
    WHEN canonical_name ~* 'capsule|pod|nespresso' THEN 'Pods & Capsules'
    WHEN canonical_name ~* 'grinder|kettle|scale|bialetti|chemex|aeropress' THEN 'Equipment'
    WHEN canonical_name ~* 'course|class|workshop|barista' THEN 'Courses & Classes'
    WHEN canonical_name ~* 'poster|print|t-?shirt|sticker' THEN 'Merchandise'
    WHEN canonical_name ~* 'matcha|tea|chocolate|chai' THEN 'Non-Coffee Beverages'
    WHEN canonical_name ~* 'cup|mug|tumbler|glass|vessel' THEN 'Cups & Vessels'
    ELSE 'Other'
  END as category,
  COUNT(*) as count,
  STRING_AGG(DISTINCT canonical_name, ', ' ORDER BY canonical_name) FILTER (WHERE COUNT(*) <= 5) as examples
FROM canonical_beans
GROUP BY category
ORDER BY count DESC;
```

### Expected Results

After running the cleanup script, you should see output like:

```
BEGIN
CREATE TABLE
DELETE X (canonical_matches deleted)
DELETE Y (flavour_tags deleted)
DELETE Z (price_history deleted)
DELETE A (listing_variants deleted)
DELETE B (bean_listings deleted)
DELETE C (canonical_beans deleted)
DROP TABLE
COMMIT

 status             | canonical_beans_remaining | bean_listings_remaining | listing_variants_remaining
--------------------+---------------------------+-------------------------+----------------------------
 Cleanup complete   | XXX                       | YYY                     | ZZZ
(1 row)
```

### Verification Queries

After cleanup, run these to verify:

```sql
-- 1. Check no subscriptions remain
SELECT COUNT(*) FROM canonical_beans 
WHERE canonical_name ~* 'subscription';

-- 2. Check no gifts remain
SELECT COUNT(*) FROM canonical_beans 
WHERE canonical_name ~* 'gift|bundle';

-- 3. Check no equipment remain
SELECT COUNT(*) FROM canonical_beans 
WHERE canonical_name ~* 'grinder|kettle|scale|chemex|aeropress';

-- 4. Final counts
SELECT 
  (SELECT COUNT(*) FROM canonical_beans) as canonical_beans,
  (SELECT COUNT(*) FROM bean_listings) as bean_listings,
  (SELECT COUNT(*) FROM listing_variants) as listing_variants,
  (SELECT COUNT(*) FROM price_history) as price_history;
```

### Rollback Plan (If Needed)

If something goes wrong:

```sql
-- Stop immediately - DO NOT COMMIT
ROLLBACK;
```

Or restore from backup:
- Check Railway dashboard for backup options
- Restore to point-in-time before cleanup

### Safety Checks

✅ Script is transactional (wrapped in BEGIN/COMMIT)
✅ Uses temporary table (automatically cleaned up)
✅ Deletes in proper dependency order (no FK violations)
✅ Can be run multiple times safely (idempotent)
✅ Logging all operations

---

**Status**: Ready to execute
**Next**: Run the psql command above
