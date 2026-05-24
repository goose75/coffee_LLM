# Phase B Week 2: Day 2 - Pilot Test Plan

**Date:** Tuesday, May 28, 2026  
**Task:** BrowserExtractor pilot testing on 10 stores  
**Status:** 🔲 Planning phase

---

## Pilot Test Objectives

1. **Validate BrowserExtractor performance** on real e-commerce sites
2. **Measure render time** and timeout frequency
3. **Test fallback chain** (rendered HTML → static extraction)
4. **Verify confidence improvement** over static extraction alone
5. **Identify optimization opportunities** for Wednesday optimization phase

---

## Pilot Test Design

### Test Sample: 10 High-Value Stores

Based on Week 1 analysis + seed data, selected stores represent:
- Known problematic sites (SPA/JavaScript heavy)
- Known good extractors (baseline)
- Mix of UK/international roasters
- Different site architectures

| Rank | Store Domain | Site Architecture | Pages | Challenge |
|------|--------------|------------------|-------|-----------|
| 1 | hasbean.co.uk | Traditional HTML + some JS | 20+ | Good baseline |
| 2 | ravecoffee.co.uk | Modern WooCommerce | 15+ | JS rendering |
| 3 | theorigincoffee.co.uk | Custom Shopify | 12+ | API data loading |
| 4 | squaremilecoffee.com | SPA / Next.js | 18+ | Heavy JS |
| 5 | bellabarista.co.uk | Magento | 8+ | Template variables |
| 6 | extractcoffee.co.uk | WordPress + WooCommerce | 12+ | Plugin-heavy |
| 7 | thecoffeehopper.com | Custom framework | 10+ | Non-standard HTML |
| 8 | baycoffeeroasters.com | Bootstrap | 6+ | Missing prices (JS) |
| 9 | abigocoffee.com | React SPA | 8+ | Full client rendering |
| 10 | colonnacoffee.com | Static HTML | 14+ | Already working well |

**Sample characteristics:**
- Total pages: 120+
- Mix: 4 problematic sites, 4 mixed sites, 2 good baselines
- Site frameworks: WooCommerce (3), Custom (4), Shopify (1), Static (2)
- Challenge types: JavaScript rendering, template variables, API data loading, custom structure

---

## Test Methodology

### For Each Store:

