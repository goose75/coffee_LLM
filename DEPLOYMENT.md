# Coffee Platform - Production Deployment Guide

## Overview

The Coffee Platform uses a simple, scalable architecture:

```
Frontend (Next.js)  →  PostgreSQL Database
      ↓                    ↑
   /api/* routes    (direct queries)
```

No backend API server needed. The Next.js frontend has built-in API routes that query PostgreSQL directly.

## Quick Deploy (5 minutes)

### Option A: Deploy to Vercel (Recommended for Frontend)

**1. Connect GitHub repo:**
```bash
vercel link
```

**2. Set environment variables in Vercel dashboard:**
```
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
```

**3. Deploy:**
```bash
vercel deploy --prod
```

**4. Test:**
Visit `your-domain.vercel.app` → should show coffees and roasters

### Option B: Deploy to Railway (Full Stack)

**1. Login and initialize:**
```bash
railway login
railway init
```

**2. Add PostgreSQL:**
```bash
railway add
# Select PostgreSQL, Railway will create it
```

**3. Get connection string:**
- Go to Railway dashboard
- Open PostgreSQL service
- Copy Database URL

**4. Import data:**
```bash
pg_dump -U coffee -h localhost coffee_platform | psql "YOUR_RAILWAY_DATABASE_URL"
```

**5. Deploy frontend:**
- Click **+ New** in Railway dashboard
- Select **GitHub Repo**
- Select `coffee_LLM`
- Set **Root directory**: `apps/public-site`
- Railway auto-detects it's a Next.js app
- Click Deploy

**6. Set environment variable:**
- Go to frontend service settings
- Add `DATABASE_URL` = your Railway PostgreSQL URL

**7. Done!**
Railway gives you a live URL

---

## Database Setup

### Export local database:
```bash
pg_dump -U coffee -h localhost coffee_platform --clean > coffee_backup.sql
```

### Import to production:
```bash
psql "postgresql://user:pass@host:port/db?sslmode=require" < coffee_backup.sql
```

### Keep in sync:
```bash
# Weekly backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
pg_dump -U coffee -h localhost coffee_platform > "backups/coffee_$DATE.sql"
psql "$PROD_DATABASE_URL" < "backups/coffee_$DATE.sql"
```

---

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `DATABASE_URL` | YES | `postgresql://user:pass@host:port/db` |
| `NEXT_PUBLIC_API_URL` | NO | `/api` (default - uses local routes) |
| `NODE_ENV` | NO | `production` |

### For SSL connections (required by Railway/Vercel):
Append `?sslmode=require` to DATABASE_URL:
```
postgresql://user:pass@host:port/db?sslmode=require
```

---

## Build for Production Locally

```bash
# Build the frontend
pnpm --filter public-site build

# Test production build
pnpm --filter public-site start

# Visit http://localhost:3000
```

---

## Monitoring & Logs

### Vercel:
- Dashboard → Deployments → Real-time logs
- Check function execution time

### Railway:
- Dashboard → Service → Logs
- Realtime streaming logs

### Database:
```bash
# Check connection pool
SELECT * FROM pg_stat_activity;

# Monitor slow queries
SELECT * FROM pg_stat_statements ORDER BY mean_time DESC;
```

---

## Troubleshooting

### "No data showing"
```bash
# Verify database connection
psql "YOUR_DATABASE_URL" -c "SELECT COUNT(*) FROM canonical_beans;"
```

### "Connection refused"
- Check DATABASE_URL in environment variables
- Verify it includes `?sslmode=require` for cloud databases
- Test connection locally: `psql "YOUR_DATABASE_URL"`

### "API routes 404"
- Ensure `NEXT_PUBLIC_API_URL` is NOT set (uses `/api` by default)
- Check that `/api/*` routes exist in `apps/public-site/src/app/api/`

### "Slow page loads"
- Check database query performance
- Enable query logging in PostgreSQL
- Consider connection pooling (Railway/Vercel handle this)

---

## Deployment Checklist

- [ ] PostgreSQL database created (Railway/AWS/Render)
- [ ] Database URL set in environment variables
- [ ] Local build tested: `pnpm --filter public-site build && pnpm --filter public-site start`
- [ ] Git repository connected to deployment platform
- [ ] Data imported to production database
- [ ] Environment variables configured
- [ ] Deployment triggered
- [ ] Live URL verified (showing data)
- [ ] Database backups scheduled (weekly recommended)

---

## Cost Estimates

### Vercel (Frontend only - you manage database):
- **Next.js deployment:** $0-20/month depending on usage
- **Database (separate):** See below

### Railway (All-inclusive):
- **PostgreSQL:** $7/month
- **Next.js:** Included in free tier or $5/month
- **Total:** ~$7-12/month

### AWS / Render / DigitalOcean (DIY):
- **Managed PostgreSQL:** $15-50/month
- **Compute (if needed):** $5-20/month

---

## Next Steps

1. **Immediate**: Deploy frontend + database
2. **This week**: Set up automated backups
3. **Next week**: Monitor performance and optimize
4. **Later**: Add admin-app for collaborative data management

---

## Support

For issues:
1. Check logs in deployment dashboard
2. Test locally: `pnpm dev:all` with `DATABASE_URL=localhost`
3. Verify database: `psql "YOUR_DATABASE_URL" -c "SELECT 1"`
4. Review this guide's troubleshooting section
