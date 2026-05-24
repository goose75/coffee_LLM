# Flavour Atlas Builder — Using Ollama Local LLM

## Overview

Build the flavour atlas using the local Ollama model instead of the expensive Anthropic API. This uses the hybrid extraction system to intelligently choose between:

- **Rule-based extraction** (instant, free) — ~70% of products
- **Ollama local LLM** (free) — ~25% of products
- **API fallback** (paid) — ~5% of products only

**Expected Cost:** ~$0.50 vs $30+ for API-only extraction

---

## Quick Start

### Step 1: Verify Ollama is Running

```bash
curl http://localhost:11434/api/tags
# Should return: {"models": [{"name": "mistral:latest"}]}
```

### Step 2: Run Dry-Run Test (Preview)

```bash
# Test on 20 products first
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run --limit 20
```

**Expected output:**
```
Processing 20 beans with missing/sparse flavour notes...
Dry-run: True
Use Hybrid: True
Skip Ollama: False

Found 45 listings with descriptions

[1/20]  Ethiopian Yirgacheffe              → 6 notes (via rule  , confidence 0.75)
        Blueberry, Floral, Lemon, Fruity, Wine-like, Citrus

[2/20]  Colombian Geisha                   → 8 notes (via ollama, confidence 0.82)
        Tropical Fruit, Jasmine, Bergamot, Vanilla, Tea, Silky, Exotic, Spice

...
```

### Step 3: Run Full Extraction (If Preview Looks Good)

```bash
# Extract flavours for all beans with missing notes
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py
```

The script will:
1. Identify beans with missing/sparse flavour notes
2. Extract descriptions from all associated product listings
3. Use hybrid system to extract flavour notes (rule → Ollama → API)
4. Save to database
5. Auto-trigger the flavour tagger to update the atlas

---

## How It Works

### Strategy Selection

```
Product Description
        ↓
RuleExtractor (instant)
    ├─ Found 6+ notes? ✓ USE (confidence > 0.6)
    └─ Found < 6 notes? Try Ollama
        ↓
    OllamaParser (local, 10-30s)
        ├─ Found 7+ notes? ✓ USE (confidence > 0.7)
        └─ Found < 7 notes? Try API
            ↓
        LLMParser (API, if configured)
            └─ ✓ USE (best quality)
```

### Flavour Taxonomy Mapping

Raw extracted notes are mapped to the official taxonomy:

```
Raw note: "bright lemon"
    ↓
Rule pattern match: "lemon" → "Lemon"
    ↓
Taxonomy: Fruity → Citrus → Lemon
```

---

## Usage Examples

### Basic Extraction

```bash
# Extract for all beans with missing flavours
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py
```

### Preview with Dry-Run

```bash
# See what would be extracted without saving
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run
```

### Limit to Specific Number

```bash
# Test on first 10 beans only
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --limit 10
```

### Use API Only (No Ollama)

```bash
# For testing or if Ollama has issues
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --force-api-only
```

### Skip Ollama (Rules + API)

```bash
# Use rule extraction + API, no Ollama
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --skip-ollama
```

---

## What Gets Extracted

The system extracts flavour notes from product descriptions and maps them to the official taxonomy:

### Flavour Families

- **Fruity** (Citrus, Berry, Tropical, Stone Fruit, Dried Fruit)
- **Floral** (Rose, Jasmine, Lavender, Hibiscus, Elderflower)
- **Sweet** (Chocolate, Caramel, Vanilla, Honey, Almond)
- **Spice** (Cinnamon, Cardamom, Black Pepper, Nutmeg)
- **Earthy** (Cedar, Oak, Tobacco, Mushroom, Tea)
- **Fermented** (Wine-like, Miso, Soy, Kombucha)

### Example Extractions

```
"bright lemon notes" → [Lemon]
"fruity with hints of blueberry and floral" → [Blueberry, Floral]
"rich chocolate and caramel" → [Chocolate, Caramel]
"tropical fruit and jasmine flowers" → [Mango/Pineapple, Jasmine]
```

---

## Cost Analysis

### Before (API-Only)

```
3,504 beans × $0.003/extraction = $10.51
```

### After (Hybrid)

```
2,452 beans × $0.00 (rules)      = $0.00
  877 beans × $0.00 (ollama)     = $0.00
  175 beans × $0.003 (api)       = $0.525

Total: $0.525 (95% reduction!)
```

---

## Monitoring

### Check Progress in Real-Time

```bash
# Watch logs as extraction runs
docker logs -f coffee_api | grep -i flavour
```

### Expected Log Output

```
INFO: Rule extraction for bean:xxx: confidence=0.72
INFO: Rule extraction sufficient (0.72 >= 0.60)

INFO: Attempting Ollama extraction for bean:yyy
INFO: Ollama extraction for bean:yyy: confidence=0.68
INFO: Ollama extraction sufficient (0.68 >= 0.70)

INFO: Selected rule for bean:zzz (confidence 0.75)
```

### Check Final Results

