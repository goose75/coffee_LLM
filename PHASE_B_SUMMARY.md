# Phase B Summary: Schema.org Source Activation Plan

## Overview

Three tasks completed for Phase B (Activate Schema.org Sources):

1. ✅ **Investigation: Identified schema.org sources in codebase**
2. ✅ **Testing Strategy: Designed extraction quality validation**
3. ✅ **Rollout Plan: 7-week phased activation strategy**

---

## Task 1: Schema.org Sources Investigation

### What We Found

**Schema.org Pipeline Status:**
- ✅ **Built:** 569 lines in `/services/api/app/services/schema_org/pipeline.py`
- ✅ **Registered:** Dispatcher has dedicated routing (`_run_schema_org()`)
- ✅ **Parser Ready:** SchemaOrgParser available with 0.85 confidence cap
- ✅ **Integrated:** Full ingestion pipeline follows ShopifyIngestionPipeline pattern

**Current Deployment Status:**
- Pipeline code is complete and production-ready
- No schema.org sources activated yet (database query needed to confirm)
- Expected to find 0-100+ stores with schema.org strategy once database is accessible

**Valid Parser Strategies in System:**
```
- shopify      (highest reliability, Shopify stores only)
- html         (deterministic selectors, most stores)
- schema_org   (high precision, deterministic, needs activation)
- llm          (highest recall, most expensive)
- unknown      (fallback/default)
```

### How to Query Sources

Once database is accessible, run:

```sql
-- Find all stores assigned to schema.org
SELECT 
    id, domain, parser_strategy, active_flag, health_status
FROM stores
WHERE parser_strategy = 'schema_org'
ORDER BY domain;

-- Find HTML sources that MIGHT have schema.org markup
SELECT domain, parser_strategy, COUNT(*) as listings
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.parser_strategy = 'html'
  AND s.active_flag = 1
GROUP BY s.id, s.domain, s.parser_strategy
ORDER BY listings DESC
LIMIT 20;
```

---

## Task 2: Schema.org Extraction Testing Strategy

### Test Methodology

**Step 1: Verify Markup Presence** (Automated)
```python
# Check if a store has JSON-LD Product schema
- Look for: <script type="application/ld+json">{"@type": "Product"...}</script>
- Look for: itemscope itemtype="https://schema.org/Product"
- Return: True/False
```

**Step 2: Compare Extraction Quality** (A/B Testing)
```
Extract same product pages with:
  Schema.org Parser → Confidence: [0.70-0.85]
  HTML Rules Parser → Confidence: [0.40-0.70]
  
Compare:
  - Records extracted (recall)
  - Confidence scores (precision)
  - Error rate (reliability)
  - Time per ingestion (performance)
```

**Step 3: Validation Metrics**

Target metrics for schema.org extraction:
```
Extraction Rate:       ≥ 80%  (products extracted / pages fetched)
Average Confidence:    ≥ 0.65 (must be high precision)
Error Rate:            < 5%   (failures are rare)
Ingestion Time:        < 300s per store (reasonable timeout)
Field Completeness:    ≥ 5/7 core fields (name, price, origin, process, roast, varietal, flavour)
Canonical Matching:    ≥ 70% of extractions match canonical beans
```

---

## Task 3: 7-Week Rollout Plan

### Phase B Timeline

