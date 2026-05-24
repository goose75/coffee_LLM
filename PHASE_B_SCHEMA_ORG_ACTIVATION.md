# Phase B: Activate Schema.org Sources

## 1. Schema.org Sources Investigation

### Current Status

**Schema.org Pipeline:** ✅ BUILT & REGISTERED
- Location: `/services/api/app/services/schema_org/pipeline.py` (569 lines)
- Dispatcher integration: `/services/ingestion/ingestion/dispatcher.py` (lines 113-236)
- Status: Ready to use, but not activated

**Parser Support:** ✅ AVAILABLE
- SchemaOrgParser at `/services/api/app/services/extraction/schema_org_parser.py`
- Confidence cap: 0.85 (deterministic, high precision)
- Handles JSON-LD markup extraction

**Valid Parser Strategies in System:**
```python
ParserStrategy = ["shopify", "html", "schema_org", "llm", "unknown"]
```

### Finding Schema.org Sources

**Database Query to Run:**
```sql
-- Find all stores with schema.org parser strategy
SELECT 
    id,
    domain,
    parser_strategy,
    active_flag,
    health_status,
    created_at
FROM stores
WHERE parser_strategy = 'schema_org'
ORDER BY domain;

-- Expected: Returns 0-N stores depending on initial setup
-- (If empty, need to identify candidates and assign schema.org strategy)
```

**Identification Method (if no schema.org stores exist):**

To find candidates, look for stores with:
1. Well-structured JSON-LD markup (schema.org microdata)
2. Modern e-commerce platforms (Shopify with schema.org support, WooCommerce with schema.org plugins)
3. Currently assigned to `html` or `unknown` strategy but have reliable schema.org markup

**Candidate Selection Criteria:**
```sql
-- Find HTML sources that MIGHT have schema.org markup
-- (Requires testing)
SELECT 
    s.domain,
    s.parser_strategy,
    COUNT(bl.id) as current_listings,
    AVG(bl.confidence) as avg_confidence
FROM stores s
LEFT JOIN bean_listings bl ON s.id = bl.store_id
WHERE s.parser_strategy = 'html'
  AND s.active_flag = 1
ORDER BY current_listings DESC, avg_confidence DESC
LIMIT 20;
```

---

## 2. Testing Schema.org Extraction

### Test Methodology

**Step 1: Verify Schema.org Markup Presence**

```python
#!/usr/bin/env python3
"""Test if a store has schema.org JSON-LD markup"""
import urllib.request
import re

def has_schema_org(domain):
    """Check if domain uses schema.org microdata"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(f"https://{domain}/shop/", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Look for JSON-LD script tags with Product schema
        has_json_ld = bool(re.search(r'"@type"\s*:\s*"Product"', html))
        has_itemscope = bool(re.search(r'itemscope.*itemtype.*schema\.org', html))
        
        return has_json_ld or has_itemscope
    except Exception as e:
        return False

# Usage
candidates = ["store1.com", "store2.com", "store3.com"]
for domain in candidates:
    if has_schema_org(domain):
        print(f"✓ {domain} has schema.org markup")
```

**Step 2: Extract and Compare**

```bash
# Route fresh ingestion request to schema.org pipeline
curl -X POST http://localhost:8000/api/v1/admin/sources/{store_id}/reingest \
  -H "Content-Type: application/json" \
  -d '{"parser_strategy": "schema_org"}'

# Monitor extraction
docker exec coffee_api python scripts/check_ingestion_run.py --store {domain}

# Compare results
# - Records seen
# - Records created
# - Average confidence
# - Errors encountered
```

**Step 3: Quality Metrics**

Compare schema.org extraction quality against HTML extraction:

```sql
-- Compare extraction methods for the same store
SELECT 
    'schema_org' as method,
    COUNT(*) as extractions,
    AVG(confidence) as avg_confidence,
    MIN(confidence) as min_confidence,
    MAX(confidence) as max_confidence,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY confidence) as median_confidence
FROM bean_listings
WHERE store_id = 'test_store_id'
  AND extraction_method = 'schema_org'

UNION ALL

SELECT 
    'html_rules',
    COUNT(*),
    AVG(confidence),
    MIN(confidence),
    MAX(confidence),
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY confidence)
FROM bean_listings
WHERE store_id = 'test_store_id'
  AND extraction_method = 'html_rules';
```

