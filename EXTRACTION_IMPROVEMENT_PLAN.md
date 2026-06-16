# Extraction Improvement Plan - Focus on Successful Patterns

**Created:** 2026-06-13  
**Status:** Ready for implementation

## Database Analysis Summary

### Current Success Metrics
- **Total Stores:** 837 active
- **Successfully Extracting:** 821 stores (98%) have at least 1 extraction
- **Total Extractions:** 11,467 products across all stores
- **Parser Breakdown:**
  - HTML: 762 stores → 8,593 extractions (75%)
  - Shopify: 16 stores → 2,075 extractions (18%)
  - LLM: 43 stores → 799 extractions (7%)

### Top Performing Stores

**Tier 1 (>70k extractions):**
1. **foundry.com** (HTML) - 90,024 total
   - 23 runs, 47% extraction efficiency
   - Consistent extraction across many pages
   
2. **neighbourhoodcoffee.co.uk** (HTML) - 78,780 total
   - 10 successful runs (2,665 total runs)
   - 61% extraction efficiency
   - 101 source pages

**Tier 2 (>10k extractions):**
3. **bradyscoffee.ie** (HTML) - 12,430 total
   - 7 runs, 59% extraction efficiency
   - High consistency

**Tier 3 (1-10k range):**
- nudeespresso.com, hotnumberscoffee.co.uk, 17grams.co.uk, volcanocoffeeworks.com
- Extraction efficiency ranges from 0.4% to 6%

## Key Insights

### Pattern 1: Single-Page Sites Extract Best
✅ **High Success:**
- shop.squaremilecoffee.com: 1 page → 793 extractions (58% efficiency)
- www.hasbean.co.uk: 1 page → 705 extractions (70% efficiency)
- ozonecoffee.co.uk: 1 page → 705 extractions (67% efficiency)
- origincoffee.co.uk: 1 page → 703 extractions (77% efficiency)

**Insight:** Sites with a single product listing page have much higher extraction success. These are likely standardized WooCommerce/Shopify stores with a fixed product list structure.

### Pattern 2: Multi-Page Sites Need Better Rules
⚠️ **Lower Success:**
- neighbourhoodcoffee.co.uk: 101 pages but 61% efficiency (good)
- hotnumberscoffee.co.uk: 177 pages but only 6% efficiency (bad)
- 17grams.co.uk: 46 pages but only 0.4% efficiency (JavaScript issue)

**Insight:** Multi-page sites need either:
1. Better pagination handling
2. Customized extraction rules per site structure
3. JavaScript rendering (for 17grams)

### Pattern 3: Successful Extractors Share Common Traits
**foundry.com analysis:**
- 190,872 pages fetched → 90,024 extractions = 47% efficiency
- 23 distinct ingestion runs
- Suggests: WooCommerce site with consistent product structure

**neighbourhoodcoffee.co.uk analysis:**
- 128,775 pages fetched → 78,780 extractions = 61% efficiency
- 10 successful out of 2,665 runs = 0.4% run success
- But when it works, it works consistently

## Improvement Strategy

### Phase 1: Analyze & Document Successful Patterns (Week 1)

**Task 1.1:** Extract HTML samples from top performers
```
- foundry.com product page
- neighbourhoodcoffee.co.uk product pages
- bradyscoffee.ie product page
- shop.squaremilecoffee.com product page
```

**Task 1.2:** Identify common HTML patterns
- Product name selectors
- Price selectors
- Description selectors
- Image selectors
- Attribute selectors (roast level, origin, etc.)

**Task 1.3:** Document site-specific rules
- Create extraction rules file for each successful site
- Map CSS selectors used by schema.org/HTML parsers

### Phase 2: Improve Failing High-Volume Sites (Week 2)

**Priority 1: 17grams.co.uk (0.4% efficiency)**
- Issue: JavaScript rendering required (omnisend_product)
- Solution: Test with Playwright browser extraction
- Expected Impact: Could increase from 920 → 5,000+ extractions
- Action: Run test_17grams_extraction.py with Playwright