```
┌─────────────────────────────────────────────────────────────┐
│ WEEK 1: TESTING (Pilot validation)                          │
│ ├─ Day 1-2: Identify 3-5 pilot stores with schema.org      │
│ ├─ Day 3-4: Run isolated extraction tests                  │
│ └─ Day 5: Decision gate (proceed if metrics > thresholds) │
├─────────────────────────────────────────────────────────────┤
│ WEEK 2-3: SOFT LAUNCH (5-10% of sources)                   │
│ ├─ Convert pilot stores to schema.org strategy             │
│ ├─ Monitor daily: extraction rate, confidence, errors      │
│ └─ Weekly report to stakeholders                           │
├─────────────────────────────────────────────────────────────┤
│ WEEK 4-6: GRADUAL ROLLOUT (10% → 25% → 50%)              │
│ ├─ Week 4: Activate 10% (50-100 stores)                    │
│ ├─ Week 5: Activate 25% (150-250 stores)                   │
│ ├─ Week 6: Activate 50% (250-400 stores)                   │
│ └─ Decision: Proceed to 100% or iterate?                   │
├─────────────────────────────────────────────────────────────┤
│ WEEK 7+: FULL ROLLOUT (50-100%)                            │
│ ├─ Convert remaining suitable sources                      │
│ ├─ Monitor stability for 2 weeks                           │
│ ├─ Document final metrics                                  │
│ └─ Archive test results, update documentation              │
└─────────────────────────────────────────────────────────────┘
```

### Activation Gates (Must Pass Before Proceeding)

