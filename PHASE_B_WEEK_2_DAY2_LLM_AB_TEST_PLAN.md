# Phase B Week 2: Day 2 - LLM v1.0.0 vs v2.0.0 A/B Test Plan

**Date:** Tuesday, May 28, 2026  
**Task:** Compare LLM extraction quality: v1.0.0 vs v2.0.0  
**Status:** 🔲 Planning phase

---

## A/B Test Objectives

1. **Measure v2.0.0 improvement** over v1.0.0 baseline
2. **Validate confidence calibration** (claimed vs actual)
3. **Assess field completeness gains** (which fields improve most?)
4. **Calculate cost impact** (token usage per version)
5. **Inform deployment decision** for Friday rollout

---

## Test Design

### Test Sample: 100 Stores (Stratified Random)

Selected to represent full spectrum of extraction challenges:

| Category | Count | Selection Criteria |
|----------|-------|-------------------|
| Good extractors | 20 | Already 0.6+ confidence with static |
| Failing stores | 30 | Currently 0 products extracted |
| Mixed results | 20 | 0.3-0.6 confidence range |
| Random sampling | 30 | Random selection from all 807 stores |
| **Total** | **100** | **Diverse representation** |

**Sample size:** 100 stores (12% of 807 HTML stores)
**Confidence interval:** ±10% at 95% confidence (statistically valid)

---

## Extraction Protocol

### For Each Store:

1. **Fetch all source pages** (all product pages discovered)
2. **Clean HTML to text** using existing `clean_page_text()` utility
3. **Extract with v1.0.0** LLMParser
   - Prompt: v1.0.0 (default, no domain context)
   - Model: claude-opus-4-1
   - Record: confidence, fields extracted, tokens used
4. **Extract with v2.0.0** LLMParser
   - Prompt: v2.0.0 (domain context injection)
   - Model: claude-opus-4-1
   - Record: confidence, fields extracted, tokens used
5. **Compare results** for each extraction

### Metrics Per Extraction

```python
{
  "store_domain": "hasbean.co.uk",
  "store_id": "uuid-here",
  "page_url": "https://...",
  "v1_confidence": 0.50,
  "v2_confidence": 0.75,
  "confidence_improvement": 0.25,
  "v1_fields": ["name", "price", "weight"],
  "v2_fields": ["name", "price", "weight", "origin", "roast"],
  "fields_gained": ["origin", "roast"],
  "v1_tokens_in": 1200,
  "v1_tokens_out": 300,
  "v2_tokens_in": 1400,
  "v2_tokens_out": 320,
  "v1_cost_usd": 0.0042,
  "v2_cost_usd": 0.0051,
  "extraction_time_sec": 3.2,
  "errors": None
}
```

---

## Measurement Framework

### Primary Metrics (Confidence & Completeness)

1. **Confidence Score** (0.0-1.0)
   - Claimed by LLM ("What's your confidence in this extraction?")
   - Compare: v1 avg vs v2 avg
   - Target: v2 >= v1 + 0.10 improvement

2. **Field Completeness** (0-7 fields)
   - Count: coffee_name, origin_country, process, roast_level, varietal, flavour_notes, price_variants
   - Compare: v1 avg vs v2 avg
   - Target: v2 >= v1 + 1 additional field

3. **Specific Field Improvements**
   - Which fields improve most?
   - Track: origin extraction, varietal detection, flavour notes parsing
   - Identify: which domains benefit most from v2

### Secondary Metrics (Cost & Performance)

4. **Token Efficiency**
   - Input tokens: typical page text length
   - Output tokens: JSON response size
   - Cost per extraction: at Claude Opus rates
   - Compare: v1 vs v2 cost difference

5. **Extraction Time**
   - API latency (seconds per extraction)
   - Compare: v1 vs v2 (should be similar)
   - Flag any significant differences

### Quality Metrics (Observed)

6. **Validity Rates**
   - % of v1 extractions: valid, partial, invalid
   - % of v2 extractions: valid, partial, invalid
   - Compare: improved validity with v2?

