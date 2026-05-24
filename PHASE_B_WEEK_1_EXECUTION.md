# Phase B Week 1: Schema.org Testing & Validation

**Phase A Status:** ✅ Complete - 9+ products live  
**Phase B Week 1:** 🟡 Starting now  
**Goal:** Validate schema.org pipeline before soft launch

---

## Week 1 Overview

### Timeline
- **Days 1-2:** Identify pilot stores with schema.org markup
- **Days 3-4:** Run isolated extraction tests  
- **Day 5:** Go/No-Go decision for soft launch

### Success Criteria
```
To proceed to Phase B Week 2 (Soft Launch):
  ✅ Schema.org avg confidence ≥ 0.65
  ✅ Error rate < 5%
  ✅ Extraction time < 300s per store
  ✅ Team confidence in rollout: HIGH
```

---

## Step 1: Identify Pilot Stores (Days 1-2)

### Current Database Analysis

From earlier query, we have 845 stores total:
- **HTML stores:** ~500-600 (currently active)
- **Shopify stores:** ~200-250 (direct API)
- **Unknown/Other:** ~50-100

### Schema.org Candidate Query

```sql
-- Find stores with strong HTML extraction (good candidates for schema.org test)
SELECT 
  s.domain, 
  s.parser_strategy,
  COUNT(bl.id) as current_products,
  ROUND(AVG(CAST(bl.raw_extraction -> 'confidence' AS NUMERIC)), 2) as avg_confidence
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.active_flag = true
  AND s.parser_strategy = 'html'
  AND COUNT(bl.id) > 50  -- Already extracting well with HTML
GROUP BY s.id, s.domain, s.parser_strategy
ORDER BY avg_confidence DESC
LIMIT 20;
```

### Manual Pilot Selection Criteria

Look for stores that:
1. ✅ Currently extracting 100+ products (HTML working)
2. ✅ Have high confidence scores (≥0.60)
3. ✅ Modern platforms (likely to have schema.org)
4. ✅ Mix of platform types (Shopify, custom, WooCommerce)

### Candidate Example Stores

Based on earlier data, good candidates:
- kissthehippo.com (226 HTML products - strong extraction)
- www.ravecoffee.co.uk (122 HTML products)
- ozonecoffee.co.uk (120 HTML products)
- www.hasbean.co.uk (120 HTML products)
- origincoffee.co.uk (102 HTML products)

---

## Step 2: Verify Schema.org Markup (Days 2-3)

### Test Script: Check Markup Presence

```python
#!/usr/bin/env python3
"""Verify schema.org JSON-LD on candidate stores"""

import urllib.request
import re

def check_schema_org(domain):
    """Check if domain has JSON-LD Product schema"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # Try shop page first, then product page
        urls = [
            f"https://{domain}/shop/",
            f"https://{domain}/products/",
            f"https://{domain}/",
        ]
        
        for url in urls:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # Check for JSON-LD
            has_json_ld = bool(re.search(r'"@type"\s*:\s*"Product"', html))
            has_itemscope = bool(re.search(r'itemscope.*itemtype.*schema\.org.*Product', html))
            
            if has_json_ld or has_itemscope:
                return True, url
        
        return False, None
    except Exception as e:
        return False, str(e)

# Test pilot stores
pilots = [
    "kissthehippo.com",
    "www.ravecoffee.co.uk",
    "ozonecoffee.co.uk",
]

for domain in pilots:
    has_markup, result = check_schema_org(domain)
    status = "✅ YES" if has_markup else "❌ NO"
    print(f"{domain}: {status}")
    if has_markup:
        print(f"  Found at: {result}")
```

### Expected Output
```
kissthehippo.com: ✅ YES
  Found at: https://kissthehippo.com/shop/
www.ravecoffee.co.uk: ✅ YES
  Found at: https://www.ravecoffee.co.uk/products/
ozonecoffee.co.uk: ❌ NO (may need fallback)
```

