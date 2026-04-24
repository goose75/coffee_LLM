# Coffee Platform

UK specialty coffee intelligence platform. Tracks prices, provenance, and taste profiles across UK roasters.

## What you'll see when running

| URL | What it is |
|---|---|
| http://localhost:3000 | **Public website** — browse coffees, price history, taste profiles |
| http://localhost:3001 | **Admin app** — ingestion, match review, price intelligence, taste review |
| http://localhost:8000 | **API** — FastAPI backend (JSON) |
| http://localhost:8000/docs | **API docs** — interactive Swagger UI |

---

## Prerequisites

- **Docker Desktop** — https://www.docker.com/products/docker-desktop
- **Node.js 20+** — https://nodejs.org
- **pnpm** — `npm install -g pnpm`

---

## Setup (one time)

### 1 — Start database and API

```bash
docker compose up -d postgres redis
sleep 10
docker compose up -d api
curl http://localhost:8000/health   # should return {"status":"ok",...}
```

### 2 — Run migrations

```bash
docker exec coffee_api alembic upgrade head
```

This runs both migrations:
- `001_initial_schema` — all 10 core tables
- `002_flavour_taxonomy` — flavour_taxonomy and bean_flavour_tags tables

### 3 — Seed the database

```bash
# Base seed: stores, canonical beans, normalisation mappings
docker exec coffee_api python scripts/seed.py

# Extended seed: listings, variants, 60-day price history, flavour taxonomy, taste tags
docker exec coffee_api python scripts/seed_extended.py
```

After seeding you'll have:
- 5 UK roasters
- 3 canonical beans (Ethiopia, Colombia, Kenya)
- 8 listings across 4 stores with 18 variants
- 60 days × 18 variants of price history
- Full 3-level flavour taxonomy (8 families → ~30 categories → ~100 tags)
- Rule-matched taste tags for all beans

### 4 — Install frontend dependencies

```bash
pnpm install
```

### 5 — Start the frontends

```bash
# Terminal 1 — public website
cd apps/public-site && pnpm dev    # http://localhost:3000

# Terminal 2 — admin app
cd apps/admin-app && pnpm dev      # http://localhost:3001
```

---

## Everything in one go (after setup)

```bash
# Terminal 1 — backend
docker compose up -d

# Terminal 2 — public site
cd apps/public-site && pnpm dev

# Terminal 3 — admin app
cd apps/admin-app && pnpm dev
```

---

## Feature overview

### Price Intelligence

| Route | What it shows |
|---|---|
| `GET /coffees/{id}/price-history` | 60-day price time series per variant |
| `GET /coffees/{id}/price-compare` | Cross-store current price comparison |
| `GET /coffees/{id}/price-stats` | Min/median/max summary cards per weight |
| `GET /market/averages` | Market-wide pricing by origin/process/roast |
| `GET /admin/prices/recent-changes` | Variants with price changes > 1% in 14 days |
| `GET /admin/prices/anomalies` | Suspected pricing errors |
| `GET /admin/prices/weight-coverage` | Variants missing weight_g |

Admin UI: http://localhost:3001/prices

### Taste Profile Intelligence

| Route | What it shows |
|---|---|
| `GET /coffees/{id}/taste-profile` | Structured flavour families + tags |
| `GET /coffees/{id}/similar` | Similar coffees by taste (Jaccard on families) |
| `GET /taste/distribution` | Family counts aggregated by origin/process/roast |
| `GET /admin/taste/review` | Low-confidence LLM tags pending human review |
| `POST /admin/taste/review/{id}/accept` | Accept a tag |
| `POST /admin/taste/review/{id}/reject` | Reject a tag |
| `POST /admin/taste/tag-bean/{id}` | Trigger normalisation for one bean |
| `POST /admin/taste/tag-all` | Bulk rule-based tagging for all beans |

Admin UI: http://localhost:3001/taste/review

### Running the LLM taste normaliser

The rule-based tagger runs automatically during `seed_extended.py`. For LLM-assisted normalisation of unmatched notes, set your API key and run:

```bash
# Trigger LLM normalisation for all beans (requires ANTHROPIC_API_KEY in .env)
curl -X POST "http://localhost:8000/api/v1/admin/taste/tag-all?use_llm=true"
```

Low-confidence LLM results (< 0.70) are queued at `/admin/taste/review` for human review.

---

## Running tests

```bash
cd services/api
python -m pytest tests/ -v
```

Key test files:
- `test_taste.py` — taxonomy structure, rule normaliser, similarity scoring, schemas
- `test_prices.py` — price normalisation, statistics, schema validation
- `test_normalisation.py` — roast/grind/process/country/region rule matching
- `test_matching.py` — entity resolution signal scorers

---

## Project structure

```
coffee-platform/
├── apps/
│   ├── public-site/               Next.js — public website (port 3000)
│   │   └── src/app/coffees/[id]/  Coffee detail with price chart + taste wheel
│   └── admin-app/                 Next.js — admin dashboard (port 3001)
│       └── src/app/
│           ├── prices/            Price changes, anomalies, weight coverage
│           └── taste/review/      LLM taste tag review queue
├── services/api/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── prices.py          Price intelligence endpoints
│   │   │   └── taste.py           Taste profile endpoints
│   │   ├── models/
│   │   │   └── flavour.py         FlavourTaxonomy + BeanFlavourTag ORM models
│   │   ├── schemas/
│   │   │   ├── prices.py          Price intelligence Pydantic schemas
│   │   │   └── taste.py           Taste intelligence Pydantic schemas
│   │   └── services/taste/
│   │       ├── taxonomy.py        3-level flavour vocabulary (8 families, ~100 tags)
│   │       ├── normaliser.py      Rule-based note→slug matching
│   │       ├── llm_normaliser.py  Claude-backed fallback normaliser
│   │       ├── service.py         TasteTaggingService orchestrator
│   │       └── prompts/v1.py      Versioned LLM prompt (taste-v1.0.0)
│   ├── alembic/versions/
│   │   ├── 001_initial_schema.py
│   │   └── 002_flavour_taxonomy.py
│   ├── scripts/
│   │   ├── seed.py               Base seed (stores, beans, mappings)
│   │   └── seed_extended.py      Extended seed (listings, prices, taxonomy, tags)
│   └── tests/test_services/
│       ├── test_prices.py
│       └── test_taste.py
```

---

## Stopping everything

```bash
docker compose down        # stops containers, keeps data
docker compose down -v     # stops containers AND wipes database
```

---

## Troubleshooting

**Empty price charts / taste wheels**
Run the extended seed: `docker exec coffee_api python scripts/seed_extended.py`

**`alembic upgrade head` fails on migration 002**
The migration requires the `review_status` enum from migration 001. Make sure both run in order.

**Taste tags not appearing on coffee detail page**
The taste profile endpoint falls back to the legacy wheel if no tags exist. Trigger tagging:
```bash
curl -X POST http://localhost:8000/api/v1/admin/taste/tag-all
```

**API health check fails**
```bash
docker compose logs api --tail=30
docker compose restart api
```