7. **Error Patterns**
   - Any JSON parse errors?
   - Any field validation failures?
   - Rate: v1 errors vs v2 errors

---

## Hypothesis & Expected Results

### Hypothesis
**v2.0.0 will improve extraction quality across all metrics:**
- Higher average confidence (0.10+ improvement)
- More complete field extraction (1+ additional field)
- Better handling of specialty coffee data
- Minimal cost increase (< 20% more tokens)

### Expected Results (Based on Prompt Design)

| Metric | v1.0.0 | v2.0.0 | Improvement |
|--------|--------|--------|-------------|
| Avg confidence | 0.45 | 0.60 | +0.15 (+33%) |
| Avg fields extracted | 3.2 | 4.5 | +1.3 (+41%) |
| Varietal detection rate | 25% | 50% | +25% |
| Flavour notes found | 40% | 70% | +30% |
| Avg tokens input | 1,200 | 1,400 | +200 (+17%) |
| Avg tokens output | 300 | 380 | +80 (+27%) |
| Cost per extraction | $0.0042 | $0.0055 | +$0.0013 (+31%) |
| Extraction time | 3.0s | 3.1s | +0.1s (+3%) |

**Note:** These are estimates; actual results will drive deployment decision.

---

## A/B Test Execution Plan

### Phase 1: Sample Preparation (30 minutes)
- [ ] Query 100 random stores (stratified by category)
- [ ] Fetch all source pages for each store
- [ ] Clean HTML → text for all pages
- [ ] Prepare extraction queue

### Phase 2: v1.0.0 Baseline (1 hour)
- [ ] Run LLMParser v1.0.0 on all 100 stores
- [ ] Record: confidence, fields, tokens, time
- [ ] Collect metrics in CSV

### Phase 3: v2.0.0 Testing (1 hour)
- [ ] Run LLMParser v2.0.0 on same 100 stores
- [ ] Record: confidence, fields, tokens, time
- [ ] Collect metrics in CSV

### Phase 4: Analysis (1 hour)
- [ ] Aggregate metrics by category
- [ ] Calculate confidence improvements
- [ ] Identify field improvements per type
- [ ] Analyze cost difference
- [ ] Statistical significance testing

### Phase 5: Decision & Documentation (30 minutes)
- [ ] Create comparison report
- [ ] Recommend: keep v1, switch to v2, or hybrid
- [ ] Plan next steps for Wednesday

---

## Key Measurement Points

### Per-Store Analysis
- Which stores improve most with v2?
- Which stores regress (if any)?
- Pattern analysis: what types benefit from v2?

### Per-Field Analysis
- Origin extraction: improvement rate?
- Varietal extraction: improvement rate?
- Flavour notes: improvement rate?
- Which fields don't improve?

### Category Analysis
- Good extractors (v1 0.6+): does v2 help?
- Failing stores (v1 0.0): can v2 salvage them?
- Mixed results (v1 0.3-0.6): does v2 push above threshold?
- Random sample: representative improvements?

### Cost Analysis
- Token increase: acceptable?
- Cost per extraction: difference significant?
- Break-even analysis: worth the cost increase?

---

## Success Criteria

**A/B test is successful if:**

1. ✅ **Confidence improvement:** v2 avg >= v1 + 0.10
2. ✅ **Field completeness:** v2 avg >= v1 + 1 field
3. ✅ **No regressions:** v2 doesn't underperform on v1-good stores
4. ✅ **Cost acceptable:** token increase < 25%
5. ✅ **Data quality:** no increase in JSON errors

**Decision matrix:**
- **5/5 criteria met** → Deploy v2.0.0 immediately (Friday)
- **4/5 criteria met** → Deploy v2.0.0 with tweaks (Friday)
- **3/5 criteria met** → Hybrid approach needed (Fri + ongoing)
- **<3/5 criteria met** → Keep v1.0.0, improve prompt later

---

## Contingency Plans

### If v2.0.0 Performs Worse
- **Reason:** Prompt changes may introduce new failure modes
- **Action:** Revert to v1.0.0, debug in Week 3
- **Fallback:** Deploy v1.0.0 Friday, plan v2 improvements

