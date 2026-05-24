# Phase B Week 2: Day 2 (Tuesday) - Test Planning Complete

**Date:** Tuesday, May 28, 2026  
**Time:** Morning (Planning phase)  
**Status:** 🔲 READY FOR EXECUTION (Tests scheduled for afternoon)

---

## Executive Summary

Both tracks have detailed test plans prepared and are ready for afternoon execution:

### Track 1: BrowserExtractor Pilot Testing
- ✅ Test plan created with 10 pilot stores
- ✅ Metrics framework defined
- ✅ Success criteria established
- 🔲 **Execution scheduled:** Afternoon (2-4 PM)
- **Deliverable:** Pilot test report (evening)

### Track 2: LLM v1 vs v2 A/B Testing
- ✅ Test design finalized (100-store stratified sample)
- ✅ Measurement framework defined
- ✅ Cost estimation complete
- 🔲 **Execution scheduled:** Afternoon (2-6 PM)
- **Deliverable:** A/B test report (evening)

---

## Track 1: BrowserExtractor Pilot Testing

### Test Plan Summary
**File:** `PHASE_B_WEEK_2_DAY2_PILOT_TEST_PLAN.md`

**Objective:** Validate BrowserExtractor performance on real sites

**Test Sample:** 10 diverse stores
- 4 problematic sites (SPA/heavy JS)
- 4 mixed architecture sites
- 2 good baseline sites (already extracting well)
- Total: 120 product pages

**Success Criteria:**
1. Average render time: < 5 seconds
2. Timeout rate: < 10%
3. Fallback trigger rate: < 5%
4. Confidence improvement: +0.2 average over static
5. 70+ products extracted from 120 pages

**Metrics Collected:**
- Render time per page
- Timeout occurrences
- Fallback trigger rate
- Confidence scores (rendered vs static)
- Field completeness
- Products extracted
- Memory usage
- Errors/exceptions

**Contingency Plans:**
- Browser crashes → auto-recovery via pool
- Network timeouts → fallback to static extraction
- Memory issues → reduce concurrent contexts
- Performance issues → documented for Wednesday optimization

**Expected Outcome:**
- If 4/5 success criteria met → Proceed to optimization
- If 3/5 criteria met → Wednesday tuning needed
- If <3/5 criteria met → Strategy reassessment

---

## Track 2: LLM A/B Test

### Test Plan Summary
**File:** `PHASE_B_WEEK_2_DAY2_LLM_AB_TEST_PLAN.md`

**Objective:** Compare v1.0.0 vs v2.0.0 extraction quality

**Test Sample:** 100 stores (stratified)
- 20 good extractors (baseline: 0.6+ confidence)
- 30 failing stores (0 products extracted)
- 20 mixed results (0.3-0.6 confidence)
- 30 random sampling
- Total: 100 stores representing full spectrum

**Primary Metrics:**
1. **Confidence:** Average improvement (target: +0.10)
2. **Completeness:** Fields extracted (target: +1 additional field)
3. **Specific improvements:** Which fields gain most?

**Secondary Metrics:**
4. **Token usage:** Input/output tokens per version
5. **Cost impact:** Price per extraction comparison
6. **Performance:** Extraction time per version
7. **Validity:** Error rates (valid/partial/invalid)

**Expected Results (Hypothesis):**
| Metric | v1.0.0 | v2.0.0 | Improvement |
|--------|--------|--------|-------------|
| Avg confidence | 0.45 | 0.60 | +0.15 |
| Avg fields | 3.2 | 4.5 | +1.3 |
| Varietal detection | 25% | 50% | +25% |
| Flavour notes | 40% | 70% | +30% |
| Token input | 1,200 | 1,400 | +17% |
| Cost increase | - | - | +31% (acceptable) |

**Contingency Plans:**
- If v2.0.0 worse → Revert to v1.0.0, debug later
- If cost too high → Optimize prompt or use hybrid approach
- If mixed results → Category-specific deployment
- If no clear winner → A/B split deployment in production

**Success Criteria:**
- 5/5 criteria met → Deploy v2.0.0 immediately (Friday)
- 4/5 criteria met → Deploy v2.0.0 with tweaks (Friday)
- 3/5 criteria met → Hybrid approach needed
- <3/5 criteria met → Keep v1.0.0, improve later

---

## Testing Schedule (Afternoon, May 28)

