# Phase B Week 2: Hybrid Approach Execution Kickoff

**Date:** May 27, 2026  
**Status:** 🚀 **WEEK 2 EXECUTION BEGINS**  
**Goal:** Deliver +2,100 products, 6% → 45% extraction success rate

---

## Week 2 Overview: Parallel Execution

### Track 1: Browser Automation (Modified Phase B)
**Timeline:** Mon-Fri (Days 1-5)  
**Scope:** Top 50 stores  
**Goal:** Deploy Playwright extraction by Friday EOD

### Track 2: LLM-Native Pipeline (Phase C Foundation)
**Timeline:** Mon-Fri (Days 1-5) + Weeks 3-4  
**Scope:** All 807 HTML stores  
**Goal:** LLM v2.0 prompt + 10% rollout by Friday EOD

### Expected Week 2 Outcome
- Top 50 stores: Browser automation active
- 80 stores (10%): LLM-native extraction active
- 150+ new products extracted
- Success rate: 6% → 15%
- Foundation for Weeks 3-4 expansion

---

## Track 1: Browser Automation Setup (Mon-Fri)

### Day 1 (Monday): Playwright Infrastructure

**Task 1a: Install & Configure Playwright (2 hours)**
```bash
# In /services/api
pip install playwright
playwright install chromium
```

**Task 1b: Create BrowserExtractor Service (2 hours)**
```
File: /services/api/app/services/extraction/browser_extractor.py

Key features:
  • Page rendering with timeout (10s)
  • JavaScript execution
  • Automatic fallback to static extraction
  • Error handling and recovery
  • Screenshot on failure for debugging
```

**Task 1c: Integration with Pipeline (1 hour)**
```
Update: /services/api/app/services/html/extractor.py

New chain:
  1. Try static HTML extraction
  2. If fails (< 0.4 confidence), try browser rendering
  3. Extract from rendered DOM
  4. Fallback to LLM if still failing
```

**Expected Deliverable:** BrowserExtractor class ready for testing

---

### Day 2 (Tuesday): Pilot Testing (10 Stores)

**Task 2a: Select 10 Pilot Stores (1 hour)**
```sql
-- Select top 10 by page count
SELECT s.domain, s.id, COUNT(sp.id) as pages
FROM stores s
JOIN source_pages sp ON s.id = sp.store_id
WHERE s.parser_strategy = 'html'
GROUP BY s.id, s.domain
ORDER BY COUNT(sp.id) DESC
LIMIT 10
```

**Task 2b: Run Extraction Tests (2 hours)**
- Fetch pages for each pilot store
- Run static HTML extraction
- Run browser extraction
- Compare results
- Document improvements

**Task 2c: Measure Performance (1 hour)**
- Extraction time per page
- Browser instance memory usage
- Timeout frequency
- Fallback trigger rate

**Expected Deliverable:** Pilot test report with metrics

---

### Day 3 (Wednesday): Optimization

**Task 3a: Performance Tuning (1 hour)**
- Reduce browser instance overhead
- Optimize timeout handling
- Batch page processing if needed
- Reduce memory footprint

**Task 3b: Error Handling (1 hour)**
- Handle browser crashes
- Implement retry logic
- Graceful degradation to static extraction
- Logging for debugging

**Task 3c: Quality Assurance (1 hour)**
- Verify extracted data integrity
- Check for false positives
- Validate confidence scoring
- Test edge cases

**Expected Deliverable:** Production-ready BrowserExtractor

---

### Day 4 (Thursday): Deployment Prep

**Task 4a: Infrastructure Setup (2 hours)**
- Configure browser instance pooling
- Set up resource limits
- Deploy to staging environment
- Test scaling with multiple instances

**Task 4b: Monitoring Setup (1 hour)**
- Extraction rate monitoring
- Performance metrics dashboard
- Error rate tracking
- Cost monitoring (browser resources)

**Expected Deliverable:** Staging environment ready for top 50 stores

---

### Day 5 (Friday): Production Deployment

**Task 5a: Final Validation (1 hour)**
- Run full test suite
- Verify staging metrics
- Check error logs
- Confirm fallback behavior

**Task 5b: Deploy to Top 50 Stores (1 hour)**
- Update store extraction strategy
- Activate browser automation
- Begin production extraction
- Monitor first hour of data

**Task 5c: Week 2 Metrics Report (1 hour)**
- Products extracted: Target 50-100
- Success rate improvement: Target 6% → 12%
- Performance metrics: Extract time, memory, cost
- Error rate: Target < 5%

**Expected Deliverable:** Browser automation live for top 50 stores

