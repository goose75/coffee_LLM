# Phase B Week 1: Pivot Strategy (Option C)
## When Schema.org Coverage is Too Low

**Date:** May 24, 2026  
**Decision Point:** Day 2 Evening  
**Data:** Tested 47 stores (7 opportunity + 40 random) = 0 active stores with schema.org  
**Status:** 🔴 Schema.org NOT VIABLE for Phase B

---

## Evidence: Schema.org Coverage is Near Zero

### Combined Testing Results
```
Opportunity stores (weak HTML extractors):     0/7 with schema.org (0%)
Random sample (diverse HTML stores):           0/40 with schema.org (0%)
                                               ───────────────────────
Total tested:                                  0/47 (0%)

Parked/expired domains found:                  1 (false positive)
Active coffee stores with schema.org:          0
```

### Confidence Level: HIGH
- **Sample size:** 47 stores (5.8% of 807 HTML stores)
- **Variety:** Mix of top performers, weak extractors, random sample
- **Geographic coverage:** UK, Ireland, US domains
- **Conclusion:** Schema.org is NOT adopted in our target market

---

## Decision: Implement Pivot Strategy (Option C)

**Original Phase B Goal:** Activate schema.org extraction for 5-10% of sources (50+ stores)

**Reality Check:** Schema.org not available in target market

**New Phase B Goal:** Improve HTML extraction reliability and fallback chain

---

## Revised Phase B Week 1: Days 3-5

Instead of testing schema.org (unavailable), pivot to:

### Days 3-4: HTML Rules Testing & Improvement

#### Task 1: Analyze Current HTML Extraction Failures

**What we know:**
- 807 HTML stores total
- Only 49 extracting products (6% success)
- 758 stores extracting nothing

**What to investigate:**
```sql
-- Find stores with pages discovered but no products extracted
SELECT 
  s.domain,
  COUNT(sp.id) as pages_found,
  COUNT(bl.id) as products_extracted
FROM stores s
LEFT JOIN source_pages sp ON s.id = sp.store_id
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.parser_strategy = 'html'
GROUP BY s.id, s.domain
HAVING COUNT(sp.id) > 0 AND COUNT(bl.id) = 0
LIMIT 10;
```

**For these failing stores:**
1. Manually inspect page structure
2. Identify what selectors are missing
3. Test parser on sample pages
4. Document selector/rule gaps

#### Task 2: Test Parser Fallback Chain

**Current chain:** schema.org → HTML rules → LLM

**Since schema.org not available:**
Test: **HTML rules → LLM fallback**

**Measurement:**
- When do HTML rules succeed?
- When do they fail and LLM succeeds?
- What's the confidence delta?
- What percentage of pages need LLM fallback?

#### Task 3: Measure Field Completeness on Working Stores

**Using our 7 opportunity stores + 40 random stores:**
1. For each store with ANY extraction, measure:
   - Coffee name: present/absent
   - Price: present/absent
   - Weight: present/absent
   - Origin: present/absent
   - Process: present/absent
   - Roast: present/absent
   - Varietal: present/absent

2. Calculate average completeness score
3. Identify which fields are consistently missed
4. Determine if targeted improvements would help

### Day 5: Decision & Documentation

**Go/No-Go Criteria (Revised for HTML focus):**

#### ✅ GO (Proceed with Modified Phase B)
- [ ] Identified ≥5 specific selector gaps in HTML extraction
- [ ] HTML rules → LLM fallback chain tested on ≥20 pages
- [ ] Average field completeness ≥ 4/7 fields
- [ ] Fallback chain works reliably (no crashes)
- [ ] Team confidence in HTML improvement roadmap: HIGH

**Next:** Week 2 = HTML selector improvements + fallback optimization

#### 🟡 AMBER (Need More Work)
- [ ] Selector gaps unclear
- [ ] Fallback chain inconsistent
- [ ] Field completeness too low (< 3/7)

**Next:** Continue analysis, revisit Week 1 or pause for improvement

#### ❌ RED (Pause Phase B)
- [ ] Can't identify improvement path
- [ ] Fallback chain broken or too slow
- [ ] LLM cost/benefit not justified

**Next:** Pause Phase B, focus on Phase C (LLM-native pipeline)

---