### Track 1 (Browser Automation)
```
2:00 PM - 2:30 PM: Setup & initialization
  - Verify BrowserExtractor imports
  - Create test harness
  - Initialize browser pool

2:30 PM - 4:00 PM: Extraction execution
  - Run BrowserExtractor on 10 stores
  - Collect metrics for 120 pages
  - Log errors in real-time

4:00 PM - 4:30 PM: Analysis & reporting
  - Aggregate metrics
  - Calculate averages & percentiles
  - Create preliminary findings
```

### Track 2 (LLM A/B Test)
```
2:00 PM - 2:30 PM: Preparation
  - Query 100-store sample
  - Fetch source pages
  - Clean HTML → text

2:30 PM - 3:30 PM: v1.0.0 Baseline
  - Run LLMParser v1.0.0 on all 100
  - Record: confidence, fields, tokens

3:30 PM - 4:30 PM: v2.0.0 A/B Test
  - Run LLMParser v2.0.0 on same 100
  - Record: confidence, fields, tokens

4:30 PM - 6:00 PM: Analysis & Reporting
  - Compare metrics
  - Calculate improvements
  - Statistical significance
  - Cost analysis
```

### Parallel Execution
- Both tracks run simultaneously (no blocking)
- Monitor for issues in real-time
- Adapt if needed (fallbacks ready)

---

## Cost Estimate for Tuesday

### Browser Automation (Track 1)
- **Cost:** $0 (no API calls)
- **Resource:** Local Playwright, zero marginal cost
- **Time:** 4 hours

### LLM A/B Testing (Track 2)
- **v1.0.0 baseline:** 100 extractions × $0.000036 = **$0.0036**
- **v2.0.0 testing:** 100 extractions × $0.000044 = **$0.0044**
- **Total:** ~**$0.008** (negligible)
- **Time:** 4 hours

### Combined Tuesday Cost
- **Total:** ~$0.01 (tracking purposes only)
- **Budget remaining:** $549.99 / $550

---

## Deliverables Expected (Tuesday Evening)

### Track 1: BrowserExtractor
1. ✅ `PHASE_B_WEEK_2_DAY2_PILOT_REPORT.md`
   - Performance summary
   - Per-store results table
   - Aggregate statistics
   - Recommendations

2. ✅ `pilot_test_metrics.csv`
   - Raw metrics (120 rows)
   - All measured fields
   - Ready for spreadsheet analysis

### Track 2: LLM A/B Test
1. ✅ `PHASE_B_WEEK_2_DAY2_LLM_REPORT.md`
   - Comparison summary
   - Confidence improvements
   - Field completeness gains
   - Cost analysis
   - Deployment recommendation

2. ✅ `llm_ab_test_metrics.csv`
   - Per-store results (100 rows)
   - v1 vs v2 metrics
   - Improvement calculations

3. ✅ `confidence_calibration.json`
   - Confidence vs quality validation
   - Calibration data for later use

---

## Day 2 Timeline

| Time | Activity | Track 1 | Track 2 | Status |
|------|----------|---------|---------|--------|
| **9:00 AM** | Planning finalized | ✅ | ✅ | Ready |
| **2:00 PM** | Tests begin | 🟢 | 🟢 | Starting |
| **4:30 PM** | Track 1 complete | ✅ | 🔄 | Halfway |
| **6:00 PM** | Track 2 complete | ✅ | ✅ | Done |
| **6:30 PM** | Reports written | ✅ | ✅ | Delivered |
| **7:00 PM** | Day 2 standup | ✅ | ✅ | Final status |

**Total time:** 9 hours (4h execution + 5h planning/documentation)  
**Planning time:** Already completed  
**Execution time:** 2-6 PM (4 hours)  
**Documentation time:** 6-7 PM (1 hour)

---

## Risks & Mitigations

### Browser Automation Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Browser crashes | Low | Medium | Auto-recovery via pool |
| Timeouts | Medium | Low | Fallback to static extraction |
| Memory issues | Low | Medium | Monitor & reduce contexts |
| Network failures | Low | Low | Retry logic, timeout handling |

### LLM A/B Test Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| v2.0.0 performs worse | Low | Medium | Keep v1.0.0 as default |
| Cost too high | Low | Low | Hybrid deployment strategy |
| API rate limits | Very low | Medium | Batch requests, retry backoff |
| JSON parse errors | Low | Low | Logged, continues to next |

