# Extraction System Status Report
Date: 2026-06-13

## Executive Summary
**Current extraction success rate: 0.48% (4 stores extracting out of 827 active stores)**

Only 4 stores are successfully extracting product data:
- 2 HTML stores (bradyscoffee.ie, hotnumberscoffee.co.uk)
- 2 Shopify stores (colonnacoffee.com, assemblycoffee.co.uk)

## By Parser Strategy

### HTML Stores (762 total)
- **Working**: 2 stores (0.26% success)
  - bradyscoffee.ie: 30 products updated, 43 seen
  - hotnumberscoffee.co.uk: 11 new products
- **Failing**: 760 stores (99.74%)
  - Most are fetching pages (20-180+ pages) but extracting 0 products
  - Suggests extraction chain failing silently on most site structures

### Shopify Stores (16 total)
- **Working**: 2 stores (12.5% success)
  - colonnacoffee.com: 4 products (1 new, 3 updated)
  - assemblycoffee.co.uk: 1 product
- **Failing**: 14 stores (87.5%)

### LLM Stores (43 total)
- **Working**: 0 stores (0% success)
- Requires API credits (currently exhausted)

### Unknown Stores (6 total)
- **Working**: 0 stores (0% success)

## Key Findings

### Why Only 4 Stores Work
1. **hotnumberscoffee.co.uk** (HTML, custom-built)
   - Not WooCommerce
   - Uses standard HTML patterns that schema.org or HTML rules can parse
   - Successfully extracts 11 products from 176 pages

2. **bradyscoffee.ie** (HTML, WooCommerce)
   - Successfully maintains 30 products
   - Extraction chain finding 43 products per run
   - Updates existing products but records_created=0 (stable state)

3. **colonnacoffee.com** (Shopify)
   - Shopify pipeline working for this store

4. **assemblycoffee.co.uk** (Shopify)
   - Shopify pipeline working for this store

### Root Causes of 0% Extraction Rate on 823 Failing Stores

1. **JavaScript-Rendered Content**
   - Sites like 17Grams.co.uk embed product data via omnisend_product JavaScript
   - Static HTML fetches don't get this data
   - JSON extractor returns None (tested and working, but no data in HTML)
   - Browser extractor fails (Playwright chromium not installed)

2. **Missing Schema.org Markup**
   - Most sites don't include schema.org microdata
   - HTML rules parser has no custom rules for most sites

3. **Anti-Bot Protection / Geographic Blocking**
   - Pipeline fetches pages successfully (pages_fetched > 0)
   - But content may be different from browser requests
   - Or sites deliberately serve different content to automated clients

4. **API Credit Exhaustion**
   - LLM extraction requires API credits
   - Current credits: insufficient
   - Blocks LLM-based extraction for 43 stores

## Technical Blockers

| Blocker | Impact | Severity | Fix Required |
|---------|--------|----------|--------------|
| Playwright chromium not installed | Browser extractor fails | HIGH | Install system dependencies in Docker |
| omnisend_product in JS only | JSON extractor returns None | HIGH | JavaScript rendering or alternative data source |
| No schema.org on most sites | schema.org extractor fails | MEDIUM | Custom HTML rules for each site or smarter detection |
| API credits exhausted | LLM extraction blocked | HIGH | Refill API credits |
| No custom HTML rules | Generic rules only match standard patterns | MEDIUM | Build extraction rules for each site |

## Actionable Next Steps

### Quick Wins (Low effort, medium impact)
1. **Refill API credits** → Enables LLM extraction for 43 stores
2. **Install Playwright chromium** → Enables browser extraction for JS-heavy sites
3. **Check if 17Grams has product API** → Alternative to omnisend_product JSON

### Medium Effort (High impact)
1. **Build custom HTML rules** for top 50 failing stores
2. **Analyze successful stores** to find common HTML patterns to generalize
3. **Implement smart site detection** to auto-select best extraction method

### Architectural Improvements
1. **Hybrid JavaScript execution** - Use Playwright or Cheerio for JS rendering
2. **Multi-source extraction** - Try multiple data sources per site (API, JSON, schema.org, HTML)
3. **Feedback loop** - Use extracted data to refine rules for future runs

## Status of Recent Work

### JSON Extraction Integration ✅
- Created and tested WooCommerce JSON extractor
- Successfully extracts from omnisend_product when present
- Integrated into HtmlExtractor as first extraction method
- **Issue**: omnisend_product data not in static HTML fetches
- **Lesson**: Sites with JS-injected content need rendering, not just fetching

### Extraction Success Analysis ✅
- Analyzed 827 active stores
- Identified only 4 working stores
- Root causes identified (JS rendering, schema.org, API credits)
- Documented technical blockers and next steps

## Recommendations

**Immediate Priority**: Refill API credits to unblock 43 LLM stores

**Next Priority**: Install Playwright + chromium to enable browser rendering for JS sites

**Long-term**: Build extraction rules library based on successful patterns from 2 working HTML stores