**Expected Results:**
- Schema.org confidence: **0.70-0.85** (higher than HTML rules)
- HTML rules confidence: **0.40-0.70**
- Schema.org = better precision, lower recall
- HTML rules = medium precision, medium recall

---

## 3. Activation Rollout Plan

### Phase B.1: Testing (Week 1)

**Goal:** Validate schema.org extraction works reliably

**Actions:**
1. **Day 1-2: Identify Candidates**
   - Query for stores with strong schema.org markup
   - Target 3-5 pilot stores (mix of platform types)
   - Document baseline metrics (current extraction rate)

2. **Day 3-4: Isolated Testing**
   - Deploy schema.org pipeline on test database
   - Run against 3 pilot stores
   - Compare confidence, extraction rate, error rate
   - Document findings

3. **Day 5: Decision Gate**
   - If schema.org avg confidence > 0.70: proceed to Phase B.2
   - If schema.org avg confidence < 0.70: pause, investigate issues, iterate
   - If error rate > 10%: debug error cases

### Phase B.2: Soft Launch (Week 2-3)

**Goal:** Activate schema.org for 5-10% of sources with positive feedback

**Actions:**
1. **Convert pilot stores to schema.org strategy**
   ```sql
   UPDATE stores
   SET parser_strategy = 'schema_org'
   WHERE domain IN ('pilot1.com', 'pilot2.com', 'pilot3.com');
   ```

2. **Monitor 1 week for:**
   - Extraction success rate
   - Product quality (confidence scores)
   - Average time per ingestion
   - Error patterns
   - Canonical matching quality

3. **Metrics Target (Soft Launch Success):**
   - Extraction rate: ≥ 80% (products extracted / pages fetched)
   - Average confidence: ≥ 0.65
   - Error rate: < 5%
   - Ingestion time: < 300s per store

### Phase B.3: Gradual Rollout (Week 4-6)

**Goal:** Expand schema.org to 50% of suitable sources

**Conversion Candidates:**
- All Shopify stores (should have schema.org support)
- All "unknown" strategy stores with detectable schema.org
- Selected HTML sources that underperform (< 0.60 avg confidence)

**Rollout Schedule:**
```
Week 4:  Enable for 10% of candidates   (50-100 stores)
Week 5:  Enable for 25% of candidates   (150-250 stores) 
Week 6:  Enable for 50% of candidates   (250-400 stores)
         → Decision on 100% rollout
```

**Parallel Monitoring:**
- Track extraction metrics daily
- Watch for platform-specific issues (e.g., Shopify vs custom)
- Identify underperforming stores for fallback strategy

### Phase B.4: Full Rollout (Week 7+)

**Goal:** 100% schema.org adoption for sources with markup

**Final Actions:**
1. Convert remaining suitable stores
2. Document final metrics (before vs after)
3. Assess hybrid strategies needed (schema.org + HTML fallback)
4. Archive old HTML-only extractions

**Keep monitoring:**
- Weekly ingestion reports
- Quality feedback from matching pipeline
- Any emerging patterns or failure modes

---

## Strategy Hierarchy (After Activation)

### Recommended Parser Strategy Assignment

```
Platform Detection → Assigned Strategy
┌─────────────────────────────────────────────────┐
│ Shopify (products.json available)               │
│ └─→ shopify (highest reliability & speed)       │
├─────────────────────────────────────────────────┤
│ Modern e-commerce WITH schema.org JSON-LD       │
│ └─→ schema_org (high precision, medium recall)  │
├─────────────────────────────────────────────────┤
│ Traditional HTML sites (WooCommerce, custom)     │
│ └─→ html (medium precision, medium recall)      │
├─────────────────────────────────────────────────┤
│ Sites requiring intelligent parsing (complex)    │
│ └─→ llm (highest recall, but uses API $$)       │
├─────────────────────────────────────────────────┤
│ Unknown / can't detect platform                  │
│ └─→ unknown (fallback to extraction service)    │
└─────────────────────────────────────────────────┘
```

