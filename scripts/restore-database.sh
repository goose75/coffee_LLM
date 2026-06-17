#!/bin/bash

# Coffee Platform Database Restore Script
# Usage: ./scripts/restore-database.sh <backup-file> [target-database-url]
# Examples:
#   ./scripts/restore-database.sh backups/coffee_20260613.sql.gz         # Restore to localhost
#   ./scripts/restore-database.sh backups/coffee_20260613.sql.gz prod    # Restore to PROD_DATABASE_URL

set -e

if [ -z "$1" ]; then
    echo "❌ Error: Backup file required"
    echo "Usage: ./scripts/restore-database.sh <backup-file> [target]"
    echo "Example: ./scripts/restore-database.sh backups/coffee_20260613.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
TARGET="${2:-local}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Error: File not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will OVERWRITE the target database!"
echo "File: $BACKUP_FILE"

if [ "$TARGET" = "prod" ] || [ "$TARGET" = "remote" ]; then
    if [ -z "$PROD_DATABASE_URL" ]; then
        echo "❌ Error: PROD_DATABASE_URL not set"
        exit 1
    fi
    echo "Target: PRODUCTION ($PROD_DATABASE_URL)"
    read -p "Type 'yes' to confirm: " confirm
    [ "$confirm" = "yes" ] || exit 1

    # Decompress if needed
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        TEMP_FILE="${BACKUP_FILE%.gz}"
        gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
        RESTORE_FILE="$TEMP_FILE"
    else
        RESTORE_FILE="$BACKUP_FILE"
    fi

    echo "Restoring to PRODUCTION..."
    psql "$PROD_DATABASE_URL" < "$RESTORE_FILE"

    # Cleanup temp file
    [ -f "$TEMP_FILE" ] && rm "$TEMP_FILE"
else
    echo "Target: localhost"
    read -p "Type 'yes' to confirm: " confirm
    [ "$confirm" = "yes" ] || exit 1

    # Decompress if needed
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        TEMP_FILE="${BACKUP_FILE%.gz}"
        gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
        RESTORE_FILE="$TEMP_FILE"
    else
        RESTORE_FILE="$BACKUP_FILE"
    fi

    echo "Restoring to localhost..."
    psql -U coffee -h localhost -d coffee_platform < "$RESTORE_FILE"

    # Cleanup temp file
    [ -f "$TEMP_FILE" ] && rm "$TEMP_FILE"
fi

echo "✅ Restore complete!"
