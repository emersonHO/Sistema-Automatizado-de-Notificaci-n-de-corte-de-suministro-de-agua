#!/bin/sh
# Copia de PostgreSQL al volumen /backups. No borra datos. Conserva 14 días.
set -eu
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="/backups/pg-${STAMP}.sql.gz"
export PGPASSWORD="${POSTGRES_PASSWORD}"
pg_dump -h db -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "$OUT"
sha256sum "$OUT" > "${OUT}.sha256"
find /backups -name 'pg-*.sql.gz' -mtime +14 -delete
find /backups -name 'pg-*.sql.gz.sha256' -mtime +14 -delete
echo "backup_ok $OUT"
