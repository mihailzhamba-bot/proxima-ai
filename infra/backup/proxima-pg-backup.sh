#!/usr/bin/env bash
# Local dumps are plain gzip.  age encryption is used only for the S3 copy.
set -euo pipefail

readonly BACKUP_DIR="/var/backups/proxima"
readonly SECRETS_DIR="/etc/proxima-ai/secrets"
readonly COMPOSE_DIR="/srv/proxima-ai/repo"
readonly RAW_DIR="${PROXIMA_RAW_DIR:?PROXIMA_RAW_DIR must be set}"
readonly DATE_TAG="$(date +%F)"

mkdir -p "$BACKUP_DIR"
cd "$COMPOSE_DIR"

backup_database() {
  local database="$1" output="$BACKUP_DIR/${DATE_TAG}-${database}.sql.gz"
  docker compose exec -T postgres sh -ceu '
    exec pg_dump -U "$(cat /run/secrets/postgres_user)" "$1"
  ' sh "$database" | gzip -c > "$output"
  printf 'OK local %s (%s)\n' "$database" "$(du -h "$output" | awk '{print $1}')"
}

backup_database proxima

raw_output="$BACKUP_DIR/${DATE_TAG}-raw.tar.gz"
tar -C "$(dirname "$RAW_DIR")" -czf "$raw_output" "$(basename "$RAW_DIR")"
printf 'OK local raw (%s)\n' "$(du -h "$raw_output" | awk '{print $1}')"

find "$BACKUP_DIR" -type f -name '*.gz' -mtime +14 -delete