### If Cost Too High
- **Reason:** Domain context + larger prompt = more tokens
- **Action:** Optimize prompt, reduce context information
- **Fallback:** Use v2.0.0 for 50% of stores (cost-sensitive)

### If Mixed Results Per Category
- **Reason:** v2.0.0 may help failing stores, not good ones
- **Action:** Consider category-specific deployment
- **Fallback:** v2 for low-confidence (<0.4), v1 for high

### If Statistical Noise (No Clear Winner)
- **Reason:** 100-store sample may not show significant difference
- **Action:** Larger test (200 stores) or longer evaluation
- **Fallback:** A/B split deployment (50/50), measure production

---

## Cost Estimation

### LLM API Costs (Claude Opus-4-1 Pricing)

**Input tokens:** $0.015 per 1M tokens  
**Output tokens:** $0.06 per 1M tokens  

**Assumptions:**
- v1.0.0: ~1,200 input, ~300 output per extraction
- v2.0.0: ~1,400 input, ~380 output per extraction
- 100 extractions to test each

**Cost calculation:**
```
v1.0.0:
  Input: 100 * 1,200 * $0.015 / 1,000,000 = $0.0018
  Output: 100 * 300 * $0.06 / 1,000,000 = $0.0018
  Total: $0.0036 per 100 extractions = $0.000036 per extraction

v2.0.0:
  Input: 100 * 1,400 * $0.015 / 1,000,000 = $0.0021
  Output: 100 * 380 * $0.06 / 1,000,000 = $0.0023
  Total: $0.0044 per 100 extractions = $0.000044 per extraction

Difference: +$0.000008 per extraction (+22% cost increase)
```

**For 100-store sample:** ~$0.36 for v1 + $0.44 for v2 = **$0.80 total**

---

## Deliverables (Tuesday Evening)

1. ✅ **LLM A/B Test Report** (`PHASE_B_WEEK_2_DAY2_LLM_REPORT.md`)
   - Executive summary
   - Confidence improvement data
   - Field completeness analysis
   - Cost comparison
   - Deployment recommendation

2. ✅ **Comparison Metrics CSV** (`llm_ab_test_metrics.csv`)
   - 100 rows (one per store sample)
   - 20+ columns (all metrics)
   - Raw data for further analysis

3. ✅ **Calibration Data** (`confidence_calibration.json`)
   - Binned confidence vs actual quality
   - Validation of confidence claims
   - Calibration adjustments needed (if any)

4. ✅ **Recommendation** (for Wednesday & Friday)
   - Deploy v2.0.0? Y/N/Hybrid
   - Suggested rollout strategy
   - Monitoring plan

---

## Timeline

**Tuesday Afternoon:**
- 2:00 PM: Preparation & sample selection (30 min)
- 2:30 PM: v1.0.0 baseline extraction (1 hour)
- 3:30 PM: v2.0.0 A/B testing (1 hour)
- 4:30 PM: Analysis & reporting (1.5 hours)
- 6:00 PM: Complete

**Tuesday Evening:**
- Generate reports
- Create visualizations (if time permits)
- Prepare Wednesday morning standup

---

## Success Definition

**A/B test is valid if:**
1. ✅ All 100 stores extracted successfully (no timeout aborts)
2. ✅ Data quality acceptable (< 5% errors)
3. ✅ Statistical significance clear (p < 0.05 if using)
4. ✅ Confidence improvement measurable (>= ±0.05 change)
5. ✅ Cost impact quantified (exact token counts recorded)

If all 5 met → Test results are actionable
If 4/5 met → Test results are useful with caveats
If <4/5 met → May need repeat test

---

## Approval to Proceed

**A/B test scheduled to begin:** Tuesday afternoon  
**Expected completion:** Tuesday evening  
**Report delivery:** Wednesday morning (Day 3 standup)

Ready to execute. Both prompts already integrated.

---

**Prepared for:** Phase B Week 2, Day 2 - LLM A/B Testing
**Status:** Ready for execution
**Next document:** PHASE_B_WEEK_2_DAY2_LLM_REPORT.md (after testing completes)