---

## Step 3: Run Isolated Extraction Test (Days 3-4)

### Test Methodology

```bash
# For each pilot store, run side-by-side comparison:

# 1. Current extraction (HTML rules)
docker exec coffee_api python3 << 'PYTHON'
# Extract current products and confidence scores
# from bean_listings for the pilot store
PYTHON

# 2. Test schema.org extraction in isolation
docker exec coffee_api python3 << 'PYTHON'
import asyncio
from app.services.extraction.schema_org_parser import SchemaOrgParser
import urllib.request

async def test_schema_org(domain):
    parser = SchemaOrgParser()
    
    # Fetch sample page
    req = urllib.request.Request(f"https://{domain}/shop/")
    html_bytes = urllib.request.urlopen(req).read()
    
    # Extract
    result = parser.extract(html_bytes, f"https://{domain}/shop/")
    
    # Report
    print(f"{domain}:")
    print(f"  Status: {result.validation_status}")
    print(f"  Confidence: {result.payload.confidence}")
    print(f"  Products found: {len(result.payload.price_variants)}")
    
    return result

for domain in pilots:
    asyncio.run(test_schema_org(domain))
PYTHON
```

### Comparison Matrix (Expected)

| Store | Strategy | Current Confidence | Schema.org Test | Winner |
|-------|----------|------------------|-----------------|--------|
| kissthehippo.com | HTML | 0.60 | 0.75 | Schema.org ✅ |
| ravecoffee.co.uk | HTML | 0.62 | 0.72 | Schema.org ✅ |
| ozonecoffee.co.uk | HTML | 0.58 | 0.40* | HTML ✓ |

*If schema.org fails, stay with HTML or add fallback

---

## Step 4: Quality Validation (Days 4-5)

### Success Threshold Check

Run these queries on test results:

```sql
-- For HTML current (baseline)
SELECT 
  COUNT(*) as records,
  ROUND(AVG(confidence), 2) as avg_confidence,
  MIN(confidence) as min_conf,
  MAX(confidence) as max_conf
FROM bean_listings
WHERE store_id = [TEST_STORE_ID];

-- Criteria:
-- ✅ Confidence ≥ 0.65 (higher than HTML's 0.60)
-- ✅ Error rate < 5%
-- ✅ Completeness (5+ of 7 fields)
```

### Completeness Check (7-Field Scoring)

Fields to verify in extracted products:
1. ✅ coffee_name
2. ✅ price_gbp (must be non-zero)
3. ✅ weight_g (in grams)
4. ✅ origin_country
5. ✅ process (washed, natural, honey, etc.)
6. ✅ roast_level (light, medium, dark, etc.)
7. ✅ varietal (or brew_suitability)

Score calculation:
```
- 5-7 fields: High confidence (0.70-0.85) ✅
- 3-4 fields: Medium confidence (0.50-0.69) ⚠️
- 1-2 fields: Low confidence (0.25-0.49) ❌
```

---

## Step 5: Go/No-Go Decision (Day 5)

### Decision Gate Criteria

**✅ GO (Proceed to Soft Launch)** if:
- Schema.org avg confidence ≥ 0.65
- Error rate < 5%
- Completeness ≥ 5/7 fields on average
- 3+ pilot stores pass threshold

**🟡 AMBER (Iterate)** if:
- Average confidence 0.55-0.64
- Some stores working, some not
- Needs selector/prompt tuning
- Decision: Tune and retest 2 more days

**❌ RED (Pause)** if:
- Average confidence < 0.55
- Error rate > 10%
- Most pilots failing
- Decision: Debug, file issues, pause rollout

### Decision Document Template