## Detailed Days 3-4 Plan

### Day 3: HTML Extraction Analysis (2-3 hours)

**Step 1: Identify Failing Store (30 min)**
```bash
# Find 3-5 stores with pages discovered but 0 products extracted
# Example: Store has 5 pages in source_pages but 0 in bean_listings
```

**Step 2: Manual HTML Inspection (1 hour)**
- Fetch product page from failing store
- Inspect HTML structure in browser
- Identify product containers (divs, spans, classes)
- Document actual selectors present vs ones we're using

**Step 3: Root Cause Analysis (30 min)**
- Is the page structure completely different?
- Are products hidden in JavaScript?
- Is the page blocked/requires JavaScript?
- Document findings

**Expected Output:**
```
Store: example.com
Pages found: 5
Products extracted: 0

Root cause: Page uses custom JavaScript framework (Vue/React)
HTML selectors present: .product-item, .price, .title
Current selectors working: None (site is SPA)

Recommendation: 
  A) Add site-specific selectors
  B) Mark as "requires JavaScript" (can't extract)
  C) Move to LLM pipeline only
```

### Day 4: Fallback Chain Testing (2-3 hours)

**Step 1: Select Test Pages (30 min)**
- 10 pages from failing stores
- 10 pages from working stores (baseline)
- 5 pages from random new stores

**Step 2: Run Extraction Chain (1 hour)**
```python
# For each page:
# 1. Try HTML rules extraction
# 2. If confidence < 0.4, try LLM
# 3. Record: HTML success/fail + confidence
# 4. Record: LLM used? Confidence gained?
```

**Step 3: Measure Fallback Effectiveness (30 min)**
```
Metric 1: When does HTML fail?
├── Answer: Low-confidence pages, unknown formats, JS-heavy sites
└── Frequency: X% of pages

Metric 2: Does LLM fix those failures?
├── Answer: Yes/No/Partial
└── Confidence improvement: 0.0 → 0.X average

Metric 3: Fallback speed?
├── Answer: HTML (50ms) + LLM (2s) = 2.05s total per page
└── Is this acceptable? (target: < 5s per page)
```

**Expected Output:**
```
HTML Rules Success Rate: 60% of pages
LLM Fallback Used: 40% of pages
LLM Improves Confidence: +0.15 average
Fallback Chain Reliability: 100% (no crashes)

Conclusion: Fallback works well. LLM cost justified for 40% of traffic.
```

---

## Revised Success Definition for Phase B

**Original:** Schema.org extraction reaching 0.65+ confidence on 100+ stores

**Revised:** HTML extraction improved with reliable LLM fallback

**Metrics:**
1. ✅ HTML extraction field completeness: ≥ 4/7 fields average
2. ✅ LLM fallback reduces errors by ≥ 20%
3. ✅ Overall pipeline reliability: > 95% success rate
4. ✅ Fallback chain executes in < 5s per page

**Outcome:**
- If metrics met: Week 2 = optimize and rollout
- If not met: Pause Phase B, focus Phase C (LLM-native)

---

## Why This Pivot Makes Sense

### Reality of Schema.org
- Not adopted in specialty coffee market (0% coverage found)
- Not a viable extraction method for our dataset
- Would be "nice to have" in Q3 when adoption improves
- Not worth 2 weeks of Phase B effort right now

### Value of HTML Improvements
- 807 HTML stores are our largest segment
- Even small improvements affect huge volume
- Fallback chain already exists (just needs optimization)
- Low cost, high impact

### Strategic Thinking
- Phase A fixed multi-product extraction (HTML)
- Phase B pivots to HTML optimization + fallback
- Phase C (LLM-native) addresses long-term 0.65+ confidence goal
- This is REALISTIC and VALUABLE

---

## Implementation: Days 3-5 Detailed Tasks

### Day 3 Morning: Store Analysis Setup
- [ ] Query database for 5 stores with pages but 0 products
- [ ] Download their HTML pages
- [ ] Inspect structure (what divs/classes actually exist?)

### Day 3 Afternoon: Root Cause Documentation
- [ ] Document why each store is failing
- [ ] Categorize failures (SPA, custom format, JS-heavy, etc.)
- [ ] Estimate effort to fix each