---

## Track 2: LLM-Native Pipeline (Phase C Foundation)

### Day 1 (Monday): Prompt Engineering (v2.0)

**Task 1a: Domain Context Analysis (1.5 hours)**
```
Research:
  • What context matters for coffee extraction?
  • How do domain types vary (UK specialty, US roasters, etc)?
  • What are common patterns we can leverage?

Output:
  • Domain context taxonomy
  • Historical pattern database structure
```

**Task 1b: LLM Prompt v2.0 Engineering (2.5 hours)**

New prompt structure:
```
System:
  • You are a specialty coffee extraction expert
  • Context: [domain type], [historical patterns]
  • Rules: [coffee-specific field definitions]
  • Examples: [10 few-shot examples - diverse cases]

Task:
  • Extract these 7 fields from the HTML
  • Rate your confidence for each field
  • Flag any uncertain extractions

Output format:
  • JSON with fields + confidence scores
  • Reasoning for confidence level
```

**Key improvements:**
- Coffee roaster vs equipment store differentiation
- Brew suitability inference from roast level
- Weight/grind option parsing
- Flavour notes extraction
- Confidence calibration (what does 0.8 really mean?)

**Expected Deliverable:** Complete LLM prompt v2.0 + 10 test examples

---

### Day 2 (Tuesday): Testing & Calibration

**Task 2a: Create Test Dataset (1 hour)**
```
Select 100 random stores:
  • 20 currently extracting well (baseline)
  • 30 with 0 extraction (challenge cases)
  • 50 random distribution
```

**Task 2b: Run v2.0 vs v1.0 Comparison (2 hours)**
```
For each of 100 test pages:
  1. Extract with v1.0 LLM prompt
  2. Extract with v2.0 LLM prompt
  3. Measure confidence improvement
  4. Compare field completeness
  5. Track token usage
```

**Task 2c: Calibration Adjustment (1 hour)**
- Analyze results
- Identify failing patterns
- Adjust prompt if needed
- Finalize v2.0

**Expected Deliverable:** Calibrated LLM v2.0 prompt ready for production

---

### Day 3 (Wednesday): Integration

**Task 3a: Update LLM Service (1.5 hours)**
```
File: /services/api/app/services/extraction/llm_parser.py

Changes:
  • Add domain_context parameter
  • Load historical patterns
  • Use v2.0 prompt
  • Implement confidence calibration
```

**Task 3b: Create LLM Pipeline (1.5 hours)**
```
New File: /services/api/app/services/llm/pipeline.py

Structure:
  • Accept store + pages
  • For each page: extract with LLM v2.0
  • Convert to BeanListing + variants
  • Return IngestionRun with metrics
```

**Expected Deliverable:** LLM-native extraction pipeline ready for testing

---

### Day 4 (Thursday): Staging Deployment

**Task 4a: Deploy to Staging (1 hour)**
- Update ingestion dispatcher
- Wire LLM pipeline for 10% of stores
- Test on staging dataset (80 stores)

**Task 4b: Quality Validation (1.5 hours)**
- Extract from 80 test stores
- Verify field extraction
- Check confidence scores
- Validate against HTML extraction for comparison

**Task 4c: Cost Analysis (0.5 hours)**
- Measure LLM API calls
- Calculate cost per extraction
- Budget for 807 stores
- Optimize if costs too high

**Expected Deliverable:** LLM pipeline tested and ready for production

---

### Day 5 (Friday): Production Rollout

**Task 5a: Enable LLM for 10% (1 hour)**
```
Update database:
  UPDATE stores
  SET extraction_strategy = 'llm_native'
  WHERE parser_strategy = 'html'
  ORDER BY RANDOM()
  LIMIT 80
```

**Task 5b: Monitor First Hour (1 hour)**
- Watch extraction logs
- Monitor API usage
- Check for errors
- Validate data quality

**Task 5c: Week 2 Metrics Report (1 hour)**
- LLM extractions: Count
- Confidence distribution
- Cost per extraction
- Comparison: HTML vs LLM
- Field completeness improvement

**Expected Deliverable:** LLM-native live for 10% of stores (80 stores)

---

## Week 2 Success Metrics

### Browser Automation Track
- [ ] Playwright installed and configured
- [ ] 10 pilot stores tested
- [ ] Top 50 stores in production
- [ ] +50-100 products extracted
- [ ] Success rate: 6% → 12%
- [ ] Browser resource usage acceptable

### LLM-Native Track
- [ ] v2.0 prompt finalized
- [ ] Tested on 100-store sample
- [ ] 80 stores (10%) in production
- [ ] +50-100 products extracted
- [ ] LLM cost acceptable
- [ ] Confidence calibration validated