```markdown
# Schema.org Pilot Test Results

**Date:** [DATE]  
**Pilot Stores Tested:** [N stores]  
**Test Duration:** [X hours]

## Results Summary

| Store | HTML Baseline | Schema.org Test | Winner | Notes |
|-------|---------------|-----------------|--------|-------|
| Store1 | 0.60 | 0.72 | Schema.org | ✅ |
| Store2 | 0.58 | 0.68 | Schema.org | ✅ |
| Store3 | 0.62 | 0.55 | HTML | Fallback needed |

## Metrics

- Average schema.org confidence: 0.68 (target: ≥0.65) ✅
- Error rate: 2% (target: <5%) ✅
- Extraction rate: 85% (target: ≥80%) ✅
- Field completeness: 5.8/7 (target: ≥5) ✅

## Decision

**✅ APPROVED FOR SOFT LAUNCH**

Recommended next steps:
1. Week 2: Enable on 5-10 pilot stores
2. Monitor daily: extraction rate, confidence, errors
3. Week 3: Expand to 50 more stores if metrics hold
```

---

## Running Phase B Week 1 Tests (TODAY)

### Quick Start Commands

```bash
# 1. Identify candidates
docker exec coffee_postgres psql -U coffee -d coffee_platform << 'SQL'
SELECT domain, COUNT(bl.id) as products
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.active_flag = true AND s.parser_strategy = 'html'
GROUP BY s.id, s.domain
HAVING COUNT(bl.id) > 50
ORDER BY COUNT(bl.id) DESC
LIMIT 5;
SQL

# 2. Test schema.org on first candidate (kissthehippo.com example)
docker exec coffee_api python3 << 'PYTHON'
import asyncio
import urllib.request
from app.services.extraction.schema_org_parser import SchemaOrgParser

async def test():
    domain = "kissthehippo.com"
    parser = SchemaOrgParser()
    
    try:
        # Fetch shop page
        req = urllib.request.Request(f"https://{domain}/shop/")
        html_bytes = urllib.request.urlopen(req, timeout=10).read()
        
        # Extract
        result = parser.extract(html_bytes, f"https://{domain}/shop/")
        
        print(f"Schema.org Test: {domain}")
        print(f"  Status: {result.validation_status}")
        print(f"  Confidence: {result.payload.confidence:.2f}")
        print(f"  ✅ Test successful" if result.payload.confidence > 0.4 else "  ❌ Low confidence")
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
PYTHON
```

---

## Deliverables for Phase B Week 1

By end of week, document:

1. **Pilot Selection Report**
   - 3-5 stores selected
   - Reason for each
   - Baseline HTML metrics

2. **Schema.org Test Results**
   - Confidence scores
   - Error rates
   - Completeness analysis

3. **Decision Document**
   - Go/No-Go recommendation
   - Metrics summary
   - Next steps

4. **Implementation Plan** (if GO)
   - Week 2 soft launch stores
   - Monitoring dashboard
   - Success metrics

---

## Timeline

```
Today (Day 1):
  └─ Run identification queries
  └─ Select 3-5 pilot stores
  
Tomorrow (Day 2):
  └─ Check schema.org markup presence
  └─ Document findings
  
Days 3-4:
  └─ Run extraction tests
  └─ Collect metrics
  
Day 5:
  └─ Analyze results
  └─ Make Go/No-Go decision
  └─ Document decision
```

---

## Success Indicators

✅ **You'll know Week 1 is successful when:**
- 3-5 pilot stores identified with schema.org markup
- Schema.org avg confidence ≥ 0.65 (better than HTML)
- Error rate < 5%
- Team confidence: HIGH
- Decision: **GO for Week 2 Soft Launch**

---

## Estimated Effort

- **Days 1-2 (Setup):** 2-3 hours
- **Days 3-4 (Testing):** 3-4 hours  
- **Day 5 (Analysis):** 1-2 hours
- **Total Week 1:** 6-9 hours

---

**Next Milestone:** Week 2 Soft Launch (5-10% of sources)  
**Ready:** All documentation and code in place  
**Status:** 🟢 READY TO START