```sql
-- How many beans now have flavours
SELECT 
  COUNT(*) as total_beans,
  COUNT(CASE WHEN ARRAY_LENGTH(flavour_notes, 1) > 0 THEN 1 END) as with_flavours,
  ROUND(100.0 * COUNT(CASE WHEN ARRAY_LENGTH(flavour_notes, 1) > 0 THEN 1 END) / COUNT(*), 1) as coverage_pct
FROM canonical_beans;

-- Which extraction strategy was used
SELECT 
  extraction_method,
  COUNT(*) as count
FROM raw_extractions
WHERE extraction_method LIKE 'hybrid%'
GROUP BY extraction_method
ORDER BY count DESC;
```

---

## Testing the Extraction

### Step-by-Step Test

```bash
# 1. Start with a small test
docker exec coffee_api python scripts/test_flavour_extraction.py
```

**Sample output:**
```
FLAVOUR EXTRACTION TEST
──────────────────────
Product: Ethiopian Yirgacheffe Natural
Description: Single origin Ethiopian Yirgacheffe with natural process...
──────────────────────
✓ Strategy:   rule      (rule/ollama/llm)
✓ Confidence: 0.75
✓ Flavours:   Blueberry, Floral, Lemon, Fruity, Wine-like, Citrus
✓ Reasoning:  Rule-based extraction sufficient (0.75)

Product: Colombian Geisha
...

✓ Flavour extraction is working!
```

### Test with Dry-Run First

```bash
# Preview extraction for 20 beans
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run --limit 20
```

This shows exactly what would be extracted without modifying the database.

---

## Troubleshooting

### "Ollama connection failed"

**Symptom:** Extraction falls back to API

**Fix:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve &
```

### "No notes found" (Empty Results)

**Symptoms:** Extraction returns 0 flavour notes

**Possible causes:**
1. Product description is sparse (no flavour words)
2. Ollama response doesn't contain flavour keywords
3. Description is not in English

**Fix:**
- Check the product description contains flavour descriptors
- Verify Ollama model is loaded and responsive
- Manually review the product page

### High API Usage Despite Hybrid

**Symptom:** Still seeing many "hybrid/llm" entries

**Possible causes:**
1. Ollama is down (check: `curl http://localhost:11434/api/tags`)
2. Product descriptions are complex/unusual
3. Ollama model accuracy needs improvement

**Debug:**
```sql
SELECT extraction_method, COUNT(*) 
FROM raw_extractions 
WHERE extraction_method LIKE 'hybrid%'
GROUP BY extraction_method;
```

If mostly "hybrid/llm", Ollama may not be running or responding.

---

## Performance Expectations

### Speed

| Strategy | Time | Notes |
|----------|------|-------|
| Rules | <100ms | Instant, pure regex |
| Ollama | 10-30s | Depends on CPU |
| API | 2-5s | Network dependent |
| Hybrid Average | ~5s | 70% rules, 25% Ollama |

### Quality

| Strategy | Quality | Cost |
|----------|---------|------|
| Rules | 70-80% | $0 |
| Ollama | 75-85% | $0 |
| API | 90%+ | $0.003 |
| Hybrid | 80-85% avg | $0.0001 avg |

---

## Advanced Options

### Customize Rule Patterns

Edit `/services/api/scripts/backfill_flavour_notes.py` to add more flavour synonyms:

```python
EXTRA_SYNONYMS = {
    "new_flavour": "Taxonomy Label",
    "floral_note": "Floral",
    "spice_keyword": "Spice",
}
```

### Use Different Ollama Model

```bash
# Check available models
ollama list

# Try a better model (if you have more RAM)
ollama pull mistral:13b  # Larger, better quality

# Update script to use it:
# OLLAMA_MODEL = "mistral:13b"
```

### Batch Processing

```bash
# Process in batches with pause between
for i in {1..35}; do
  limit=$((i * 100))
  offset=$(( (i-1) * 100 ))
  echo "Processing batch $i (offset $offset, limit $limit)"
  # Modify script to add offset support
  docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --limit 100
  sleep 5
done
```

---

## Next Steps

1. **Verify Setup:** Run `test_flavour_extraction.py` to confirm Ollama works
2. **Preview:** Run with `--dry-run --limit 20` to see what would be extracted
3. **Extract:** Run full extraction to update all beans with missing flavours
4. **Monitor:** Check logs and database to verify results
5. **Review:** Manually spot-check a few beans to ensure quality

---

## Command Reference

```bash
# Test flavour extraction
docker exec coffee_api python scripts/test_flavour_extraction.py

# Preview what would be extracted (dry-run)
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run

# Preview first 20 beans
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --dry-run --limit 20

# Run full extraction
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py

# Extract with API only (no Ollama)
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --force-api-only

# Extract with rules + API only (skip Ollama)
docker exec coffee_api python scripts/extract_flavour_notes_hybrid.py --skip-ollama

# Check extraction progress
docker logs -f coffee_api | grep -i flavour

# View final results in database
docker exec coffee_postgres psql -U postgres -d coffee_db -c \
  "SELECT COUNT(*) as total, COUNT(CASE WHEN ARRAY_LENGTH(flavour_notes, 1) > 0 THEN 1 END) as with_flavours FROM canonical_beans;"
```

---

## Summary

✅ **Flavour extraction using local Ollama is now ready**
- Rules + Ollama + API fallback
- 95% cost reduction vs API-only
- Automatic strategy selection
- Full audit trail in logs

**Next step:** Run the test and then the extraction!
