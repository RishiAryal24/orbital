#!/usr/bin/env bash
# =============================================================
# PyLoom Technologies — Database Restore Utility
# Restores a PostgreSQL database from Cloudflare R2 / AWS S3 backup.
#
# Usage:
#   bash scripts/restore-db.sh
#   bash scripts/restore-db.sh 2026-09-24T15-00-00Z
#
# Environment variables:
#   BACKUP_BUCKET (default: pyloom-backups)
#   R2_ENDPOINT_URL (optional: https://<account_id>.r2.cloudflarestorage.com)
#   DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
# =============================================================
set -euo pipefail

BUCKET="${BACKUP_BUCKET:-pyloom-backups}"
DB_NAME="${DB_NAME:?Set DB_NAME env var}"
DB_USER="${DB_USER:?Set DB_USER env var}"
DB_PASSWORD="${DB_PASSWORD:?Set DB_PASSWORD env var}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

ENDPOINT_FLAG=""
if [ -n "${R2_ENDPOINT_URL:-}" ]; then
  ENDPOINT_FLAG="--endpoint-url ${R2_ENDPOINT_URL}"
fi

list_backups() {
  echo "Available backups in s3://$BUCKET/backups/:"
  aws s3 ls "s3://$BUCKET/backups/" ${ENDPOINT_FLAG} \
    | awk '{print $4}' | grep "\.sql\.gz$" | sort -r | head -20
}

if [ $# -eq 0 ]; then
  list_backups
  echo ""
  echo "Usage: $0 <TIMESTAMP>"
  echo "  e.g. $0 2026-09-24T15-00-00Z"
  exit 0
fi

TIMESTAMP="$1"
FILENAME="pyloom-backup-${TIMESTAMP}.sql.gz"
S3_KEY="s3://$BUCKET/backups/$FILENAME"
TMPFILE="/tmp/$FILENAME"

echo "⬇️  Downloading $S3_KEY …"
aws s3 cp "$S3_KEY" "$TMPFILE" ${ENDPOINT_FLAG}

echo "⚠️  This will DROP and recreate the database: $DB_NAME on $DB_HOST"
read -r -p "  Are you sure? Type 'yes' to continue: " confirm
if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  rm -f "$TMPFILE"
  exit 1
fi

export PGPASSWORD="$DB_PASSWORD"

echo "🔄 Recreating $DB_NAME …"
psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
  --dbname=postgres \
  --command="DROP DATABASE IF EXISTS $DB_NAME;" \
  --command="CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "📥 Restoring from backup …"
gunzip -c "$TMPFILE" \
  | psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
         --dbname="$DB_NAME" \
         --single-transaction \
         --set ON_ERROR_STOP=on

rm -f "$TMPFILE"
echo "✅ Database $DB_NAME restored successfully from $FILENAME."
