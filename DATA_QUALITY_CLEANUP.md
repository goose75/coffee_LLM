# Data Quality Cleanup: Removing Non-Coffee Items

This guide explains how to clean up the database and prevent non-coffee items from being sourced in the future.

## Problem

The database contains non-coffee items that should not be in the coffee product catalog:

- **Subscriptions**: Weekly/monthly/seasonal plans and boxes
- **Bundles & Gifts**: Gift sets, multi-packs, gift boxes
- **Pods & Capsules**: Nespresso, K-Cups, coffee pods
- **Equipment**: Grinders, kettles, scales, brewers, espresso machines
- **Courses & Classes**: Barista training, latte art courses
- **Merchandise**: T-shirts, posters, stickers, apparel
- **Non-coffee beverages**: Tea, matcha, chocolate, chai
- **Cups & Mugs**: Mugs, cups, tumblers, glassware, vessels

## Solution Overview

### 1. Prevention (Ongoing)

Non-coffee items are now filtered out at the extraction stage using the `is_coffee_product()` classifier in three pipelines:

- **Shopify Pipeline** (`services/api/app/services/shopify/pipeline.py`)
  - Already implemented ✓
  - Uses `coffee_classifier.is_coffee_product()`

- **HTML Pipeline** (`services/api/app/services/html/pipeline.py`)
  - Updated to add coffee classification ✓
  - Rejects non-coffee products before saving to database

- **Schema.org Pipeline** (`services/api/app/services/schema_org/pipeline.py`)
  - Updated to add coffee classification ✓
  - Rejects non-coffee products before saving to database

The classifier checks product titles against comprehensive patterns and rejects items that don't match coffee bean signals (origin countries, bean types, roast levels, etc.).

### 2. Cleanup (One-time)

To remove existing non-coffee items from the database:

#### Option A: Using SQL (Recommended for Railway)

Run the cleanup script directly against the database:

```bash
# Via psql with remote connection
psql "$DATABASE_URL" -f services/api/scripts/delete-non-coffee.sql

# Or copy the SQL commands and run in your database tool
```

This script:
1. Identifies all canonical beans matching non-coffee patterns
2. Deletes related canonical matches
3. Deletes related flavour tags
4. Deletes related price history
5. Deletes related listing variants
6. Deletes bean listings
7. Deletes canonical beans

#### Option B: Using Docker (If running locally)

```bash
# Run inside the API container
docker exec coffee_api python scripts/cleanup_non_coffee.py --dry-run  # Preview
docker exec coffee_api python scripts/cleanup_non_coffee.py --yes      # Execute
```

#### Option C: Using the cleanup script with confirmation

```bash
cd services/api
python scripts/cleanup_non_coffee_products.py --dry-run      # See what will be deleted
python scripts/cleanup_non_coffee_products.py --confirm      # Actually delete
```

## Patterns Used for Classification

### Exclude Patterns (Hard Rejects)

These patterns immediately reject a product, even if it contains coffee keywords:

- Capsules/pods: `capsule`, `pod`, `nespresso`
- Gift sets: `gift set`, `gift box`, `bundle`
- Subscriptions: `subscription`, `monthly plan`, `weekly box`
- Equipment brands: `fellow`, `bialetti`, `chemex`, `aeropress`, `hario`
- Equipment types: `grinder`, `kettle`, `scale`, `tamper`
- Courses: `course`, `class`, `workshop`, `barista`
- Merchandise: `t-shirt`, `poster`, `sticker`, `apron`
- Non-coffee: `matcha`, `tea`, `chocolate`, `chai`
- Vessels: `cup`, `mug`, `tumbler`, `glass`

### Include Patterns (Positive Signals)

A product must have at least one of these signals to be considered coffee:

- Origin countries: `Ethiopia`, `Kenya`, `Colombia`, `Brazil`, etc.
- Bean types: `whole bean`, `ground coffee`, `coffee beans`, `arabica`, `robusta`
- Roast levels: `light roast`, `medium roast`, `dark roast`
- Process types: `washed`, `natural`, `honey process`, `anaerobic`
- Product signals: `single origin`, `blend`, `espresso`, `decaf`

## How Filtering Works

### In Extraction Pipelines

When a product is extracted from a store (Shopify, HTML, schema.org):

1. **Extract** - Parse product title, description, tags
2. **Validate** - Check extraction confidence
3. **Classify** - Run through `is_coffee_product()` classifier
   - If non-coffee → **SKIP** (log warning)
   - If coffee → **CONTINUE** to database
4. **Save** - Store in bean_listings table

### Classifier Logic

```python
from app.services.shopify.coffee_classifier import is_coffee_product

product = {
    "title": "Ethiopian Yirgacheffe",
    "product_type": "Coffee",
    "tags": ["single origin", "light roast"]
}

is_coffee, reason = is_coffee_product(product)
# Returns: (True, "origin: 'ethiopia'")

# For a subscription:
product = {
    "title": "Monthly Coffee Subscription",
    "product_type": "",
    "tags": []
}

is_coffee, reason = is_coffee_product(product)
# Returns: (False, "excluded: '\\bsubscription\\b'")
```

## Verification

After cleanup, verify the database state:

```sql
-- Check total items
SELECT COUNT(*) FROM canonical_beans;

-- See what categories remain
SELECT 
  CASE
    WHEN canonical_name ~* 'subscription' THEN 'subscription'
    WHEN canonical_name ~* 'gift' THEN 'gift'
    WHEN canonical_name ~* 'grinder' THEN 'equipment'
    ELSE 'coffee'
  END as category,
  COUNT(*) as count
FROM canonical_beans
GROUP BY category;

-- Find any remaining non-coffee items (should be empty)
SELECT canonical_name
FROM canonical_beans
WHERE canonical_name ~* 'subscription|gift|bundle|grinder|pod|matcha|tea|chocolate'
LIMIT 20;
```

## Metrics

Track cleanup effectiveness:

- **Before**: Total items in canonical_beans table
- **After**: Total items in canonical_beans table
- **Removed**: Difference + count by category
- **Sourcing change**: Monitor ingestion logs for "Skipping non-coffee product" messages

## Ongoing Monitoring

Check ingestion run logs for non-coffee rejections:

```sql
-- Count non-coffee products rejected in recent runs
SELECT 
  COUNT(*) as rejected,
  EXTRACT(DATE FROM created_at) as date
FROM ingestion_runs
WHERE warnings LIKE '%non-coffee%'
  OR warnings LIKE '%Rejected%'
GROUP BY EXTRACT(DATE FROM created_at)
ORDER BY date DESC
LIMIT 10;
```

## Files Modified

- `services/api/app/services/html/pipeline.py` - Added coffee classification
- `services/api/app/services/schema_org/pipeline.py` - Added coffee classification
- `services/api/app/services/shopify/pipeline.py` - Already has classification
- `services/api/scripts/delete-non-coffee.sql` - New cleanup script

## Implementation Status

✅ **Prevention**: Coffee classification added to HTML and schema.org pipelines
✅ **Prevention**: Shopify pipeline already has classification
✅ **Cleanup**: SQL script ready for one-time cleanup
✅ **Monitoring**: Warnings logged for rejected non-coffee products

## Next Steps

1. Run the cleanup script once against production database
2. Monitor ingestion logs for non-coffee rejections
3. Adjust patterns if needed based on false positives/negatives
4. Archive and review products removed for data recovery if needed
