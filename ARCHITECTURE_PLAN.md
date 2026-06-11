# Architecture Plan: Local Development + Railway Deployment

## Current State (Local - No Changes)

```
You are here:

┌─────────────────────────────────────────────────────────┐
│                    YOUR COMPUTER (Local)                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Admin App (port 3001)                                 │
│       ↓                                                 │
│  FastAPI Backend (port 8000)                           │
│  ├─ Data entry                                         │
│  ├─ Extraction pipelines                              │
│  └─ Complex business logic                            │
│       ↓                                                 │
│  PostgreSQL (port 5432)                               │
│       ↓                                                 │
│  Your Coffee Data                                      │
│                                                         │
│  Public Site (port 3000) ←──┐                         │
│       └─→ Calls FastAPI API ─┘                        │
│                                                         │
└─────────────────────────────────────────────────────────┘

Status: Keep exactly as-is. Keep building.
```

### What You Do Locally

1. **Enter data in admin-app** (http://localhost:3001)
2. **API processes it** (http://localhost:8000)
3. **Public site tests it** (http://localhost:3000)
   - Calls the FastAPI backend
   - No changes to your workflow

---

## Future State (Railway Deployment)

When you're ready to let others test, you'll deploy to Railway using one of two options:

### Option A: Direct Database (Recommended)
```
┌─────────────────────────────┐
│      RAILWAY (Cloud)        │
├─────────────────────────────┤
│                             │
│  Public Site (Deployed)     │
│       ↓                      │
│  Next.js API Routes         │ ← NEW: queries DB directly
│  (/api/coffees, etc.)       │    (we built these)
│       ↓                      │
│  PostgreSQL (Railway)       │
│       ↓                      │
│  Coffee Data                │
│                             │
└─────────────────────────────┘

Flow:
- You: admin-app → API → export data
- They: public-site → direct DB queries ← cost: $7/month
```

**New files used:**
- `src/lib/db.ts` (PostgreSQL connection)
- `src/lib/db-queries.ts` (SQL queries)
- `src/app/api/` (Next.js API routes)
- `src/lib/api.ts` (modified to call local routes)

### Option B: Full Stack on Railway (Simpler but Expensive)
```
┌──────────────────────────────┐
│      RAILWAY (Cloud)         │
├──────────────────────────────┤
│                              │
│  Admin App (Optional)        │
│       ↓                       │
│  FastAPI API (Deployed)      │
│       ↓                       │
│  Public Site (Deployed)      │
│       ↓                       │
│  PostgreSQL (Railway)        │
│       ↓                       │
│  Coffee Data                 │
│                              │
└──────────────────────────────┘

Flow:
- You: admin-app → API → data
- They: public-site → FastAPI → DB ← cost: $25-30/month
```

**New files used:** None. Same setup as local.

---

## Decision Point (When You Deploy)

When you're ready:

**Choose Option A if:** You want the cheapest solution ($7/month) and only need the public-site to display data (no real-time admin edits).

**Choose Option B if:** You want to keep the full setup on Railway, or eventually deploy admin-app there too for collaborative editing.

---

## Current Action Items

### Now (Local)
- ✅ Keep building in admin-app
- ✅ Keep using FastAPI locally
- ✅ Keep using public-site for testing
- ✅ No changes needed

### When Ready to Deploy
1. Create PostgreSQL on Railway (`railway add`)
2. Export local data: `pg_dump ... > backup.sql`
3. Import to Railway: `psql RAILWAY_URL < backup.sql`
4. Deploy public-site to Railway
5. Choose Option A or B:
   - **Option A:** Update `api.ts` to call local API routes (we have the files ready)
   - **Option B:** Just deploy everything as-is (no code changes)
6. Share Railway URL with testers

---

## File Reference

### Files Created (for Option A - Railway Direct DB)
These are ready to use when you deploy to Railway:

```
apps/public-site/
├── src/lib/
│   ├── db.ts ..................... PostgreSQL connection pool
│   └── db-queries.ts ............. SQL query functions
│
├── src/app/api/
│   ├── coffees/route.ts ........... GET /api/coffees
│   ├── coffees/[id]/route.ts ...... GET /api/coffees/:id
│   ├── coffees/[id]/compare/route.ts
│   ├── roasters/route.ts .......... GET /api/roasters
│   ├── new-releases/route.ts ...... GET /api/new-releases
│   └── market/averages/route.ts ... GET /api/market/averages
│
└── .env.local ..................... DATABASE_URL (for dev)
```

**These files don't affect local development.** Your `api.ts` still calls FastAPI locally.

### Files Unchanged (Local Development)
```
apps/public-site/
└── src/lib/api.ts ................. REVERTED to call FastAPI
                                   (still uses localhost:8000)
```

---

## Cost Comparison

| Setup | Local | Railway (Option A) | Railway (Option B) |
|-------|-------|-------------------|-------------------|
| **Services** | Admin + API + DB | Public-site + DB | Admin + API + Public-site + DB |
| **Cost** | Free (local machine) | $7-10/month | $25-30/month |
| **Data entry** | You (local) | You (local, then sync) | Cloud (collaborative) |
| **Public access** | No | Yes | Yes |
| **Complexity** | High (3 processes) | Low (1 process + managed DB) | High (4+ processes) |

---

## Next Steps

**Choose one:**

1. **Continue building locally** (what you're doing now)
   - Nothing changes
   - Keep using admin-app + API locally
   - Deploy when you're ready

2. **Deploy to Railway now**
   - Create PostgreSQL
   - Export/import your data
   - Deploy public-site
   - Choose Option A or B above

3. **Ask me questions**
   - About the architecture
   - When you're ready to deploy
   - If you hit any issues

---

**You're all set. Keep building!** 🚀