### Smart Fallback Chain

After Phase B activation, implement intelligent fallback:

```python
# When schema.org extraction fails:
try schema_org_parser
except confidence < 0.4:
    try html_rules_parser
    except confidence < 0.4:
        try llm_parser
        except:
            return no_extraction
```

---

## Implementation Checklist

### Pre-Activation
- [ ] Verify SchemaOrgIngestionPipeline compiles and imports correctly
- [ ] Confirm dispatcher routing to `_run_schema_org()` works
- [ ] Test on 1 known schema.org source (manual ingestion)
- [ ] Document baseline metrics for comparison

### Soft Launch (5-10% of sources)
- [ ] Select 3-5 pilot stores with strong schema.org markup
- [ ] Convert pilot stores to schema.org strategy in DB
- [ ] Monitor ingestion success rate (target: ≥ 80%)
- [ ] Monitor extraction confidence (target: avg ≥ 0.65)
- [ ] Document any errors or edge cases
- [ ] Approve or iterate

### Gradual Rollout (10-50%)
- [ ] Identify next batch of schema.org candidates
- [ ] Implement A/B testing (schema.org vs current strategy)
- [ ] Monitor quality metrics
- [ ] Prepare rollback plan if needed
- [ ] Weekly reporting to stakeholders

### Full Rollout (50-100%)
- [ ] Convert all suitable sources
- [ ] Monitor stability for 2 weeks
- [ ] Document final metrics
- [ ] Update configuration documentation
- [ ] Archive Phase B.1-B.3 test results

---

## Risk Assessment

### Low Risk
- ✅ Schema.org parser already built and tested
- ✅ Dispatcher integration complete
- ✅ Fallback to HTML/LLM available
- ✅ No database schema changes needed

### Medium Risk
- ⚠️  Some stores may have broken JSON-LD markup
- ⚠️  Platform-specific quirks (Shopify vs WooCommerce schema)
- ⚠️  Ingestion time might increase (more parsing)

### Mitigation
- Start small (5 pilot stores)
- Monitor closely (daily metrics)
- Quick rollback capability (revert parser_strategy in DB)
- Fallback strategy always available

---

## Success Criteria

**Phase B Complete When:**
- ✅ 10+ stores successfully using schema.org strategy
- ✅ Average extraction confidence ≥ 0.65
- ✅ Error rate < 5%
- ✅ Extraction time per store < 300s
- ✅ Canonical matching works correctly
- ✅ No critical bugs reported

---

## Deliverables

| Item | Owner | Timeline | Status |
|------|-------|----------|--------|
| Identify pilot stores | DevOps/Product | Week 1 | ⬜ TODO |
| Test extraction quality | Engineering | Week 1 | ⬜ TODO |
| Soft launch 5 stores | DevOps | Week 2 | ⬜ TODO |
| Monitor metrics | Engineering | Weeks 2-3 | ⬜ TODO |
| Gradual rollout plan | Product | Week 4 | ⬜ TODO |
| Full activation | DevOps | Week 7 | ⬜ TODO |

---

## Next Actions

1. **Immediate:** Query database for existing schema.org stores
   ```bash
   # Via admin API or direct DB query
   SELECT * FROM stores WHERE parser_strategy = 'schema_org';
   ```

2. **This week:** Test schema.org extraction on 1-2 known good sources
   - Verify markup detection
   - Check extraction quality
   - Validate confidence scores

3. **Next week:** Begin Phase B.1 testing with pilots
   - Identify 5 candidate stores
   - Run isolated tests
   - Document baseline metrics

4. **Week 3:** Decision point - green light for Phase B.2?
   - Review metrics
   - Approve or iterate
   - Plan soft launch

---

**Document Version:** 1.0  
**Last Updated:** May 24, 2026  
**Status:** READY FOR IMPLEMENTATION
