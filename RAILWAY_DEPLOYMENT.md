# Railway Deployment Checklist - Coffee Platform

**Status:** Ready to Deploy  
**Date:** 2026-06-16  
**Backup:** ✅ `/backups/coffee_20260616_201354.sql.gz` (4.4MB)

---

## Pre-Deployment Verification

- ✅ Production build successful: `pnpm --filter public-site build`
- ✅ Frontend server tested: http://localhost:3000 loads correctly
- ✅ Database backup created: 4.4MB compressed (~60MB uncompressed)
- ✅ Docker services running: PostgreSQL, Redis, API
- ✅ railway.toml configured
- ✅ Environment variables documented

---

## One-Command Railway Deployment

### Step 1: Authenticate (Choose One)

**Option A: With API Token**
```bash
export RAILWAY_TOKEN="your-token-here"
railway login --token $RAILWAY_TOKEN
```

**Option B: Browser Login**
```bash
railway login
# Opens browser for authentication
```

**Option C: Already Authenticated**
```bash
railway whoami  # Verify existing auth
```

### Step 2: Initialize Railway Project
```bash
cd /Users/travisganz/coffee_LLM
railway init
# Select or create a project named "coffee-platform"
```

### Step 3: Add PostgreSQL Database
```bash
railway add
# Select: PostgreSQL
# Railway auto-creates and configures the database
```

### Step 4: Get Database Connection String
```bash
railway variables DATABASE_URL
# Copy the output — you'll need it for the next step
```

### Step 5: Restore Database Backup
```bash
# Set the connection string as an environment variable
export PROD_DATABASE_URL="<paste-railway-database-url-here>"

# Restore the backup
./scripts/restore-database.sh backups/coffee_20260616_201354.sql.gz prod
# When prompted, type: yes
```

### Step 6: Deploy Frontend
```bash
railway up
# Deploys using railway.toml configuration
# Public URL will be shown after deployment completes
```

---

## Manual Deployment (If Needed)

### Via Railway Dashboard (GUI)

1. Go to https://railway.app/dashboard
2. Create new project → Select "GitHub Repo" → Choose `coffee_LLM`
3. Configure:
   - **Root Directory:** `apps/public-site`
   - **Build Command:** `pnpm --filter public-site build` (auto-detected)
   - **Start Command:** `pnpm --filter public-site start` (auto-detected from railway.toml)
   - **Environment Variables:**
     - `DATABASE_URL` = Your PostgreSQL connection string
     - `NODE_ENV` = `production`
4. Click "Deploy"

---

## Post-Deployment Verification

### Immediate Checks (5 minutes)
```bash
# 1. Check deployment status
railway status

# 2. View deployment logs
railway logs

# 3. Test homepage loads
curl https://<your-railway-domain>/

# 4. Test API endpoint
curl 'https://<your-railway-domain>/api/roasters?page_size=1'
```

### Manual Testing
1. Open your Railway domain in a browser
2. Verify homepage loads (Grounds title, navigation visible)
3. Navigate to /coffees (should load coffee listings)
4. Search for a coffee (should return results if database restored)
5. Click on a coffee to view details (should show pricing, origins, etc.)

### Monitoring
- Railway Dashboard: https://railway.app/dashboard → Select your project
- View logs in real-time: `railway logs --tail`
- Monitor database: PostgreSQL service logs in Railway dashboard

---

## Troubleshooting

### "Build failed" Error
**Solution:** Ensure NODE_ENV is not set locally (Railway sets it automatically)
```bash
unset NODE_ENV
railway up
```

### "Cannot find module" in Build
**Solution:** Clear node_modules and reinstall
```bash
rm -rf node_modules pnpm-lock.yaml
pnpm install
railway up
```

### API Returns "Failed to fetch roasters"
**Cause:** DATABASE_URL not set or database not seeded
**Solution:** 
1. Verify DATABASE_URL in Railway variables: `railway variables`
2. Restore database backup: `./scripts/restore-database.sh ... prod`
3. Check database connection: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM canonical_beans;"`

### Slow Page Loads
**Solution:** Database query optimization
1. Check largest tables: `railway logs` → look for query slowness
2. Verify indexes exist on canonical_beans, bean_listing tables
3. Add `?ssl=require` to DATABASE_URL if missing

---

## Database Management

### Backup Production Database
```bash
# Pull current production database
pg_dump $RAILWAY_DATABASE_URL > backup_prod_$(date +%Y%m%d).sql
gzip backup_prod_$(date +%Y%m%d).sql
```

### Restore Backup to Production
```bash
./scripts/restore-database.sh <backup-file.sql.gz> prod
```

### Set Up Weekly Automatic Backups
```bash
# Add to crontab
0 2 * * 0 cd /Users/travisganz/coffee_LLM && ./scripts/backup-database.sh

# Run: crontab -e
```

---

## Environment Variables Required

| Variable | Required | Value | Source |
|----------|----------|-------|--------|
| `DATABASE_URL` | ✅ YES | `postgresql://user:pass@host:port/db?sslmode=require` | Railway PostgreSQL service |
| `NODE_ENV` | ❌ NO | `production` | Auto-set by Railway |
| `NEXT_PUBLIC_API_URL` | ❌ NO | Leave unset (defaults to `/api`) | Not needed |

---

## Cost Breakdown

| Service | Plan | Cost |
|---------|------|------|
| Frontend (Next.js) | Included | Included in Railway credit |
| PostgreSQL Database | Premium | $7-10/month |
| **Total** | - | **~$7-10/month** |

**Railway Free Trial:** 5$ credit per month for first 3 months

---

## Support & Next Steps

### If Deployment Succeeds
1. ✅ Share domain URL with users
2. ✅ Set up weekly backup schedule
3. ✅ Monitor logs for errors
4. ✅ (Optional) Deploy admin panel later

### If You Need Help
1. Check Railway logs: `railway logs`
2. Verify DATABASE_URL: `railway variables`
3. Test database connection locally first
4. Review this guide's troubleshooting section

---

## Architecture on Railway

```
┌─────────────────────────────────────────────────────────┐
│                    Railway Platform                      │
├─────────────────────────────────────────────────────────┤
│  Service: public-site (Next.js)                         │
│  ├─ Port: 3000 (internal)                              │
│  ├─ Start: pnpm --filter public-site start            │
│  └─ Root: apps/public-site                            │
├─────────────────────────────────────────────────────────┤
│  Service: PostgreSQL (pgvector/pgvector:pg16)          │
│  ├─ Port: 5432                                          │
│  ├─ Database: railway-assigned                          │
│  └─ Size: ~60MB (your backup data)                     │
├─────────────────────────────────────────────────────────┤
│  Public URL: <your-project>.railway.app               │
└─────────────────────────────────────────────────────────┘
```

---

**Ready to deploy! Run `railway init` when you're ready.** 🚀
