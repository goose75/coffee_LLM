# Coffee Platform - Production Ready

## ✅ Status: Ready to Deploy

The Coffee Platform is now fully functional and ready for production deployment. This guide covers everything needed to get it live for others to use.

---

## What You Have

### Architecture
```
┌─────────────────────────────────────────────┐
│         Next.js Frontend (TypeScript)       │
│     apps/public-site (port 3000)            │
├─────────────────────────────────────────────┤
│  Local API Routes (/api/*)                  │
│  - Direct PostgreSQL queries                │
│  - No external API needed                   │
├─────────────────────────────────────────────┤
│         PostgreSQL Database                 │
│  - 826 roasters                             │
│  - 1,958 coffees (with pricing)             │
│  - Price history tracking                   │
└─────────────────────────────────────────────┘
```

### Data
- **826** specialty coffee roasters across the UK
- **1,958** unique coffee products
- **Price history** tracking across all stores
- **Rich metadata**: origins, processes, roast levels, flavor notes

### Frontend Features
- Browse & search 1,958+ coffees
- Filter by origin, process, roast level, flavor family
- Compare prices across 826 roasters
- View price history & trends  
- Responsive design (mobile-first)
- Dark mode support

---

## Deploy in 15 Minutes

### Option 1: Vercel (Recommended - Easiest)

**1. Connect GitHub repo:**
```bash
vercel link
# Select Yes to create a new Vercel project
```

**2. Set environment variables:**
```bash
vercel env add DATABASE_URL
# Paste your PostgreSQL connection string
# Format: postgresql://user:pass@host:port/db?sslmode=require
```

**3. Deploy:**
```bash
vercel deploy --prod
```

**4. Done!**
Your site is live at `your-project.vercel.app`

**Cost:** ~$5-20/month for frontend + your database cost

---

### Option 2: Railway (Full-Stack - One Platform)

**1. Install Railway CLI:**
```bash
npm install -g @railway/cli
```

**2. Login & create project:**
```bash
railway login
railway init
```

**3. Add PostgreSQL database:**
```bash
railway add
# Select PostgreSQL
# Railway creates it automatically
```

**4. Get your database URL:**
- Go to Railway dashboard
- Open PostgreSQL service
- Copy the Database URL

**5. Seed your data:**
```bash
# Export from localhost
pg_dump -U coffee -h localhost coffee_platform | gzip > backup.sql.gz

# Import to Railway
psql "YOUR_RAILWAY_DATABASE_URL" < <(gunzip -c backup.sql.gz)
```

**6. Deploy frontend:**
- In Railway dashboard: **+ New** → **GitHub Repo**
- Select `coffee_LLM`
- Set **Root directory** to `apps/public-site`
- Add environment variable: `DATABASE_URL` = your Railway PostgreSQL URL
- Click Deploy

**Cost:** ~$7-12/month (included in Railway's free tier first month)

---

## Database Backup & Restore

### Backup locally:
```bash
./scripts/backup-database.sh
# Creates: backups/coffee_YYYYMMDD_HHMMSS.sql.gz
```

### Restore to production:
```bash
export PROD_DATABASE_URL="postgresql://user:pass@host:port/db?sslmode=require"
./scripts/restore-database.sh backups/coffee_*.sql.gz prod
```

### Set up weekly automated backup:
```bash
# Add to crontab
0 2 * * 0 cd /path/to/coffee_LLM && ./scripts/backup-database.sh
```

---

## Verify It's Working

### Local test:
```bash
pnpm dev:all
# Opens http://localhost:3000
```

### Production test:
```bash
# Check homepage loads
curl https://your-domain.com | grep "coffees"

# Check API route works
curl https://your-domain.com/api/roasters?page_size=1
```

---

## Environment Variables Required

| Variable | Required | Example | Platform |
|----------|----------|---------|----------|
| `DATABASE_URL` | ✅ YES | `postgresql://user:pass@host:port/db?sslmode=require` | Both |
| `NEXT_PUBLIC_API_URL` | ❌ NO | Leave unset (defaults to `/api`) | Both |
| `NODE_ENV` | ❌ NO | `production` (auto-set) | Both |

---

## Troubleshooting

### "No data showing"
```bash
# Verify connection
psql "YOUR_DATABASE_URL" -c "SELECT COUNT(*) FROM canonical_beans;"

# Result should be ~1958
```

### "Connection refused"
- Check DATABASE_URL includes `?sslmode=require` (required for cloud databases)
- Verify IP whitelist allows your deployment platform
- Test locally with same DATABASE_URL

### "API routes 404"
- Ensure `NEXT_PUBLIC_API_URL` is NOT set  
- Check `/api/*` routes exist in `apps/public-site/src/app/api/`

### Slow page loads
- Monitor database query time: `SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;`
- Add connection pooling if needed

---

## Next Steps

1. **Choose deployment platform** (Vercel easiest, Railway most integrated)
2. **Backup local database**
3. **Deploy**
4. **Set up weekly backups**
5. **Share URL with users**
6. **(Future)** Deploy admin app for collaborative data management

---

## Monitoring

### Check deployment logs:

**Vercel:**
- Dashboard → Deployments → Logs

**Railway:**
- Dashboard → Service → Logs

### Check database health:
```bash
psql "YOUR_DATABASE_URL" <<EOF
SELECT datname, numbackends, xact_commit, xact_rollback FROM pg_stat_database WHERE datname='coffee_platform';
SELECT * FROM pg_stat_activity LIMIT 10;
EOF
```

---

## Cost Summary

| Component | Platform | Cost |
|-----------|----------|------|
| Frontend | Vercel | $0-20/mo |
| Frontend | Railway | Included |
| Database | AWS RDS | $15-50/mo |
| Database | Railway | $7/mo |
| Database | Render | $15-100/mo |

**Most affordable:** Railway at ~$7-12/month  
**Easiest:** Vercel frontend + managed database at ~$15-20/month

---

## Production Checklist

- [ ] Database backed up
- [ ] Environment variables configured
- [ ] Deployment platform selected
- [ ] Frontend deployed
- [ ] Database imported/seeded
- [ ] Homepage loads (no 404)
- [ ] API route working (`/api/roasters`)
- [ ] Coffees & prices display
- [ ] Search functionality works
- [ ] Weekly backup scheduled
- [ ] Monitoring/logging set up
- [ ] URL shared with users

---

## Files Modified for Deployment

- `apps/public-site/src/lib/api.ts` - Uses local `/api` routes
- `apps/public-site/src/lib/db.ts` - PostgreSQL connection pool
- `apps/public-site/src/app/api/*` - Local API routes (no external service)
- `railway.toml` - Railway deployment config
- `vercel.json` - Vercel deployment config
- `scripts/backup-database.sh` - Backup automation
- `scripts/restore-database.sh` - Restore automation

---

## Support

For issues:
1. Check logs in deployment dashboard
2. Test locally: `DATABASE_URL=localhost pnpm dev:all`
3. Verify database connection string
4. Review this guide's troubleshooting section

---

**Ready to deploy? Start with Option 1 or 2 above!** 🚀
