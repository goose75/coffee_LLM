# Lightweight Deployment - Quick Start

## What We Just Built

✅ **public-site now queries the database directly** (no API needed)
✅ **Local API routes** wrap database queries (`/api/coffees`, `/api/roasters`, etc.)
✅ **Ready to deploy** to Railway with just PostgreSQL + Next.js frontend
✅ **Zero external dependencies** - no FastAPI, Redis, or complex orchestration

## Files Changed

```
apps/public-site/
├── src/lib/
│   ├── api.ts (UPDATED - now calls local API routes)
│   ├── db.ts (NEW - PostgreSQL connection pool)
│   └── db-queries.ts (NEW - SQL queries for coffees, roasters, etc.)
├── src/app/api/
│   ├── coffees/
│   │   ├── route.ts (GET /api/coffees)
│   │   └── [id]/
│   │       ├── route.ts (GET /api/coffees/:id)
│   │       └── compare/route.ts (GET /api/coffees/:id/compare)
│   ├── roasters/route.ts (GET /api/roasters)
│   ├── new-releases/route.ts (GET /api/new-releases)
│   └── market/averages/route.ts (GET /api/market/averages)
├── .env.local (NEW - DATABASE_URL for local dev)
└── package.json (UPDATED - added pg driver)
```

## How It Works

**Before:**
```
Client → public-site → FastAPI API → PostgreSQL
(requires 3 services to test)
```

**Now:**
```
Client → public-site → Local Next.js API Routes → PostgreSQL
(requires only 2 services: database + frontend)
```

## Testing Locally

**1. Make sure PostgreSQL is running:**
```bash
psql -U coffee -h localhost coffee_platform -c "SELECT 1"
```

**2. Start the public-site:**
```bash
cd apps/public-site
npm run dev
```

**3. Visit http://localhost:3000**
- Browse coffees ✅
- Search by origin ✅
- View roasters ✅
- See new releases ✅

No API needed!

## Deploying to Railway

### Step 1: Create PostgreSQL on Railway
```bash
cd /Users/travisganz/coffee_LLM
railway login
railroad init
railway add  # Select PostgreSQL
```

### Step 2: Get Railway Postgres URL
In Railway dashboard, go to PostgreSQL service → Settings → copy the connection string

### Step 3: Seed Data
```bash
# Export local data
pg_dump -U coffee -h localhost coffee_platform > backup.sql

# Import to Railway
psql "YOUR_RAILWAY_DATABASE_URL" < backup.sql
```

### Step 4: Deploy public-site to Railway
In Railway dashboard:
1. Click **+ New** → **GitHub Repo** → Select coffee_LLM
2. Set config:
   - **Root directory:** `apps/public-site`
   - **Add variable:** `DATABASE_URL=YOUR_RAILWAY_DATABASE_URL`
3. Click Deploy

### Step 5: Test Live
Railway gives you a URL like: `public-site-prod-xxxxx.up.railway.app`

Visit it → see your live coffee platform!

## Cost

| Service | Cost |
|---------|------|
| PostgreSQL | $7/month |
| Next.js (public-site) | Included in $5 credit |
| **Total First Month** | **Free (within $5 credit)** |
| **Monthly After** | **~$7-10** |

## Next Steps (Priority Order)

### Immediate (this hour)
- [ ] Deploy PostgreSQL to Railway
- [ ] Export/import your local data
- [ ] Deploy public-site
- [ ] Verify it works at public URL

### This week
- [ ] Share public-site URL with testers
- [ ] Continue data entry via local admin-app
- [ ] Weekly: export local data → import to Railway

### Later (optional enhancements)
- [ ] Add individual coffee detail pages
- [ ] Implement price history charts
- [ ] Add taste profile / flavor families
- [ ] Deploy admin-app to Railway for collaborative editing

## Troubleshooting

**"No data showing"** → Export/import your database
```bash
pg_dump -U coffee coffee_platform > backup.sql
psql "YOUR_RAILWAY_URL" < backup.sql
```

**"Connection refused"** → Check DATABASE_URL environment variable in Railway
- Should look like: `postgresql://user:pass@host:port/db`

**"SSL error"** → Railway requires SSL
- The pg driver handles this automatically
- If issues: add `?sslmode=require` to connection string

---

**Ready to deploy?** Run:
```bash
railway login && railway init
```

Questions? Check DEPLOYMENT_GUIDE.md for detailed steps.
