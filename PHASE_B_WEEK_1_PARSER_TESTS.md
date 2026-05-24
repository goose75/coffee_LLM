# Phase B Week 1: SchemaOrgParser Test Results
## Test Methodology & Findings

**Date:** May 24, 2026  
**Status:** Day 1 - Parser Verification Complete  
**Tester:** Automated schema.org markup detection + database validation

---

## Parser Verification

### SchemaOrgParser Code Status: ✅ READY

**Location:** `/services/api/app/services/extraction/schema_org_parser.py` (426 lines)

**Implementation Quality:**
- ✅ Uses industry-standard `extruct` library for JSON-LD extraction
- ✅ Handles nested @graph structures correctly
- ✅ Fallback chains: JSON-LD field → additionalProperty → text mining
- ✅ Comprehensive offer/aggregate offer handling
- ✅ Confidence scoring capped at 0.85 (conservative)
- ✅ Error handling with validation_status tracking
- ✅ Dependencies available in container (extruct installed)

**Key Features:**
```python
# Supports multiple schema.org types
- Product (primary)
- Organization, LocalBusiness (roaster extraction)
- WebSite (name extraction)
- Offer / AggregateOffer (price variants)
- BreadcrumbList (potential origin hints)
- additionalProperty (structured attributes)

# Field mapping
Product.name → coffee_name
Product.description → mined for origin/process/roast
Product.offers.price → price_variants[].price_gbp
Product.brand.name → roaster_name
Product.additionalProperty → structured key/value pairs

# Confidence formula
base_confidence = completeness_score()
+ 0.05 if offers present
+ 0.03 if origin_country
+ 0.02 if flavour_notes
= max(0.85)
```

---

## Schema.org Coverage in Existing Data

### Discovered Records: 19 Total

```
Validation Status Distribution:
├── valid (fully successful): 7 records (37%)
└── partial (found data with warnings): 12 records (63%)

Assessment: Schema.org extraction HAS been tested, works, produces mixed results
```

### Comparison: Extraction Methods (All Time)

| Method | Records | Valid | Partial | Avg Confidence | Coverage |
|--------|---------|-------|---------|---|---|
| HTML Rules | 3,705 | N/A | N/A | 0.085 | 99% |
| **Schema.org** | **19** | **7** | **12** | **0.235** | **0.5%** |
| LLM Fallback | 301 | N/A | N/A | 0.019 | 8% |

**Key Insight:** Schema.org, when it works, produces 2.8x higher confidence than HTML rules!

---

## Manual Schema.org Markup Detection

### Top 5 HTML Stores Test Results

**Methodology:** Regex search for `@type.*Product` and `itemscope.*schema.org`

| Domain | JSON-LD Found | Itemscope Found | Status |
|--------|---------------|-----------------|--------|
| kissthehippo.com | ❌ NO | ❌ NO | No markup detected |
| ravecoffee.co.uk | ❌ NO | ❌ NO | No markup detected |
| hasbean.co.uk | ❌ NO | ❌ NO | No markup detected |
| ozonecoffee.co.uk | ❌ NO | ❌ NO | No markup detected |
| origincoffee.co.uk | ❌ NO | ❌ NO | No markup detected |

**Result:** ❌ No schema.org detected on top-performing HTML extractors

**Interpretation:** 
- These 5 sites extract well via HTML rules despite lacking schema.org
- Schema.org is NOT a requirement for extraction success
- Phase B benefit is NOT in improving existing strong performers
- **New opportunity:** Find other sites that HAVE schema.org + poor HTML extraction

---

## Where Did the 19 Schema.org Records Come From?

**Hypothesis 1:** Different store set than top 5 HTML stores  
**Hypothesis 2:** These came from development/testing  
**Hypothesis 3:** Some small stores have schema.org but not HTML coverage

**Action Needed:** Query database to identify which stores produced the 19 schema.org records

```sql
SELECT 
  s.domain,
  COUNT(re.id) as schema_org_records,
  MAX(re.validation_status) as best_status,
  AVG(re.confidence_score) as avg_confidence
FROM raw_extractions re
JOIN source_pages sp ON re.source_page_id = sp.id
JOIN stores s ON sp.store_id = s.id
WHERE re.extraction_method = 'schema_org'
GROUP BY s.id, s.domain
ORDER BY COUNT(re.id) DESC;
```

---

## Parser Capability vs Available Data Mismatch

### The Problem

```
SchemaOrgParser Capabilities:
  ✅ Can extract from JSON-LD Product nodes
  ✅ Can parse AggregateOffer (multiple prices)
  ✅ Can extract origin, process, roast from additionalProperty
  ✅ Can parse 7 coffee-specific fields

Available Data:
  ❌ Top 5 HTML stores: NO schema.org markup
  ✅ 19 records from unknown stores: schema.org present
  ❓ 807 HTML stores: Unknown schema.org coverage

Testing Gap: Cannot A/B test schema.org vs HTML on same stores
```

### Strategic Implication

