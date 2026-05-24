# Phase B Week 1: Schema.org Testing & Validation
## Final Execution Plan (Days 1-5)

**Date:** May 24, 2026  
**Phase:** B  
**Week:** 1 (Testing & Validation)  
**Status:** 🟡 Ready to Execute

---

## Executive Summary

Phase A is complete and live in production (9+ products from 17grams extracting now). Phase B Week 1 is beginning with a **revised strategy based on actual data discovery**:

- Original Plan: Compare schema.org vs HTML on same top-performing stores
- **Reality Check:** Top HTML stores don't have schema.org JSON-LD markup
- **Revised Plan:** Find "opportunity stores" with weak HTML extraction and test if schema.org helps them
- **Week 1 Goal:** Validate that schema.org extraction works and adds value for stores where HTML is struggling

---

## Week 1 Timeline & Tasks

### Day 1 (Today): Initial Discovery ✅ COMPLETE

**Completed:**
- ✅ Database analysis: 841 total stores, only 49 extracting products
- ✅ Top 5 HTML stores identified: kissthehippo (226), ravecoffee (122), hasbean (120), ozonecoffee (120), origincoffee (102)
- ✅ Schema.org markup check: None found on top 5 stores
- ✅ SchemaOrgParser code verified: Production-quality, 426 lines, comprehensive
- ✅ Existing schema.org extractions found: 19 records (7 valid, 12 partial, avg confidence 0.235 vs 0.085 for HTML)
- ✅ Opportunity stores identified: 7 HTML stores with 1-20 products extracted (weak extraction)

**Deliverables:**
- ✅ PHASE_B_WEEK_1_FINDINGS.md
- ✅ PHASE_B_WEEK_1_BASELINE_METRICS.md
- ✅ PHASE_B_WEEK_1_PARSER_TESTS.md

---

### Day 2: Opportunity Store Schema.org Detection

**Tasks:**

1. **Manual Schema.org Markup Check**
   - Check each of the 7 opportunity stores for schema.org JSON-LD
   - Use browser inspect or curl to view page source
   - Document findings

   Stores to check:
   - redemptionroasters.com (20 products)
   - roundhillroastery.com (17 products)
   - girlswhogrindcoffee.com (14 products)
   - www.pactcoffee.com (10 products)
   - 17grams.co.uk (9 products) ← Already extracting via Phase A
   - sevendistricts.co.uk (1 product)
   - www.monmouthcoffee.co.uk (1 product)

2. **Test SchemaOrgParser on Sample Pages**
   - For stores with schema.org markup, fetch product page
   - Run SchemaOrgParser extraction
   - Document: validation_status, confidence, fields extracted
   - Compare to existing HTML extraction (if any)

3. **Classify Stores**
   - Schema.org found + works well → Pilot Tier 1 (high potential)
   - Schema.org found + marginal → Pilot Tier 2 (medium potential)
   - No schema.org found → Baseline (no change from HTML)

---

### Days 3-4: Extraction Testing & Comparison

**Tasks:**

1. **Run Isolated Parser Tests**
   - Select 5-7 stores for focused testing
   - For each store, run BOTH:
     - HTML extractor (existing)
     - SchemaOrgParser (new)
   - Measure & compare:
     - Coffee name (match %)
     - Price variants (count + values)
     - Origin country (presence)
     - Process type (presence)
     - Roast level (presence)
     - Overall confidence score

2. **Document Results**
   - Create comparison matrix (HTML vs schema.org per store)
   - Identify which fields schema.org captures better
   - Note any cases where schema.org contradicts HTML data

3. **Quality Assessment**
   - Manual spot-check: Pick 2-3 products from each store
   - Rate extraction quality vs actual website content
   - Validate that extracted data is accurate

**Expected Measurement Table:**

| Store | HTML Confidence | Schema.org Confidence | Winner | Notes |
|-------|-----------------|----------------------|--------|-------|
| redemption... | 0.08 | 0.25 | SO | ✅ Schema.org 3x better |
| roundhill... | 0.06 | 0.22 | SO | ✅ Schema.org found data |
| girlswho... | 0.10 | 0.00 | HTML | ❌ No schema.org |
| pactcoffee... | 0.12 | 0.20 | SO | ✅ Schema.org helps |
| 17grams... | 0.40 | 0.15 | HTML | ⚠️ HTML better (Elementor) |

---

### Day 5: Go/No-Go Decision

**Decision Gate Evaluation:**

1. **Confidence Metric** (Target: ≥ 0.20 average)
   - Calculate average confidence for schema.org extractions
   - Compare to HTML baseline

2. **Field Completeness** (Target: ≥ 5/7 core fields)
   - Count fields: coffee_name, price, weight, origin, process, roast, varietal
   - Calculate average completeness score

3. **Error Rate** (Target: < 5%)
   - Count extraction failures / total attempts
   - Expected: Some failures OK if parser is robust

4. **Extraction Speed** (Target: < 300ms per page)
   - Measure parser execution time
   - Expected: Should be fast (deterministic parsing)

5. **Team Confidence** (Target: HIGH)
   - Does parser seem production-ready?
   - Any code concerns?
   - Risk assessment acceptable?

---

## Go/No-Go Decision Criteria

### ✅ GO TO WEEK 2 SOFT LAUNCH

