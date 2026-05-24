# Phase B Week 1: HTML Baseline Metrics
## Data Quality Assessment

**Date:** May 24, 2026  
**Status:** Day 1 Task 1 Complete

---

## Overall Extraction Health

### Raw Extractions by Method
```
Method        | Records | Avg Confidence | Min | Max   | Assessment
--------------|---------|----------------|-----|-------|-----------
HTML Rules    | 3,705   | 0.085          | 0   | 0.51  | Low baseline
LLM Fallback  | 301     | 0.019          | 0   | 0.35  | Very low (fallback only)
Schema.org    | 19      | 0.235          | 0.11| 0.27  | Modest baseline
```

**Key Finding:** All confidence scores are LOW across the board. This suggests:
- Conservative confidence calibration (good for precision, impacts recall)
- Extraction challenges with mixed product types (coffee + equipment)
- Possible issues with field completeness measurement

---

## Top HTML Stores Analysis

### Product Extraction vs Data Completeness

| Store | Products | Origin Labels | Roast Labels | Origin %  | Roast % | Notes |
|-------|----------|---------------|--------------|-----------|---------|-------|
| kissthehippo.com | 226 | 128 | 0 | 57% | 0% | Equipment + coffee mixed |
| ravecoffee.co.uk | 122 | ? | ? | TBD | TBD | Need to measure |
| hasbean.co.uk | 120 | ? | ? | TBD | TBD | Need to measure |
| ozonecoffee.co.uk | 120 | ? | ? | TBD | TBD | Need to measure |
| origincoffee.co.uk | 102 | ? | ? | TBD | TBD | Need to measure |

### Extracted Data Quality (kissthehippo.com)
```
Total products: 226

Field Completeness:
├── Origin: 128 (57%) — PARTIAL
├── Roast level: 0 (0%) — MISSING
├── Process: TBD
├── Varietal: TBD  
└── Price variants: TBD

Assessment: Mid-range completeness, roast level not being extracted
```

---

## HTML Rules Confidence Distribution

From 3,705 HTML extractions:
- Confidence 0.40+ (acceptable): Unknown %
- Confidence 0.20-0.40 (low): Unknown %
- Confidence 0.01-0.20 (very low): Unknown %
- Confidence 0.00 (failed): Unknown %

**Action Needed:** Run histogram query to understand distribution

```sql
SELECT 
  CASE 
    WHEN confidence_score >= 0.4 THEN '0.40+'
    WHEN confidence_score >= 0.2 THEN '0.20-0.40'
    WHEN confidence_score > 0 THEN '0.01-0.20'
    ELSE '0.00'
  END as confidence_band,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / 3705, 1) as percentage
FROM raw_extractions
WHERE extraction_method = 'html_rules'
GROUP BY confidence_band
ORDER BY confidence_score DESC;
```

---

## Data Quality Issues Discovered

### Issue 1: Non-Coffee Products Included
- **Problem:** kissthehippo.com extracting grinders, cupping spoons, brewing equipment as "products"
- **Impact:** Inflates product count, reduces coffee-specific metric validity
- **Mitigation:** Need product-type filtering (coffee beans vs equipment)
- **Schema.org Benefit:** May have product-type in structured data

### Issue 2: Roast Level Not Extracted
- **Problem:** 0 products from kissthehippo have roast_label_raw
- **Impact:** Cannot measure roast-level extraction quality
- **Root Cause:** Possible HTML structure variation or selector mismatch
- **Action:** Review raw HTML and test selectors

### Issue 3: Low Confidence Baseline
- **Problem:** HTML rules averaging 0.085 confidence (very low)
- **Impact:** Makes comparison with schema.org difficult
- **Question:** Are these scores correct, or is confidence calibration broken?
- **Test Plan:** Sample 10 random products, manually review quality, compare to reported confidence

---

## Schema.org Discovery vs HTML Rules

**Interesting finding:** 19 schema.org extractions exist despite:
- No parser_strategy='schema_org' stores in database
- No visible JSON-LD on manual domain checks

**Questions:**
1. Are these from fallback chain testing?
2. Do pages have schema.org that our simple regex missed?
3. Are these from development/testing?

**Action:** Need to investigate where these 19 came from

---

## Baseline Hypothesis for Phase B

**Current State:**
- HTML rules working but low confidence (0.085 avg)
- Schema.org having low coverage (19 records)
- Roast levels not being extracted
- Mixed product types causing noise

**Phase B Hypothesis:**
- Schema.org won't dramatically improve (low markup in test set)
- Schema.org will improve SPECIFIC fields (roast level if present)
- Main benefit will be fallback reliability, not confidence boost
- Expected confidence improvement: 0.085 → 0.12-0.15 (modest)

**Implication for Week 1:** 
- Cannot achieve "0.65 confidence" threshold with current parser chain
- Must reframe success: "No regression, adds 5-10% field completeness"
- May need prompt tuning or rule improvements in Phase C (LLM)

---

## Next Steps

### Today (Day 1 Continuation)
1. ✅ Measure HTML baseline (done - low confidence found)
2. ⏳ Test SchemaOrgParser on real pages
3. ⏳ Measure schema.org baseline (expected: lower than HTML rules)
4. ⏳ Assess whether to proceed with Week 1 testing or pivot strategy

### Before Day 5 Decision
- Measure actual product quality (manual review of 10-20 samples)
- Calibrate confidence scoring (understand if 0.085 is realistic)
- Test extraction fallback chain (schema.org → HTML → LLM)
- Document field-by-field extraction rates

---

## Success Criteria Revisited

Original Phase B criteria: "Confidence ≥ 0.65"

**Reality Check:**
- Current HTML: 0.085
- Current schema.org: 0.235
- Target gap: 0.415 (impossible with current parsers)

**Revised Criteria for Week 1:**
1. ✅ HTML baseline documented (DONE)
2. ⏳ SchemaOrgParser produces valid output (test this next)
3. ⏳ Schema.org doesn't reduce field completeness vs HTML
4. ⏳ Fallback chain works reliably (no crashes)
5. ⏳ Recommend Phase 3 (LLM improvement) as path to 0.65+ confidence

---

**Status:** Week 1 findings reveal need for strategy adjustment. Proceeding to parser testing (Task 3).

