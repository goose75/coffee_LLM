# Step 4: Verification Checklist

## Admin App Functionality Verification

### 1. Admin Dashboard Load Test

**Test**: Admin app loads without errors

```bash
# Check if admin app builds successfully
cd /Users/travisganz/coffee_LLM/apps/admin-app
pnpm build

# Expected: Build completes with no errors
```

**Verification Query**:
```sql
-- Check admin app can query basic data
SELECT COUNT(*) as total_beans FROM canonical_beans;
SELECT COUNT(*) as total_listings FROM bean_listings;
SELECT COUNT(*) as total_variants FROM listing_variants;
```

### 2. Beans Page Verification

**Test**: Admin beans page works correctly

```javascript
// In browser console on admin app /beans page:
console.log("Checking beans page data...");

// Should show no non-coffee items in first 50 results
fetch('/api/beans?page=1&page_size=50')
  .then(r => r.json())
  .then(data => {
    const nonCoffee = data.data.filter(b => 
      b.canonical_name.match(/subscription|gift|bundle|grinder|pod/i)
    );
    console.log(`Non-coffee items found: ${nonCoffee.length}`);
    console.log('Details:', nonCoffee);
  });
```

### 3. Search Functionality Test

**Test**: Search works correctly with clean data

| Query | Expected Result | ✓ |
|-------|-----------------|---|
| "Ethiopia" | Real Ethiopian coffees | [ ] |
| "subscription" | NO results | [ ] |
| "espresso" | Espresso beans/blends | [ ] |
| "grinder" | NO results | [ ] |
| "gift" | NO results | [ ] |
| "Colombia" | Real Colombian coffees | [ ] |
| "tea" | NO results | [ ] |
| "single origin" | Single origin coffees | [ ] |

### 4. Product Card Display

**Test**: Admin product cards show only coffee

```javascript
// Check product cards on beans page
const productNames = document.querySelectorAll('[data-test="product-card-title"]');
let issues = [];

productNames.forEach(name => {
  const text = name.textContent;
  if (text.match(/subscription|gift|grinder|course|matcha|tea/i)) {
    issues.push(text);
  }
});

if (issues.length > 0) {
  console.error("Found non-coffee products:", issues);
} else {
  console.log("✓ All product cards are coffee products");
}
```

### 5. Roasters Page Test

**Test**: Roasters page still shows all valid roasters

```sql
-- Verify roasters haven't been affected by cleanup
SELECT COUNT(*) FROM stores WHERE roaster_flag = true AND active_flag = true;
-- Should match pre-cleanup count (roasters shouldn't be affected)
```

### 6. Ingestion Runs Dashboard

**Test**: Monitor rejections in admin dashboard

```javascript
// Check ingestion run warnings
fetch('/api/ingestion-runs?limit=20')
  .then(r => r.json())
  .then(data => {
    const runData = data.data || [];
    const recentRuns = runData.filter(r => {
      const warnings = r.warnings || [];
      return warnings.some(w => w.message.includes('Rejected non-coffee'));
    });
    console.log(`Recent runs with rejections: ${recentRuns.length}`);
    console.log('Details:', recentRuns);
  });
```

## Database Integrity Verification

### Pre-Cleanup Baseline (Run BEFORE cleanup)

```sql
-- Save baseline counts
CREATE TABLE IF NOT EXISTS cleanup_baseline AS
SELECT 
  'before_cleanup' as phase,
  NOW() as timestamp,
  (SELECT COUNT(*) FROM canonical_beans) as canonical_beans,
  (SELECT COUNT(*) FROM bean_listings) as bean_listings,
  (SELECT COUNT(*) FROM listing_variants) as listing_variants,
  (SELECT COUNT(*) FROM price_history) as price_history,
  (SELECT COUNT(*) FROM canonical_beans WHERE canonical_name ~* 'subscription|gift|bundle|grinder|pod') as non_coffee_items;
```

### Post-Cleanup Verification (Run AFTER cleanup)

```sql
-- Verify cleanup effectiveness
SELECT 
  'Beans removed' as metric,
  (SELECT canonical_beans FROM cleanup_baseline WHERE phase = 'before_cleanup') - 
  (SELECT COUNT(*) FROM canonical_beans) as count
UNION ALL
SELECT 'Listings removed', 
  (SELECT bean_listings FROM cleanup_baseline WHERE phase = 'before_cleanup') - 
  (SELECT COUNT(*) FROM bean_listings)
UNION ALL
SELECT 'Variants removed',
  (SELECT listing_variants FROM cleanup_baseline WHERE phase = 'before_cleanup') - 
  (SELECT COUNT(*) FROM listing_variants)
UNION ALL
SELECT 'Non-coffee items remaining',
  (SELECT COUNT(*) FROM canonical_beans WHERE canonical_name ~* 'subscription|gift|bundle|grinder|pod');
```