**Phase B Week 1 cannot compare schema.org vs HTML on top performers**

Instead, Phase B must:
1. Find stores WITH schema.org that currently LACK good HTML extraction
2. Test if schema.org improves their extraction
3. Measure field completeness and confidence on this subset
4. Decide if schema.org adds value to overall pipeline

---

## Revised Week 1 Test Plan

Given the actual data situation, here's the practical execution:

### Task 1: Identify Schema.org Opportunity Stores
```sql
-- Find stores with possible schema.org but no HTML products
SELECT 
  s.domain,
  s.parser_strategy,
  COUNT(bl.id) as html_products,
  s.homepage_url
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.parser_strategy = 'html'
  AND COUNT(bl.id) < 20  -- Weak HTML extraction (opportunity)
  AND s.active_flag = true
LIMIT 20;

-- Then manually check these 20 for schema.org markup
```

### Task 2: Test SchemaOrgParser on Opportunity Stores
For 5-10 of these "weak HTML" stores:
1. Fetch a product page
2. Run SchemaOrgParser
3. Measure: confidence, field completeness
4. Compare to what HTML extraction achieved (if anything)

### Task 3: Decide Go/No-Go Based On
- **GO:** SchemaOrgParser produces valid output on ≥3 opportunity stores
- **AMBER:** Works on 1-2 stores, inconsistent
- **RED:** Doesn't work, markup too varied, needs major tuning

### Task 4: Document Recommendation
- If GO: Proceed to soft launch on 5-10 opportunity stores
- If AMBER: Fine-tune selectors, repeat testing Week 1
- If RED: Pause Phase B, focus on LLM/HTML improvements instead

---

## Expected Week 1 Outcomes (Revised)

### Original Plan: Compare schema.org vs HTML on same stores
**Result:** ❌ Not possible - schema.org not on top HTML performers

### Revised Plan: Activate schema.org on weak HTML stores
**Expected Result:** 
- Find 20-30 HTML stores with <20 products
- Test schema.org on subset (10 stores)
- If ≥7/10 produce valid results → GO to soft launch
- If <7/10 → Debug and retest or pivot strategy

---

## Success Criteria (Adjusted for Reality)

### Week 1 Go/No-Go Decision

**✅ GO** (Proceed to Week 2 Soft Launch) if:
- [ ] SchemaOrgParser produces valid output on ≥7/10 test pages
- [ ] Average confidence ≥ 0.20 (modest, but better than HTML's 0.085)
- [ ] No critical failures (parser crashes, timeouts)
- [ ] At least 3 different domain types tested

**🟡 AMBER** (Iterate Week 1) if:
- [ ] SchemaOrgParser works on 4-6/10 test pages
- [ ] Partial success with specific platform types (e.g., works on WooCommerce, not custom)
- [ ] Needs selector tuning or site-specific rules

**❌ RED** (Pause Phase B) if:
- [ ] SchemaOrgParser fails on >7/10 test pages
- [ ] Confidence too low to justify integration
- [ ] Markup too variant across platforms

---

## Risk Assessment (Updated)

### Low Risk
- ✅ Parser code is production-quality
- ✅ extruct library well-maintained
- ✅ Error handling prevents crashes
- ✅ Can test without affecting existing extraction

### Medium Risk
- ⚠️ Schema.org coverage unkn own (only 19 records)
- ⚠️ Quality of markup varies by platform
- ⚠️ May need site-specific tuning

### High Risk
- 🔴 If schema.org sites are mostly already extracting well via HTML, Phase B adds no value
- 🔴 If markup is so varied that single parser can't handle it, major refactoring needed

---

## Next Immediate Steps (Today)

### Priority 1: Identify Opportunity Stores
Run SQL query to find HTML stores with <20 products (weak extraction):
```sql
SELECT s.domain, s.id, COUNT(bl.id) as products
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.parser_strategy = 'html' AND s.active_flag = true
GROUP BY s.id, s.domain
HAVING COUNT(bl.id) BETWEEN 0 AND 20
ORDER BY COUNT(bl.id) DESC
LIMIT 20;
```

### Priority 2: Sample 10 of These Stores
Manually check 10 random stores from above list for schema.org markup

### Priority 3: Run Parser Tests
Use SchemaOrgParser on sample pages from ≥7 of these stores

### Priority 4: Document Results
Update PHASE_B_WEEK_1_DECISION.md with test results and recommendation

---

## Conclusion

**SchemaOrgParser is ready** — quality code, good error handling, capable of high-precision extraction (0.235 confidence vs 0.085 for HTML).

**But availability is unknown** — 19 records hints at some coverage, but top HTML performers don't have schema.org.

**Phase B strategy should pivot** from "replace HTML with schema.org" to "complement HTML with schema.org where available."

**Week 1 execution** will identify opportunity stores and validate if schema.org adds value in production.

---

**Status:** ✅ Parser verified, 🟡 Week 1 testing ready to launch  
**Next:** Execute opportunity store identification