### Day 4 Morning: Fallback Chain Testing
- [ ] Select 25 test pages (mix of success/fail/random)
- [ ] Create test harness to run HTML → LLM chain
- [ ] Measure confidence, speed, reliability

### Day 4 Afternoon: Analysis & Metrics
- [ ] Calculate fallback effectiveness
- [ ] Measure field completeness
- [ ] Document where LLM is winning vs HTML

### Day 5: Decision & Documentation
- [ ] Write PHASE_B_WEEK_1_DECISION.md
- [ ] Go/No-Go recommendation (based on revised criteria)
- [ ] If GO: Outline Week 2 HTML improvement plan
- [ ] If RED: Document why and recommend Phase C focus

---

## Risks of This Pivot

### Low Risk
- ✅ No code changes (testing only)
- ✅ No risk to production
- ✅ Fallback chain already exists
- ✅ Realistic expectations

### Medium Risk
- ⚠️ Might find HTML extraction unfixable on many sites (JS-heavy)
- ⚠️ LLM cost might be too high for margin
- ⚠️ Performance might not meet < 5s target

### High Risk
- 🔴 If most failures are JS-related, can't fix with selectors
- 🔴 If LLM doesn't improve results, fallback is waste
- 🔴 Might conclude Phase B is not viable at all

### Mitigation
- Test small sample first (Days 3-4)
- If problems found, escalate for decision before Day 5
- Have Phase C alternative ready

---

## Expected Outcomes

### Scenario 1: HTML Improvements Clear (60% likely)
```
Week 1 Result: ✅ GO (modified)
└─ Found 5+ specific selector improvements
└─ Fallback chain effective
└─ Clear roadmap

Week 2: HTML Selector Enhancement
└─ Add site-specific selectors
└─ Test on top 20 failing stores
└─ Measure improvement

Week 3+: Rollout selective improvements
└─ Deploy working selectors
└─ Monitor extraction rates
└─ Track field completeness
```

### Scenario 2: Issues Found But Fixable (20% likely)
```
Week 1 Result: 🟡 AMBER
└─ Found issues in fallback chain
└─ Performance needs optimization
└─ Some failures are JS-related

Week 1.5: Debug & Optimize
└─ Fix fallback issues
└─ Improve LLM prompt for coffee extraction
└─ Batch test again

Week 2: GO Decision
└─ Proceed with improvements if fixed
└─ Or pivot to Phase C if needed
```

### Scenario 3: Fundamental Problems (20% likely)
```
Week 1 Result: ❌ RED
└─ Most failures are JS-heavy (can't extract with selectors)
└─ LLM too expensive for improvement gained
└─ Fallback chain has issues

Week 2: PAUSE PHASE B
└─ Focus on Phase C (LLM-native pipeline)
└─ Build self-improving LLM system
└─ Abandon selector-based extraction
```

---

## Key Insight

**This pivot is actually BETTER for the business:**

- ❌ Phase B Schema.org: 0% coverage, low value
- ✅ Phase B HTML: 96% of sources, high value
- 🚀 Phase C LLM: Long-term 0.65+ confidence goal

By pivoting to HTML, we're not delaying the goal—we're taking the path that actually works.

---

## Decision Question for User

**Before Days 3-4, confirm:**

1. ✅ **Should we proceed with this pivot?**
   - YES: Continue with HTML analysis on Days 3-4
   - NO: What alternative would you prefer?

2. ✅ **Is the revised success criteria acceptable?**
   - (HTML field completeness ≥ 4/7 + fallback reliable)
   - Or would you like different metrics?

3. ✅ **Any stores you want us to focus on specifically?**
   - We can deep-dive on your preferred failing stores

---

## Summary

**Phase B Week 1 Status (End of Day 2):**

- ❌ Schema.org strategy: **BLOCKED** (0% coverage)
- ✅ HTML pivot strategy: **READY** (applies to 96% of sources)
- 🟡 Days 3-5 approach: **REVISED** (HTML + fallback testing)
- 📊 Decision gate: **May 29 (still on track)**

**Next:** Confirm pivot, proceed with Days 3-4 HTML analysis

---

**Document Version:** 1.0  
**Status:** Ready for execution  
**Date:** May 24, 2026 (End of Day 2)

