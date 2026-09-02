#!/usr/bin/env bash
# Restore the newest local plain-gzip dump into the disposable proxima_test DB.
set -euo pipefail

readonly BACKUP_DIR="/var/backups/proxima"

[[ $# -eq 1 ]] || { printf '%s\n' "usage: $0 <tenant>" >&2; exit 64; }
tenant="$1"
[[ "$tenant" =~ ^[a-z0-9][a-z0-9_-]{2,63}$ ]] || { printf '%s\n' "restore-check: invalid tenant id" >&2; exit 1; }
[[ -n "${PROXIMA_SECRETS_DIR:-}" ]] || { printf '%s\n' "restore-check: PROXIMA_SECRETS_DIR is required (see infra/jobs.env)" >&2; exit 1; }
[[ -n "${PROXIMA_RAW_DIR:-}" ]] || { printf '%s\n' "restore-check: PROXIMA_RAW_DIR is required (see infra/jobs.env)" >&2; exit 1; }

dump_file="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name '????-??-??-proxima.sql.gz' -print | sort | tail -n 1)"
[[ -n "$dump_file" ]] || { printf '%s\n' "restore-check: no local proxima .sql.gz dump found for ${tenant}" >&2; exit 1; }

compose=(docker compose)
# The single-quoted snippets below run inside the postgres container: $(cat …) and
# "$user" must expand there, not on the host (SC2016 is intentional).
# shellcheck disable=SC2016
"${compose[@]}" exec -T postgres sh -ceu '
  user=$(cat /run/secrets/postgres_user)
  psql -v ON_ERROR_STOP=1 -U "$user" -d postgres \
    -c "DROP DATABASE IF EXISTS proxima_test" \
    -c "CREATE DATABASE proxima_test"
'
# shellcheck disable=SC2016
gunzip -c "$dump_file" | "${compose[@]}" exec -T postgres sh -ceu '
  exec psql -v ON_ERROR_STOP=1 -U "$(cat /run/secrets/postgres_user)" -d proxima_test
'
# shellcheck disable=SC2016
"${compose[@]}" exec -T postgres sh -ceu '
  exec psql -v ON_ERROR_STOP=1 -U "$(cat /run/secrets/postgres_user)" -d proxima_test \
    -c "SELECT count(*) FROM fact_cabinet_daily_current"
'
