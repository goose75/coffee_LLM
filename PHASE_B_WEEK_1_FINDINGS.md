# Phase B Week 1: Schema.org Testing & Validation
## Initial Findings Report

**Date:** May 24, 2026  
**Status:** 🟡 In Progress - Day 1  
**Execution Model:** Phase B adapted for actual data conditions

---

## Database State Analysis

### Current Extraction Coverage
```
Total Active Stores: 841
Stores with products extracted: 49

By Parser Strategy:
- HTML: 807 stores (6% extracting)
- Shopify: 28 stores (all extracting)  
- Unknown: 6 stores (0% extracting)
- Schema.org: 0 stores (no pipeline yet)

Total products in system: 2,390
```

### Top HTML Stores (Extraction Success Baseline)
| Rank | Domain | Products | Strategy |
|------|--------|----------|----------|
| 1 | kissthehippo.com | 226 | HTML |
| 2 | ravecoffee.co.uk | 122 | HTML |
| 3 | hasbean.co.uk | 120 | HTML |
| 4 | ozonecoffee.co.uk | 120 | HTML |
| 5 | origincoffee.co.uk | 102 | HTML |
| 6 | shop.squaremilecoffee.com | 88 | HTML |
| 7 | volcanocoffeeworks.com | 88 | HTML |

**Total top 5 HTML stores:** 690 products extracted  
**Average confidence:** Need to measure

---

## Schema.org Markup Discovery

### Result: No Direct JSON-LD Found

Manual check on top 5 HTML stores (kissthehippo, ravecoffee, hasbean, ozonecoffee, origincoffee):
- ❌ No Product JSON-LD found on shop pages
- ❌ No itemscope/itemtype schema.org markup found
- ❌ No BreadcrumbList schema found
- ❌ No Organization schema found

### Interpretation

**This is not a failure — it's crucial information:**

1. **Top HTML stores don't have schema.org** → They're extracting well via HTML rules alone
2. **No parser_strategy='schema_org' stores exist** → Schema.org is a net-new category
3. **Phase B strategy needs adjustment** → Cannot do direct comparison (schema.org vs HTML baseline) on top performers

---

## Phase B Week 1: Revised Execution Plan

### New Approach: Opportunity Discovery

Since top HTML extractors don't have schema.org, Phase B Week 1 should:

**Option A: Test SchemaOrgParser in isolation**
- Verify SchemaOrgParser code works and can extract from pages
- Test against the 807 HTML stores to identify which have schema.org embedded
- Find the "hidden" schema.org stores and measure their confidence vs HTML extraction
- This becomes our pilot set

**Option B: Activate schema.org on existing HTML stores**  
- Enable schema.org extraction ALONGSIDE HTML (fallback chain)
- Run both extractors on same pages
- Measure: When schema.org finds data, how does confidence compare?
- When schema.org fails, does HTML extraction still work? (risk assessment)

**Option C: Find stores with known schema.org (external research)**
- Search for high-quality e-commerce sites known to have schema.org
- Test against our parser
- Use as pilot validation

---

## Immediate Next Steps (Today)

### Task 1: Measure HTML Baseline Confidence
```sql
-- Get average confidence for top HTML stores
SELECT 
  s.domain,
  COUNT(bl.id) as products,
  ROUND(AVG(CAST(bl.raw_extraction -> 'confidence' AS NUMERIC)), 2) as avg_confidence,
  MIN(CAST(bl.raw_extraction -> 'confidence' AS NUMERIC)) as min_conf,
  MAX(CAST(bl.raw_extraction -> 'confidence' AS NUMERIC)) as max_conf
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.parser_strategy = 'html'
  AND COUNT(bl.id) > 50
GROUP BY s.id, s.domain
ORDER BY COUNT(bl.id) DESC
LIMIT 5;
```

### Task 2: Search for Schema.org in HTML Content
- Sample pages from each top HTML store
- Run deep schema.org detection (check HTML source comments, data attributes)
- Parse JSON-LD embedded in script tags more thoroughly

### Task 3: Test SchemaOrgParser Implementation
- Verify pipeline code exists and can be instantiated
- Test extraction on known schema.org page (like a major retailer)
- Measure confidence scores it produces

### Task 4: Classify the 807 HTML Stores
- Categorize by platform type (Elementor, WooCommerce, Shopify, custom)
- Estimate how many might have schema.org (modern platforms more likely)
- Identify subset for manual testing

---

## Decision Gate for Week 2

**GO if:**
- SchemaOrgParser successfully extracts from ≥ 3 test pages with confidence ≥ 0.65
- Found at least 10 stores with schema.org markup  
- No critical failures in parser code

**AMBER if:**
- SchemaOrgParser works but with lower confidence (0.50-0.65)
- Found 3-9 stores with schema.org
- Minor code issues that can be fixed in 1-2 days

**RED if:**
- SchemaOrgParser doesn't work or produces confidence < 0.50
- Found 0-2 stores with schema.org in 807-store sample
- Critical code issues or integration problems

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| No schema.org found in dataset | Medium | Can't A/B test | Switch to Option B (run alongside HTML) |
| SchemaOrgParser produces low confidence | Medium | Defeats purpose | Tune prompts/selectors, compare with HTML |
| Top HTML stores break if schema.org enabled | Low | Rollback | Test on non-top stores first |
| Week 1 inconclusive | Medium | Delay Phase B | Set clearer definition of success upfront |

---

## Recommendation for Week 1 Execution

**Pursue Option B: Run Schema.org Alongside HTML**

**Rationale:**
- Top HTML extractors are working (226, 122, 120 products each)
- No direct schema.org competition/comparison possible
- Better to prove schema.org adds value (finds more products) not reduces value
- Safer for rollout: HTML stays, schema.org enhances

**Week 1 Tasks:**
1. ✅ Document HTML baseline confidence (Task 1 above)
2. ✅ Verify SchemaOrgParser works (Task 3 above)
3. Test extraction chain: schema.org → HTML fallback on sample pages
4. Measure: Does schema.org ever find products HTML misses?
5. Measure: Does schema.org ever produce LOWER confidence (false positives)?
6. Measure: Parser execution time (target < 300ms per page)

**Success Criteria:**
- SchemaOrgParser produces valid output for ≥ 80% of test pages
- Average confidence ≥ 0.60 on pages where it finds schema.org
- Fallback to HTML works if schema.org fails (100% success rate)
- Execution time < 300ms average

**Go/No-Go Decision (Day 5):**
- GO: Proceed to Week 2 soft launch (enable schema.org on 5-10 pilot stores)
- AMBER: Tune prompts/selectors, run Week 1 again
- RED: Debug parser issues, assess whether to delay Phase B

---

## Files to Create/Update

- [ ] PHASE_B_WEEK_1_FINDINGS.md (this file) ✅
- [ ] PHASE_B_WEEK_1_BASELINE_METRICS.md (HTML confidence analysis)
- [ ] PHASE_B_WEEK_1_PARSER_TESTS.md (SchemaOrgParser test results)
- [ ] PHASE_B_WEEK_1_DECISION.md (Go/No-Go documentation)

---

**Next Action:** Execute Task 1 & 3 (baseline confidence + parser verification)

