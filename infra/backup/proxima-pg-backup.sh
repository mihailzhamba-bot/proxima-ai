#!/bin/bash
# Nightly pg_dump: pilot proxima + proxima_dev -> local (retention 14d) + age-encrypted -> S3 proxima-backups (ru-3)
set -uo pipefail
SEC=/etc/proxima-ai/secrets
PGUSER=$(cat $SEC/postgres_user)
AGE_PUB=$(cat $SEC/backup_age_recipient)
BACKUP_DIR=/var/backups/proxima
STAMP=$(date +%F)
mkdir -p "$BACKUP_DIR"
for db in proxima; do
  F="$BACKUP_DIR/${STAMP}-${db}.sql.gz"
  if docker exec proxima-ai-postgres-1 pg_dump -U "$PGUSER" "$db" | gzip > "$F"; then
    echo "$(date -Is) OK local $db ($(du -h "$F" | cut -f1))"
  else
    echo "$(date -Is) FAIL local $db" >&2; continue
  fi
  if age -r "$AGE_PUB" "$F" > "$F.age" 2>/dev/null && s3cmd put "$F.age" "s3://proxima-backups/${STAMP:0:7}/${STAMP}-${db}.sql.gz.age" >/dev/null 2>&1; then
    echo "$(date -Is) OK s3 ${STAMP}-${db}.sql.gz.age"
    rm -f "$F.age"
  else
    echo "$(date -Is) FAIL s3 $db (local copy kept)" >&2
  fi
done
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +14 -delete
find "$BACKUP_DIR" -name "*.age" -mtime +3 -delete
# dev db (rootless container in agent zone)
F="$BACKUP_DIR/${STAMP}-proxima_dev.sql.gz"
if DOCKER_HOST=unix:///run/user/1002/docker.sock docker exec proxima-dev pg_dump -U proxima_dev proxima_dev | gzip > "$F" 2>/dev/null; then
  echo "$(date -Is) OK local proxima_dev ($(du -h "$F" | cut -f1))"
  if age -r "$AGE_PUB" "$F" > "$F.age" 2>/dev/null && s3cmd put "$F.age" "s3://proxima-backups/${STAMP:0:7}/${STAMP}-proxima_dev.sql.gz.age" >/dev/null 2>&1; then
    echo "$(date -Is) OK s3 ${STAMP}-proxima_dev"; rm -f "$F.age"
  fi
else
  echo "$(date -Is) SKIP proxima_dev (zone down?)" >&2
fi