**Overall Risk:** Low (all mitigated)

---

## Wednesday Preparation

### If Browser Tests Succeed (4-5/5 criteria met)
**Wednesday:** Optimization phase
- [ ] Analyze performance bottlenecks
- [ ] Optimize selector matching
- [ ] Tune timeout thresholds
- [ ] Expected: Small tweaks, proceed to deployment

### If Browser Tests Need Work (3/5 criteria met)
**Wednesday:** Tuning phase
- [ ] Debug slow pages
- [ ] Adjust render timeouts (perhaps 7s instead of 10s)
- [ ] Improve selector detection
- [ ] Re-test on problem stores

### If LLM v2.0.0 Significantly Better (+0.15 confidence)
**Wednesday:** Integration & decision
- [ ] Integrate v2.0.0 into LLMParser
- [ ] Make default for Friday rollout
- [ ] Update LLM service config

### If LLM v2.0.0 Mixed Results
**Wednesday:** Refinement decision
- [ ] Analyze per-category results
- [ ] Consider hybrid deployment
- [ ] Prepare rollout strategy

---

## Key Decision Points (End of Day 2)

### Decision 1: Browser Automation Path
**Question:** Do we proceed with browser automation as-is, or optimize?
**Data:** Pilot test results (render time, fallback rate, confidence)
**Decision:** Go/Optimize/Abort
**Timeline:** Decide by 6 PM, Wednesday action based on this

### Decision 2: LLM Prompt Version
**Question:** Deploy v2.0.0, keep v1.0.0, or hybrid?
**Data:** A/B test results (confidence improvement, cost)
**Decision:** v2 deploy / v1 keep / hybrid split
**Timeline:** Decide by 6 PM, Wednesday implementation

---

## Communication Plan

### Tuesday Evening (6-7 PM)
- Complete final reports
- Write summary findings
- Prepare Wednesday morning standup

### Wednesday Morning (9 AM)
- Day 2 standup with metrics
- Present findings to stakeholders
- Decision on path forward

### Wednesday Afternoon
- Execute decisions (optimization or deployment prep)
- Document changes

---

## Success Metrics for Day 2

**Track 1 Success:**
- ✅ No unhandled exceptions during testing
- ✅ Metrics collected for all 120 pages
- ✅ Performance baseline established
- ✅ Clear recommendation for next steps

**Track 2 Success:**
- ✅ Both v1 and v2 run successfully
- ✅ Data quality confirmed (< 5% errors)
- ✅ Confident improvement measurement
- ✅ Clear deployment recommendation

**Combined Success:**
- ✅ All tests complete by 6 PM
- ✅ Reports delivered by 7 PM
- ✅ Clear direction for Wednesday

---

## Next Steps (Thursday & Friday)

### Thursday (Day 4): Deployment Preparation
**Track 1:**
- [ ] Infrastructure setup for top 50 stores
- [ ] Staging environment ready
- [ ] Monitoring configured

**Track 2:**
- [ ] Staging deployment of selected prompt version
- [ ] Quality validation on 80-store sample
- [ ] Cost tracking setup

### Friday (Day 5): Production Go-Live
**Track 1:**
- [ ] Deploy BrowserExtractor to top 50 stores
- [ ] Monitor for issues
- [ ] Collect early metrics

**Track 2:**
- [ ] Roll out LLM version to 10% of stores (80 stores)
- [ ] Monitor for issues
- [ ] Collect cost data

**Both:**
- [ ] Generate Week 2 final report
- [ ] Document lessons learned
- [ ] Plan Week 3 expansion

---

## Status Summary

🟢 **READY FOR EXECUTION**

**Tuesday Afternoon:** Both test plans ready, full execution team prepared
- BrowserExtractor pilot testing: 10 stores, 120 pages
- LLM A/B testing: 100 stores, 200 total samples
- Expected completion: 6-7 PM (reports & analysis)

**Wednesday Morning:** Data-driven decision making
- Results presented
- Path forward chosen
- Week 2 final push begins

**Risk Level:** Low (all contingencies planned)  
**Timeline:** On track  
**Resources:** Allocated and ready

---

**Prepared for:** Phase B Week 2, Day 2 - Execution Readiness
**Status:** ✅ All systems ready, tests scheduled for afternoon
**Next document:** PHASE_B_WEEK_2_DAY2_PILOT_REPORT.md (after testing completes)