**Priority 2: hotnumberscoffee.co.uk (6% efficiency)**
- Issue: 177 source pages, complex structure
- Solution: Improve HTML parsing rules or identify missing source pages
- Expected Impact: Could increase from 1,947 → 10,000+ extractions
- Action: Analyze pagination, improve selectors

**Priority 3: nudeespresso.com (0 extractions despite 2,571 runs!)**
- Issue: Critical - should be extracting but isn't
- Solution: Investigate what changed, fix extraction chain
- Expected Impact: Could enable 10,000+ extractions
- Action: Check logs, test extraction on sample page

### Phase 3: Quick Wins - Replicate Single-Page Success (Week 3)

**Goal:** Find other single-page sites and apply working rules

**Strategy:**
1. Query for stores with 1-2 source pages
2. Test extraction on them
3. If failing, apply rules from successful single-page sites
4. Should have 50%+ extraction rate if done right

**Expected Impact:** +5,000-10,000 extractions from low-hanging fruit

### Phase 4: Build Generic HTML Parser Improvements (Week 4)

**Goal:** Improve generic HTML rules parser to handle more site patterns

**Action Items:**
1. Add more common CSS selectors for product names
2. Improve price extraction (handle different currency formats)
3. Add support for variant extraction from tables/lists
4. Add schema.org fallback within HTML pages

**Expected Impact:** +10-20% extraction rate across all HTML stores

## Implementation Roadmap

### Week 1: Foundation
- [ ] Extract HTML samples from top performers
- [ ] Document common selectors and patterns
- [ ] Create extraction rules documentation
- [ ] Set up testing framework for rules

### Week 2: High-Impact Fixes
- [ ] Test Playwright on 17grams (should fix 0.4% → 30%+)
- [ ] Improve hotnumberscoffee parsing rules
- [ ] Fix nudeespresso extraction (investigate failure)
- [ ] Document fixes and measure impact

### Week 3: Quick Wins
- [ ] Identify all single-page sites
- [ ] Apply working rules to similar sites
- [ ] Measure extraction rate improvements
- [ ] Deploy rules to production

### Week 4: Polish & Optimize
- [ ] Generic parser improvements
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Documentation update

## Success Metrics

**Target Improvements:**
- 17grams.co.uk: 920 → 5,000+ extractions (5x)
- hotnumberscoffee: 1,947 → 10,000+ extractions (5x)
- nudeespresso: 0 → 5,000+ extractions
- Overall extraction rate: 11,467 → 30,000+ extractions (2.6x)

**Quality Metrics:**
- Extraction confidence: Maintain >0.5 average
- False positive rate: <5% (bad product extractions)
- Coverage: 95%+ of sites with >100 extractions

## Technical Debt Addressed

1. ✅ Playwright installed - enables browser extraction for JS sites
2. ✅ BrowserPool fixed - browser contexts work properly
3. ⏳ HTML rules parser - needs improvement based on working patterns
4. ⏳ Error logging - need better diagnostics for why sites fail

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Overfit rules to successful sites | Breaking other sites | Test rules on diverse sites |
| JavaScript content requiring headless=false | False negatives on Playwright | Implement headless detection evasion |
| Source page discovery incomplete | Missing many products | Implement sitemap crawler |
| API credit exhaustion on LLM sites | Can't improve LLM extraction | Not blocking - focus on HTML/Shopify |

## Next Steps (Immediate)

1. **Today:** Run Playwright test on 17grams to verify it improves extraction
2. **Tomorrow:** Start HTML sample collection and pattern documentation
3. **This week:** Complete Phase 1 analysis
4. **Next week:** Begin Phase 2 high-impact fixes

---

**Estimated Time to 30k+ extractions:** 4 weeks  
**Confidence:** HIGH (based on clear patterns in existing data)