**Requirements (ALL must be true):**
- [ ] SchemaOrgParser produces valid/partial output on ≥ 7/10 test pages
- [ ] Average confidence ≥ 0.20 (better than HTML's 0.085)
- [ ] Error rate < 5% (graceful failures, no crashes)
- [ ] Extraction time < 300ms average
- [ ] Parser code quality: acceptable for production
- [ ] At least 3 different platform types tested successfully

**If GO:** Proceed with Week 2 soft launch on 5-10 pilot stores

---

### 🟡 AMBER (Iterate)

**Triggers:**
- [ ] SchemaOrgParser works on 5-6/10 test pages (inconsistent)
- [ ] Confidence between 0.12-0.20 (borderline)
- [ ] Works well on specific platforms only (e.g., WooCommerce) but not others
- [ ] Needs selector tuning or rule adjustments
- [ ] Parser has minor bugs but is fixable

**If AMBER:** Investigate root causes, tune selectors, retest Days 1-4 of Week 1

---

### ❌ RED (Pause)

**Triggers:**
- [ ] SchemaOrgParser fails on > 5/10 test pages
- [ ] Average confidence < 0.12 (not worth integration cost)
- [ ] Error rate > 10% or crashes observed
- [ ] Markup too variant across platforms (no unified approach works)
- [ ] Parser code has production-blocking issues
- [ ] Week 1 results unclear or inconclusive

**If RED:** 
- Pause Phase B, investigate why schema.org coverage is so low
- Focus instead on LLM improvement (Phase C) to achieve 0.65+ confidence
- Revisit Phase B in Q3 if more sites adopt schema.org

---

## Success Indicators

You'll know **Week 1 is successful** when:

1. **Data is clear:**
   - ✅ SchemaOrgParser works on ≥7/10 opportunity stores
   - ✅ Confidence measurements are consistent and documentable
   - ✅ Field completeness is measurable and useful

2. **Decision is defensible:**
   - ✅ Metrics align with success criteria above
   - ✅ Team is confident in recommendation
   - ✅ Next steps are clear (GO/AMBER/RED)

3. **Documentation is complete:**
   - ✅ PHASE_B_WEEK_1_DECISION.md written with full rationale
   - ✅ Test results documented in comparison matrix
   - ✅ Risk assessment completed

---

## Deliverables (Due Day 5)

### Documents to Produce

1. **PHASE_B_WEEK_1_DECISION.md**
   - Executive summary of Week 1 findings
   - Go/No-Go recommendation (GO / AMBER / RED)
   - Rationale and supporting data
   - Next steps

2. **PHASE_B_WEEK_1_TEST_RESULTS.md**
   - Comparison matrix (HTML vs SchemaOrg per store)
   - Field completeness analysis
   - Quality assessment notes
   - Parser execution time measurements

3. **PHASE_B_WEEK_1_OPPORTUNITY_STORES.md**
   - List of 7 opportunity stores
   - Schema.org markup findings for each
   - Recommendation for soft launch (if GO)

---

## Estimated Effort

- **Day 1:** 4 hours (investigation + data analysis) ✅ COMPLETE
- **Day 2:** 2-3 hours (manual schema.org checking + first parser tests)
- **Day 3-4:** 4-5 hours (comprehensive testing + comparison)
- **Day 5:** 1-2 hours (analysis + decision + documentation)
- **Total:** 11-15 hours

---

## Key Assumptions & Risks

### Assumptions
1. Opportunity stores DO have schema.org markup (to be validated)
2. SchemaOrgParser code is correct and functional (verified)
3. extruct library works reliably (verified)
4. Test pages are representative of store's product catalog

### Risks
- **Low:** Parser crashes or timeouts → Mitigated by error handling in code
- **Medium:** Schema.org coverage still too low → Pivot to alternative strategy
- **Medium:** Markup quality varies too much → Needs site-specific tuning
- **High:** If schema.org not available, Phase B blocked → Focus on LLM instead

### Mitigation
- Test early and often (don't wait until Day 5)
- Document failures immediately
- If stuck, escalate to team decision (GO/NO-GO earlier)
- Have LLM improvement as fallback plan

---

## Critical Files & Locations

### Code
- Parser: `/services/api/app/services/extraction/schema_org_parser.py` ✅
- Integration point: `/services/ingestion/ingestion/dispatcher.py` (update routing)
- Tests exist: `/services/api/tests/test_services/test_schema_org_pipeline.py`

### Documentation
- Phase A complete: PHASE_A_COMPLETE.md ✅
- Phase B strategy: PHASE_B_SCHEMA_ORG_ACTIVATION.md ✅
- Week 1 findings (created today):
  - PHASE_B_WEEK_1_FINDINGS.md ✅
  - PHASE_B_WEEK_1_BASELINE_METRICS.md ✅
  - PHASE_B_WEEK_1_PARSER_TESTS.md ✅

---

## Week 1 Status: 🟢 READY TO EXECUTE

All preparation complete. Ready to:
1. Check opportunity stores for schema.org markup (Day 2)
2. Run parser tests (Days 3-4)
3. Make Go/No-Go decision (Day 5)

**Next Step:** Proceed with Day 2 opportunity store schema.org detection

---

**Document Version:** 1.0  
**Status:** Week 1 Execution Ready  
**Date:** May 24, 2026

