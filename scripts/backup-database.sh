#!/bin/bash

# Coffee Platform Database Backup Script
# Usage: ./scripts/backup-database.sh [local|remote]
# Examples:
#   ./scripts/backup-database.sh local          # Backup from localhost
#   ./scripts/backup-database.sh remote         # Backup from PROD_DATABASE_URL

set -e

BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="coffee_${DATE}.sql"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "📦 Starting database backup..."

if [ "$1" = "remote" ]; then
    if [ -z "$PROD_DATABASE_URL" ]; then
        echo "❌ Error: PROD_DATABASE_URL not set"
        exit 1
    fi
    echo "Backing up from PRODUCTION..."
    pg_dump "$PROD_DATABASE_URL" > "$BACKUP_DIR/$FILENAME"
else
    echo "Backing up from localhost..."
    pg_dump -U coffee -h localhost coffee_platform > "$BACKUP_DIR/$FILENAME"
fi

# Compress
gzip "$BACKUP_DIR/$FILENAME"
FINAL_FILE="$BACKUP_DIR/${FILENAME}.gz"

SIZE=$(du -h "$FINAL_FILE" | cut -f1)
echo "✅ Backup complete: $FINAL_FILE ($SIZE)"

# Keep only last 7 backups
echo "🧹 Cleaning old backups..."
ls -t "$BACKUP_DIR"/coffee_*.sql.gz | tail -n +8 | xargs -r rm

echo "📊 Recent backups:"
ls -lh "$BACKUP_DIR"/coffee_*.sql.gz | tail -5 | awk '{print $9, "(" $5 ")"}'