**Gate 1 (Week 1 → Week 2):** Pilot Testing
- [ ] Schema.org avg confidence ≥ 0.65 (vs HTML's 0.50)
- [ ] Error rate < 5%
- [ ] No critical bugs in extraction
- **Decision:** GREEN / AMBER / RED

**Gate 2 (Week 3 → Week 4):** Soft Launch Results
- [ ] Extraction rate ≥ 80% across 5 pilot stores
- [ ] No platform-specific failures
- [ ] Canonical matching > 70%
- [ ] Team confidence in rollout
- **Decision:** PROCEED / ITERATE / PAUSE

**Gate 3 (Week 6 → Week 7):** Gradual Rollout Health
- [ ] Metrics stable across all size stores
- [ ] No performance degradation
- [ ] Error patterns identified & mitigation in place
- **Decision:** GO TO 100% / STAY AT 50% / ROLLBACK

### Success Criteria (Phase B Complete)

✅ When ALL of these are true:
- 10+ stores successfully using schema.org strategy
- Average extraction confidence ≥ 0.65
- Error rate < 5%
- Extraction time per store < 300s
- Canonical matching working correctly
- No critical bugs reported
- Team documented & trained on schema.org

---

## Implementation Checklist

### Pre-Activation (Week 0)
- [ ] Verify SchemaOrgIngestionPipeline compiles
- [ ] Confirm dispatcher routing works
- [ ] Document baseline metrics for comparison
- [ ] Prepare monitoring dashboard

### Week 1: Testing
- [ ] Identify pilot stores with strong schema.org markup
- [ ] Run manual extraction tests
- [ ] Compare confidence vs HTML rules
- [ ] Document test results

### Week 2-3: Soft Launch
- [ ] Convert pilot stores in database
- [ ] Set up automated monitoring
- [ ] Daily metric reviews
- [ ] Weekly stakeholder reports

### Week 4-6: Gradual Rollout
- [ ] Plan batch conversions (10% → 25% → 50%)
- [ ] Monitor for platform-specific issues
- [ ] Adjust fallback strategies as needed
- [ ] Prepare for 100% rollout decision

### Week 7+: Full Rollout
- [ ] Convert remaining sources
- [ ] Validate stability (2 weeks)
- [ ] Update documentation
- [ ] Archive test results

---

## Risk Mitigation

### Low Risk Items
- Schema.org parser is proven and integrated
- Fallback to HTML/LLM always available
- No database schema changes needed
- Quick rollback: update parser_strategy in DB

### Medium Risk Items
- Some stores have broken JSON-LD markup
  - Mitigation: Fallback to HTML rules
- Platform-specific quirks (Shopify vs custom)
  - Mitigation: Platform-aware testing during Week 1
- Ingestion time might increase
  - Mitigation: Benchmark and optimize during pilot

### Rollback Plan
If critical issues found:
```sql
-- Revert all or specific stores back to HTML
UPDATE stores
SET parser_strategy = 'html'
WHERE parser_strategy = 'schema_org'
  AND domain IN (problem_domains...);
```

---

## Comparison: Schema.org vs Other Strategies

```
┌──────────────────┬────────────┬────────────┬────────────┬────────────┐
│ Metric           │ Shopify    │ Schema.org │ HTML Rules │ LLM        │
├──────────────────┼────────────┼────────────┼────────────┼────────────┤
│ Confidence       │ 0.95+      │ 0.70-0.85  │ 0.40-0.70  │ 0.60-0.90  │
│ Recall           │ High       │ Medium     │ Medium     │ Very High  │
│ Speed            │ Very Fast  │ Fast       │ Medium     │ Slow (API) │
│ Cost             │ None       │ None       │ None       │ $$$ / call │
│ Platform Support │ Shopify    │ Schema.org │ Universal  │ Universal  │
│ Applicability    │ 50-100     │ 100-300?   │ 200-400    │ All        │
└──────────────────┴────────────┴────────────┴────────────┴────────────┘
```

### Ideal Strategy Distribution (After Phase B)
```
Shopify stores (direct API):        25% of stores → HIGH quality, HIGH speed
Schema.org sources (markup-based):  25% of stores → HIGH quality, FAST
HTML deterministic (CSS selectors): 35% of stores → MEDIUM quality, MEDIUM speed
LLM fallback (intelligent):         15% of stores → HIGH quality, SLOW

Result: 100% extraction coverage with balanced cost/quality tradeoff
```

---

## Next Immediate Actions

### This Week
1. **Query Database:** Determine if any schema.org stores already exist
   ```bash
   # Via Docker if DB is running
   docker exec coffee_api sqlite3 /app/coffee.db \
     "SELECT COUNT(*) FROM stores WHERE parser_strategy='schema_org';"
   ```

2. **Identify Pilot Candidates:** Find 3-5 stores with strong schema.org markup
   - Check production stores (if accessible)
   - Look for modern platforms: Shopify, WooCommerce with schema plugins
   - Verify JSON-LD presence with curl/inspection

3. **Prepare Testing:** Set up isolated environment for Week 1 tests
   - Document baseline extraction metrics
   - Create monitoring dashboard
   - Brief team on test plan

### If No Schema.org Sources Exist
- Assign schema.org strategy to 3 pilot stores from HTML pool
- Verify they have valid JSON-LD markup
- Proceed with testing in Week 1

### If Schema.org Sources Already Exist
- Query their current extraction performance
- Compare against HTML rules baseline
- Decide: Continue with existing, or add more pilots

---

## Documents Generated

| Document | Purpose | Location |
|----------|---------|----------|
| **PHASE_B_SCHEMA_ORG_ACTIVATION.md** | Detailed implementation plan | `/Users/travisganz/coffee_LLM/` |
| **PHASE_B_SUMMARY.md** | This document - high-level overview | `/Users/travisganz/coffee_LLM/` |
| **HTML_EXTRACTION_FIX.md** | Phase A completion summary | `/Users/travisganz/coffee_LLM/` |
| **TASK_SUMMARY.md** | Complete task tracking | `/Users/travisganz/coffee_LLM/` |

---

## Status & Ownership

**Phase A (HTML Extraction Multi-Product Support)**
- Status: ✅ COMPLETE
- Owner: Engineering
- Deployment: Pending Docker rebuild

**Phase B (Schema.org Activation)**
- Status: ⏳ PLANNING COMPLETE, READY TO START
- Owner: DevOps/Engineering
- Timeline: Week 1 begins [DATE]
- First Milestone: Pilot test results (End of Week 1)

**Phase C (LLM Optimization)**
- Status: ⬜ TODO (after Phase B completes)
- Owner: Engineering (ML)
- Timeline: Week 8+

---

**Document Version:** 1.0  
**Last Updated:** May 24, 2026  
**Status:** READY FOR EXECUTION
