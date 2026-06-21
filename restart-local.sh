#!/bin/bash

# Coffee LLM - Local Development Restart Script
# Kills all processes, clears caches, and rebuilds from main
# ─────────────────────────────────────────────────────────────────────────────

set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo "🔄 Coffee LLM Local Restart"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ──────────────────────────────────────────────────────────────────────────────
# 1. Kill all running processes
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "📍 Step 1: Killing all running processes..."

# Kill any processes on ports 3000 and 3001
for port in 3000 3001; do
  if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  → Killing process on port $port..."
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
  fi
done
sleep 1

# Kill any Node.js processes (public-site dev server, admin-app dev server)
if pgrep -f "node.*public-site\|node.*admin-app\|next.*dev" > /dev/null 2>&1; then
  echo "  → Killing Node.js dev servers..."
  pkill -f "node.*public-site\|node.*admin-app\|next.*dev" || true
  sleep 1
fi

# Kill any pnpm processes
if pgrep -f "pnpm" > /dev/null 2>&1; then
  echo "  → Killing pnpm processes..."
  pkill -f "pnpm" || true
  sleep 1
fi

# Stop Docker containers
echo "  → Stopping Docker containers..."
docker compose down --remove-orphans 2>/dev/null || true
sleep 2

echo "  ✓ All processes killed"

# ──────────────────────────────────────────────────────────────────────────────
# 2. Clear caches and build artifacts
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "📍 Step 2: Clearing caches and build artifacts..."

# Clear Node modules
if [ -d "node_modules" ]; then
  echo "  → Removing node_modules..."
  rm -rf node_modules
fi

if [ -d "apps/public-site/node_modules" ]; then
  echo "  → Removing public-site/node_modules..."
  rm -rf apps/public-site/node_modules
fi

if [ -d "apps/admin-app/node_modules" ]; then
  echo "  → Removing admin-app/node_modules..."
  rm -rf apps/admin-app/node_modules
fi

# Clear Next.js build artifacts
echo "  → Removing .next caches..."
find apps -name ".next" -type d -exec rm -rf {} + 2>/dev/null || true
find apps -name ".turbo" -type d -exec rm -rf {} + 2>/dev/null || true

# Clear pnpm cache
echo "  → Clearing pnpm store..."
pnpm store prune 2>/dev/null || true

# Clear pnpm lockfile cache
if [ -d ".pnpm-store" ]; then
  rm -rf .pnpm-store
fi

# Clear TypeScript build cache
find . -name "tsconfig.tsbuildinfo" -delete 2>/dev/null || true

echo "  ✓ Caches cleared"

# ──────────────────────────────────────────────────────────────────────────────
# 3. Update branch (or checkout main if needed)
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "📍 Step 3: Ensuring on main branch..."

# Stash any uncommitted changes
if ! git diff-index --quiet HEAD --; then
  echo "  → Stashing uncommitted changes..."
  git stash
fi

# Check if we're already on main
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "main" ]; then
  echo "  → Already on main branch, pulling latest..."
  git pull origin main 2>/dev/null || git pull
else
  # Try to checkout main (may fail if in worktree, that's okay)
  echo "  → Checking out main branch..."
  git checkout main 2>/dev/null || echo "  → (Note: in worktree, skipping checkout)"
  git pull origin main 2>/dev/null || git pull
fi

echo "  ✓ On main branch, up to date"

# ──────────────────────────────────────────────────────────────────────────────
# 4. Install dependencies
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "📍 Step 4: Installing dependencies..."

echo "  → Installing root dependencies..."
pnpm install --frozen-lockfile

echo "  → Installing workspace dependencies..."
pnpm --filter public-site install
pnpm --filter admin-app install

echo "  ✓ Dependencies installed"

# ──────────────────────────────────────────────────────────────────────────────
# 5. Start Docker services (postgres, redis, api, admin-app)
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "📍 Step 5: Starting Docker services..."
echo "  → Starting postgres, redis, api, admin-app..."

docker compose up -d postgres redis api admin-app

echo "  → Waiting for services to be healthy..."
sleep 10

# Check if services are running
if docker ps | grep -q "coffee_postgres"; then
  echo "  ✓ PostgreSQL is running"
else
  echo "  ✗ PostgreSQL failed to start"
  exit 1
fi

if docker ps | grep -q "coffee_api"; then
  echo "  ✓ API is running"
else
  echo "  ✗ API failed to start"
  exit 1
fi

if docker ps | grep -q "coffee_admin"; then
  echo "  ✓ Admin app is running"
else
  echo "  ✗ Admin app failed to start"
  exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# 6. Start local dev servers
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "📍 Step 6: Starting local development servers..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Ready! Starting public-site and admin-app..."
echo ""
echo "Access points:"
echo "  → Public Site:  http://localhost:3000"
echo "  → Admin App:    http://localhost:3001"
echo "  → API:          http://localhost:8000"
echo "  → PostgreSQL:   localhost:5432"
echo "  → Redis:        localhost:6379"
echo ""
echo "To stop, press Ctrl+C"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run both dev servers concurrently
pnpm dev:all