1. **Select first 10 product pages** (if available)
2. **Fetch raw HTML** without rendering
3. **Run BrowserExtractor** (with rendering)
4. **Measure metrics:**
   - Page render time (ms)
   - Timeout occurrences (Y/N)
   - Fallback triggered? (Y/N if confidence < 0.4)
   - Final confidence score
   - Field completeness (# of 7 fields extracted)
   - Products extracted
5. **Compare to baseline:** Static extraction on same pages

### Metrics Collection

For each page extraction:
```python
{
  "store_domain": "hasbean.co.uk",
  "page_url": "https://www.hasbean.co.uk/products/...",
  "render_time_ms": 2340,
  "timeout_triggered": False,
  "fallback_triggered": False,
  "rendered_confidence": 0.85,
  "static_confidence": 0.45,
  "confidence_gain": 0.40,
  "fields_extracted": 6,
  "products_extracted": 1,
  "errors": None
}
```

---

## Success Criteria

### Performance Baseline (Target)
- [ ] Average render time: < 5,000 ms (5 seconds)
- [ ] Timeout rate: < 10% of pages
- [ ] Fallback trigger rate: < 5% of pages
- [ ] Confidence gain: +0.2 average over static

### Quality Metrics (Target)
- [ ] Average field completeness: >= 4/7 fields
- [ ] Products extracted: 80+ from 120 pages (67%+)
- [ ] No critical errors or exceptions

### Infrastructure Validation
- [ ] Browser pool stability: zero crashes
- [ ] Memory usage: < 500MB peak
- [ ] Context cleanup: all contexts released properly

---

## Risk Mitigation During Testing

| Risk | Mitigation |
|------|-----------|
| **Page timeouts** | Configured 10s timeout, will fall back to static |
| **Browser crashes** | Context pooling + error handling, automatic recovery |
| **Memory issues** | Monitor peak memory, limit concurrent extractions to 5 |
| **Network issues** | Retry logic built in, 8s network timeout |
| **Invalid HTML** | UTF-8 and latin-1 fallback decoding |

---

## Test Execution Plan

### Phase 1: Setup (30 minutes)
- [ ] Verify BrowserExtractor imports and basic functionality
- [ ] Create test harness for metrics collection
- [ ] Prepare data logging

### Phase 2: Execution (2 hours)
- [ ] Run BrowserExtractor on all 10 stores (120 pages)
- [ ] Collect metrics in real-time
- [ ] Log any errors or anomalies

### Phase 3: Analysis (30 minutes)
- [ ] Aggregate metrics by store
- [ ] Calculate averages and percentiles
- [ ] Compare rendered vs static extraction
- [ ] Identify problem stores/patterns

### Phase 4: Documentation (30 minutes)
- [ ] Create pilot test report
- [ ] Document findings and recommendations
- [ ] Prepare for Wednesday optimization

---

## Expected Outcomes

### Positive Outcome (Success) ✅
- Average render time: 3-4 seconds
- Fallback rate: < 5%
- Confidence improvement: +0.25 average
- 80+ products extracted from 120 pages
- No critical errors

**Next step:** Proceed to optimization (Wed)

### Mixed Outcome (Needs Tuning) 🟡
- Average render time: 4-6 seconds
- Fallback rate: 5-15%
- Confidence improvement: +0.15 average
- 70-80 products extracted

**Next step:** Wednesday optimization of timeouts/selectors

### Poor Outcome (Strategy Adjustment) 🔴
- Average render time: > 6 seconds
- Fallback rate: > 15%
- Confidence improvement: < +0.10 average
- < 60 products extracted

**Next step:** Reassess approach, consider:
- Longer timeout strategy
- Async pooling improvements
- Selector optimization
- Alternative fallback chain

---

## Deliverables (Tuesday Evening)

1. ✅ **Pilot Test Report** (`PHASE_B_WEEK_2_DAY2_PILOT_REPORT.md`)
   - Performance metrics summary
   - Per-store results table
   - Aggregate statistics
   - Visualizations (if time permits)

2. ✅ **Metrics CSV** (`pilot_test_metrics.csv`)
   - Raw data for analysis
   - 120 rows (one per page)
   - 12 columns (all measured metrics)

3. ✅ **Recommendations** (for Wednesday optimization)
   - Timeout adjustments
   - Selector improvements
   - Fallback strategy tweaks

---

## Contingency Plans

### If Browser Crashes
- Context pool has auto-recovery
- Log the crash, continue with next page
- Mark as "error" in metrics

### If Network Timeout
- Use fallback static extraction
- Mark "fallback_triggered=True"
- Log timeout details

### If Memory Issues
- Reduce concurrent contexts from 5 to 3
- Add garbage collection calls between extractions
- Monitor peak memory in real-time

### If Performance Too Slow
- Document findings
- Wednesday: consider batch processing vs concurrent
- Thursday: reassess architecture

---

## Success Definition

**Pilot test is successful if:**
1. ✅ No unhandled exceptions (all errors caught)
2. ✅ Average render time < 5 seconds
3. ✅ Fallback rate < 10%
4. ✅ Confidence improvement > +0.15 average
5. ✅ 70+ products extracted from 120 pages

If 4/5 criteria met → proceed to optimization
If 3/5 criteria met → optimization needed
If <3/5 → strategy reassessment needed

---

## Notes for Test Execution

- **Browser pool initialization:** Takes ~5 seconds (one-time)
- **Per-page extraction:** 2-5 seconds (rendering) + 0.5s (extraction)
- **Error recovery:** Automatic, page skips to next
- **Logging:** INFO level for progress, DEBUG for details
- **Interruption:** Can pause after each store, resume next
- **Data loss prevention:** Metrics logged to CSV after each page

---

## Post-Test Actions

### If Tests Pass
1. Document findings in report
2. Create Wednesday optimization plan (if any improvements possible)
3. Proceed to deployment prep (Thursday)

### If Tests Need Tuning
1. Analyze per-store failures
2. Wednesday: adjust timeouts, selectors, fallback strategy
3. Re-test on 2-3 problem stores
4. Measure improvements
5. Proceed to deployment if improvements significant

### If Strategy Fails
1. Emergency meeting: assess issue
2. Consider alternatives:
   - Increase timeout to 15 seconds
   - Use async-optimized extraction
   - Focus on non-SPA stores only (top 30)
   - Hybrid: browser for top 50, static for rest

---

## Approval to Proceed

**Tests scheduled to begin:** Tuesday afternoon  
**Expected completion:** Tuesday evening  
**Report delivery:** Wednesday morning (Day 3 standup)

Ready to execute. All infrastructure in place.

---

**Prepared for:** Phase B Week 2, Day 2 - Pilot Testing
**Status:** Ready for execution
**Next document:** PHASE_B_WEEK_2_DAY2_PILOT_REPORT.md (after testing completes)