### Data Consistency Checks

```sql
-- Check for orphaned records (should all be 0)
SELECT 
  'Listings with missing beans' as check_name,
  COUNT(*) as orphaned_count
FROM bean_listings
WHERE canonical_bean_id IS NOT NULL
  AND canonical_bean_id NOT IN (SELECT id FROM canonical_beans)
UNION ALL
SELECT 'Variants with missing listings',
  COUNT(*)
FROM listing_variants
WHERE bean_listing_id NOT IN (SELECT id FROM bean_listings)
UNION ALL
SELECT 'Price history with missing variants',
  COUNT(*)
FROM price_history
WHERE listing_variant_id NOT IN (SELECT id FROM listing_variants);
```

### Category Distribution Check

```sql
-- Verify only real coffee remains
SELECT 
  'Coffee products (should be >90%)' as category,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM canonical_beans), 1) as percentage
FROM canonical_beans
WHERE canonical_name ~* 'coffee|bean|origin|roast|espresso|blend|decaf|arabica|robusta|ethiopia|kenya|colombia|brazil'
UNION ALL
SELECT 'Suspicious items (should be ~0)',
  COUNT(*),
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM canonical_beans), 1)
FROM canonical_beans
WHERE canonical_name ~* 'subscription|gift|bundle|grinder|kettle|course|matcha|tea|chocolate|cup|mug';
```

## Admin App Feature Checks

### Feature 1: Bulk Enhance

**Test**: Bulk enhance still works

```javascript
// Try bulk enhance feature
const enhanceBtn = document.querySelector('[data-test="bulk-enhance-btn"]');
if (enhanceBtn) {
  console.log("✓ Bulk enhance button visible");
  // Click would trigger enhancement
} else {
  console.error("✗ Bulk enhance button not found");
}
```

### Feature 2: Filtering & Search

**Test**: All filter options work

- [ ] Process filter works (washed, natural, honey, etc.)
- [ ] Roast level filter works (light, medium, dark)
- [ ] Search by name works
- [ ] Search by origin works
- [ ] Pagination works
- [ ] Completeness ring displays correctly

### Feature 3: Product Details

**Test**: Individual product pages load

```bash
# Pick a bean ID and test detail page
curl -s "http://localhost:3000/admin/beans/[BEAN_ID]" | grep -q "canonical_name" && echo "✓ Detail page works" || echo "✗ Detail page failed"
```

### Feature 4: Performance

**Test**: Pages load within acceptable time

```javascript
// Measure load time for beans page
const start = performance.now();
fetch('/api/beans?page=1&page_size=50')
  .then(() => {
    const end = performance.now();
    const duration = end - start;
    console.log(`API response time: ${duration.toFixed(2)}ms`);
    if (duration < 1000) console.log("✓ Performance OK");
    else console.warn("⚠ Slow response");
  });
```

## User-Facing App Verification

### Public Site Search

**Test**: Public site shows only coffee products

```bash
# Check public site loads
curl -s "https://yourdomain.com/api/coffees?page=1" | jq '.data[] | .canonical_name' | head -20
# Should show only coffee products, no subscriptions/gifts
```

### Public Site Filters

**Test**: All search filters work

- [ ] Origin country filter shows only coffee
- [ ] Process filter works
- [ ] Roast level filter works
- [ ] Price range filter works
- [ ] Search returns only coffee products

## Final Checklist

### Pre-Deployment
- [ ] Code changes reviewed
- [ ] Build completes without errors
- [ ] Cleanup script syntax verified

### Post-Deployment
- [ ] Admin app loads
- [ ] Beans page displays
- [ ] Search works
- [ ] Filters work
- [ ] Pagination works
- [ ] Bulk enhance available
- [ ] Performance acceptable

### Post-Cleanup
- [ ] Baseline metrics recorded
- [ ] Cleanup script executed successfully
- [ ] Non-coffee items removed (verified via query)
- [ ] No orphaned records
- [ ] Data consistency checks pass
- [ ] Coffee products remain intact

### Monitoring
- [ ] Ingestion logs show rejections
- [ ] Dashboard queries working
- [ ] Alert thresholds set
- [ ] False positive rate < 2%

### User Testing
- [ ] Public site search clean
- [ ] Admin search working
- [ ] No broken links
- [ ] No console errors

## Success Criteria

✅ **All Checks Pass If**:

1. Admin app loads without errors
2. Database contains only coffee products
3. No non-coffee items in search results
4. Ingestion logs show successful rejections
5. Performance metrics acceptable
6. All user interactions work smoothly
7. Zero orphaned records
8. Data integrity verified

---

**Verification Checklist**: Ready to execute
