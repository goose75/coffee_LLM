# Lightweight Deployment Guide (Database + Public Site)

## What We Changed

The public-site now queries the PostgreSQL database **directly** instead of calling the FastAPI backend. This means:

✅ **No API deployment needed** — saves server costs
✅ **Simple architecture** — just database + frontend
✅ **Users can test** — public-site is fully functional
✅ **You manage data locally** — use admin-app + API locally, sync to Railway when ready

## Architecture

```
You (Local)
├── admin-app (port 3001) → API (port 8000) → PostgreSQL (local:5432)
│   └─ You manage data entry here
│
└── public-site (local:3000) → PostgreSQL (Railway cloud) [after deployment]
    └─ Users test the platform here
```

## Deployment Steps

### 1. Create PostgreSQL Database on Railway

```bash
railway login
cd /Users/travisganz/coffee_LLM
railway init
railroad add  # Select PostgreSQL
```

Once created, Railway shows you a connection string. Save it somewhere.

### 2. Export Your Local Database → Railway

```bash
# Backup your local data
pg_dump -U coffee -h localhost coffee_platform > backup.sql

# Connect to Railway PostgreSQL and import data
# Replace CONNECTION_STRING with your Railway Postgres URL
psql CONNECTION_STRING < backup.sql
```

### 3. Deploy public-site to Railway

In Railway dashboard:
- Click **+ New** → **GitHub Repo**
- Select coffee_LLM repo
- Set root directory: `apps/public-site`
- Add environment variable:
  ```
  DATABASE_URL=<your-railway-postgres-connection-string>
  ```
- Click Deploy

### 4. Verify It Works

Once deployed, Railway gives you a public URL (something like `public-site-prod-xxx.up.railway.app`).

Visit it and you should see:
- Coffee browsing works
- Search works
- Roaster listings work
- Price comparisons work (shows current prices from database)

## Local Development

### Setup

```bash
# Make sure PostgreSQL is running locally
# Then:
cd /Users/travisganz/coffee_LLM

# Terminal 1: Start admin-app + API
pnpm dev  # Starts all services

# Terminal 2: Start public-site (separate to avoid db connection pooling)
cd apps/public-site
npm run dev  # Connects to local PostgreSQL
```

### Testing

1. Go to http://localhost:3001 (admin-app)
   - Enter new coffee data
   - Manage products
   
2. Go to http://localhost:3000 (public-site)
   - Should see your data immediately
   - This queries the local database

### Syncing Data to Railway

When you want to push your local data to the live site:

```bash
# Export local DB
pg_dump -U coffee -h localhost coffee_platform > backup.sql

# Import to Railway
psql $RAILWAY_DATABASE_URL < backup.sql

# Done! Your live site now has the latest data
```

## Environment Variables

### For public-site (both local and Railway):

```
DATABASE_URL=postgresql://user:password@host:port/database
```

That's it! No API keys, no CORS complexity.

## Cost on Railway

- **PostgreSQL:** $7/month (+ $1/GB data transfer)
- **Next.js frontend:** $2/month (with $5 monthly credit, you stay free for 2-3 months)
- **Total:** ~$9/month after free credit runs out, or free for first month

## Limitations (for Now)

These features are read-only (not working yet with direct DB):
- Price history charts (placeholder)
- Taste profile / flavor families (placeholder)
- Similar coffee recommendations (placeholder)

**These can be added later** by querying the price_history table and flavor_tags table directly.

## Troubleshooting

### "Error: connect ECONNREFUSED"
- Make sure PostgreSQL is running locally: `psql -U coffee -h localhost coffee_platform -c "SELECT 1"`
- Or make sure Railway Postgres connection string is correct

### "SSL error"
- Railway requires SSL for Postgres connections. The `pg` library handles this automatically.
- If issues persist, add `?sslmode=require` to the connection string

### "No data showing on public-site"
- Check that you exported and imported the data: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM canonical_beans"`
- Verify the connection string is correct in Railway dashboard

---

## Next Steps

1. **Immediate (today):** 
   - Deploy PostgreSQL to Railway
   - Export local data and import to Railway
   - Deploy public-site
   - Test that it works

2. **This week:**
   - Share public-site URL with testers
   - Continue entering data via local admin-app
   - Sync data weekly to Railway

3. **Later (optional):**
   - Implement price history display
   - Add taste profile queries
   - Deploy admin-app to Railway for collaborative data entry
   - Deploy API for advanced features
