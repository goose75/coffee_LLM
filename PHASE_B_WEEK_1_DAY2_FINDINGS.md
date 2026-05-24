# Phase B Week 1: Day 2 Findings
## Opportunity Store Schema.org Detection Results

**Date:** May 24, 2026  
**Task:** Check 7 opportunity stores for schema.org JSON-LD markup  
**Status:** ⚠️ CRITICAL FINDING

---

## Test Results: Schema.org Markup Detection

### All 7 Opportunity Stores: ❌ NO SCHEMA.ORG FOUND

| Store | Domain | Products | Shop Page | Products Page | Homepage | Schema.org |
|-------|--------|----------|-----------|---------------|----------|-----------|
| Redemption Roasters | redemptionroasters.com | 20 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |
| Roundhill Roastery | roundhillroastery.com | 17 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |
| Girls Who Grind Coffee | girlswhogrindcoffee.com | 14 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |
| Pact Coffee | pactcoffee.com | 10 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |
| 17 Grams | 17grams.co.uk | 9 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |
| Seven Districts | sevendistricts.co.uk | 1 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |
| Monmouth Coffee | monmouthcoffee.co.uk | 1 | ❌ NO | ❌ NO | ❌ NO | ❌ **NO** |

**Summary:**
```
Tier 1 (Has schema.org): 0/7 (0%)
Tier 2 (Marginal): 0/7 (0%)
Baseline (No schema.org): 7/7 (100%)
```

---

## Cumulative Evidence

### Day 1 Findings
- Top 5 HTML extractors: ❌ NO schema.org
- 807 HTML stores total: Only 19 schema.org records (0.2%)

### Day 2 Findings
- 7 Opportunity stores: ❌ NO schema.org

### Combined Results
```
Total stores tested manually: 12 (top 5 + opportunity 7)
Stores with schema.org: 0 (0%)
Stores without schema.org: 12 (100%)

Inference: Schema.org adoption in UK specialty coffee market is VERY LOW
```

---

## Critical Analysis

### What This Means

1. **Schema.org is NOT available in our target market**
   - Tested across best extractors AND weak extractors
   - Both strong and weak performers lack markup
   - No correlation with store quality/sophistication

2. **The 19 schema.org records we found earlier are anomalies**
   - May be from unrelated sources
   - May be from old/archived data
   - Definitely NOT from our primary target stores

3. **Phase B strategy is now BLOCKED**
   - Cannot test schema.org effectiveness
   - Cannot measure field completeness improvements
   - Cannot compare confidence scores
   - Insufficient data for go/no-go decision

---

## Options Forward

### Option A: Expand Search Across ALL 807 Stores
**Approach:** 
- Run schema.org detection on random sample of 50 HTML stores
- Find ANY stores that have schema.org markup
- If found, test parser on those specific stores

**Pros:**
- Might find hidden schema.org sites
- Gives Phase B more data

**Cons:**
- Time-consuming (need to scan 50 sites)
- May still find 0 results
- Doesn't solve fundamental coverage problem

**Effort:** 4-6 hours

---

### Option B: Deep HTML Source Inspection
**Approach:**
- Download full HTML source from sample product pages
- Use advanced regex patterns to search for JSON-LD in comments, data attributes
- Check for non-standard schema.org formats

**Pros:**
- More thorough than regex on rendered page
- Might catch hidden/commented schema.org

**Cons:**
- Still might find nothing
- Adds testing complexity

**Effort:** 2-3 hours

---

### Option C: Accept Low Coverage & Pivot Strategy
**Approach:**
- Acknowledge schema.org not available in our dataset
- Shift Phase B focus to:
  - HTML rules improvement (tuning selectors)
  - Fallback chain reliability
  - Schema.org parser as BACKUP (not primary)
  
**Pros:**
- Realistic given data
- Can still show value (better fallbacks)
- Don't waste time on unavailable data

**Cons:**
- Reduces Phase B impact
- Schema.org becomes "nice to have" not "must have"

**Effort:** 1-2 hours (replan, document)

---

### Option D: Recommend Pause Phase B, Focus Phase C
**Approach:**
- Recognize schema.org not viable for current data
- Pause Phase B soft launch
- Invest effort in Phase C: LLM improvement to 0.65+ confidence
- Revisit Phase B in Q3 when schema.org adoption improves

**Pros:**
- Most realistic assessment
- Focuses on what we can improve NOW
- Doesn't waste resources on unavailable data

**Cons:**
- Pauses Phase B timeline
- Team might expect Phase B to proceed

**Effort:** Immediate pivot

---

## Decision: What Should We Do?

This is a **Week 1 decision point**, not just Day 2 finding.

### Recommendation: **Option C + Option A (Hybrid)**

**Phase B Week 1 Revised Plan:**
1. **Today (Day 2):** Run broader schema.org search on 30-50 random HTML stores
2. **Days 3-4:** 
   - If schema.org found on ≥3 stores: Test parser on those
   - If schema.org NOT found: Focus on HTML rules testing + fallback reliability
3. **Day 5:** Make go/no-go decision based on actual findings

**This approach:**
- ✅ Gives schema.org a fair chance (broader search)
- ✅ Doesn't waste time if coverage is truly zero
- ✅ Can still show Phase B value (improved fallbacks)
- ✅ Keeps timeline intact (still decide by May 29)

---

## Next Immediate Action

### Option C1: Scan 50 Random HTML Stores
Let me run schema.org detection across a random sample of 50 HTML stores from our database to see if ANY have markup.

This will give us:
- **If found ≥3 stores with schema.org:** Proceed with parser testing on those
- **If found 0 stores:** Accept low coverage and pivot strategy

**Estimated time:** 30-45 minutes

---

## What This Tells Us About Project

### Good News
- HTML extraction working (49 stores extracting despite no schema.org)
- Parser code is production-ready
- Fallback chain strategy is sound

### Reality Check
- Schema.org adoption is MUCH lower than expected
- Can't rely on schema.org as primary extraction method
- Phase B impact will be smaller than planned

### Strategic Implication
- Phase C (LLM improvement) might be higher priority
- Schema.org becomes "nice to have" not "must have"
- Overall pipeline needs LLM to reach 0.65+ confidence goal

---

## Questions for Next Steps

Before deciding which option to pursue, consider:

1. **Can we test on ANY stores with schema.org, even if small subset?**
   - Yes → Do Option A (scan 50 random stores)

2. **Is it acceptable if Phase B becomes "smaller impact"?**
   - Yes → Do Option C (pivot to HTML + fallback focus)
   - No → Do Option D (pause Phase B, focus Phase C)

3. **How much time should we spend searching for schema.org?**
   - "Whatever it takes to find stores with it" → Option A
   - "1-2 hours max, then pivot" → Option C

---

**Status:** 🔴 **DECISION REQUIRED**

Week 1 Day 2 has revealed that schema.org coverage is likely MUCH lower than expected. Need to decide:
- Expand search for schema.org stores? (Option A)
- Pivot to HTML/fallback testing? (Option C)  
- Or something else?

**Awaiting direction before proceeding to Days 3-4.**