### Combined
- [ ] Total products added: +100-200
- [ ] Overall success rate: 6% → 15%
- [ ] Both pipelines stable
- [ ] Monitoring dashboards live
- [ ] Week 3 scaling plan ready

---

## Resources Required (Week 2)

### Engineering
- 1 full-time engineer (main implementation)
- 0.5 engineer for monitoring/support
- 4 hours code review

### Infrastructure
- Playwright browser instances (10-20 concurrent)
- Additional database space (~100MB)
- LLM API quota (800+ extractions × 5k tokens avg)

### Estimated Costs
- Browser automation: $50-100/week
- LLM API calls: $200-300/week
- Infrastructure: $100-150/week
- **Total: $350-550/week**

---

## Risk Mitigation (Week 2)

### Risk: Browser Automation Too Slow
**Mitigation:** Test performance early (Day 1-2), optimize or reduce scope

### Risk: LLM Costs Exceed Budget
**Mitigation:** Monitor daily, adjust prompt complexity, consider cheaper model for fallback

### Risk: Both Pipelines Fail
**Mitigation:** Keep static HTML extraction as fallback, don't break existing extraction

### Risk: Data Quality Issues
**Mitigation:** Validate extracted fields, compare with manual spot-checks

---

## Daily Standup Format (Mon-Fri)

### Each Day:
```
Track 1 (Browser Automation):
  [ ] Tasks completed
  [ ] Blockers encountered
  [ ] Metrics so far
  [ ] Next day plan

Track 2 (LLM-Native):
  [ ] Tasks completed
  [ ] Blockers encountered
  [ ] Test results
  [ ] Next day plan

Combined:
  [ ] On track for Week 2 goals
  [ ] Any course corrections needed
```

---

## Week 3-4 Preview (Dependent on Week 2 Success)

### Week 3 (If Week 2 Successful)
- Expand LLM to 25% of stores (200 stores)
- Optimize browser automation for cost
- Target: +1,000 products

### Week 4 (If Week 3 Successful)
- Expand LLM to 50% of stores (400 stores)
- Document lessons learned
- Plan Phase C continuation to 100%
- Target: +2,000 products total

---

## Critical Success Factors

1. **Stay focused on hybrid approach** - Don't shift strategies mid-week
2. **Validate early** - Day 2-3 testing informs success
3. **Monitor costs** - Browser + LLM can add up
4. **Keep fallbacks** - Always able to revert to static HTML
5. **Document everything** - Metrics for week 3 decisions

---

## Deliverables by End of Week 2

**Code:**
- [ ] BrowserExtractor service (production-ready)
- [ ] LLM v2.0 prompt (calibrated)
- [ ] LLM-native pipeline (tested)
- [ ] Updated ingestion dispatcher

**Documentation:**
- [ ] Browser automation deployment guide
- [ ] LLM v2.0 prompt documentation
- [ ] Week 2 metrics report
- [ ] Week 3 execution plan

**Operational:**
- [ ] Top 50 stores on browser automation
- [ ] 80 stores on LLM-native extraction
- [ ] Monitoring dashboards live
- [ ] Cost tracking active

---

## Go-Live Checklist (Friday EOD)

**Before deploying browser automation:**
- [ ] Pilot test on 10 stores passed
- [ ] Performance acceptable
- [ ] Error handling verified
- [ ] Fallback mechanism tested
- [ ] Monitoring ready

**Before deploying LLM v2.0:**
- [ ] 100-store test completed
- [ ] Confidence scores validated
- [ ] Cost per extraction calculated
- [ ] Quality checks passed
- [ ] Error handling verified

**Before final metrics report:**
- [ ] 24 hours of production data collected
- [ ] No critical errors
- [ ] Success rate improvement confirmed
- [ ] Cost tracking validated

---

## Week 2 Timeline Summary

```
Monday:    Playwright setup + LLM prompt v2.0 engineering
Tuesday:   Pilot testing + LLM calibration testing
Wednesday: Performance optimization + Integration
Thursday:  Production prep + Staging validation
Friday:    Deploy both pipelines + Collect metrics

By EOW:
  ✅ Browser automation: Live for top 50 stores
  ✅ LLM-native: Live for 10% of stores (80 stores)
  ✅ +100-200 new products extracted
  ✅ Success rate: 6% → 15%
```

---

**Status:** 🚀 **WEEK 2 EXECUTION BEGINS NOW**

**Next Immediate Action:** Start Playwright installation and LLM prompt engineering this Monday morning.

