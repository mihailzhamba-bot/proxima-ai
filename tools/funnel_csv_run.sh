#!/usr/bin/env bash
# Story 3.3 / AD-5: weekly async CSV download (owner, control-plane-admin)
# followed by promotion (least-privilege collector). No secret value is passed.
set -euo pipefail

readonly REPOSITORY_DIR="/srv/proxima-ai/repo"

usage() {
  printf '%s\n' "usage: $0 <tenant> [--dry-run]" >&2
  exit 64
}

fail() {
  printf '%s\n' "funnel_csv_run: $*" >&2
  exit 1
}

[[ $# -ge 1 && $# -le 2 ]] || usage
tenant="$1"
shift
dry_run=false
if [[ $# -eq 1 && "$1" == "--dry-run" ]]; then
  dry_run=true
elif [[ $# -ne 0 ]]; then
  usage
fi
[[ "$tenant" =~ ^[a-z0-9][a-z0-9_-]{2,63}$ ]] || fail "invalid tenant id"

secrets_dir="${PROXIMA_SECRETS_DIR:-/etc/proxima-ai/secrets}"
analytics_token="${secrets_dir}/${tenant}_wb_analytics_token"
raw_dir="${PROXIMA_RAW_DIR:-}"
spool_dir="${raw_dir}/wb-async-spool"

if [[ "$dry_run" == true ]]; then
  printf '%s\n' "phase 1: docker compose --profile jobs run --rm control-plane-admin python tools/wb_async_report.py --env-file infra/jobs.env --tenant-id ${tenant} --period latest-closed-week"
  printf '%s\n' "phase 2: docker compose --profile jobs run --rm collector npm run funnel-csv-promote -- --tenant ${tenant}"
  exit 0
fi

[[ -n "${PROXIMA_SECRETS_DIR:-}" ]] || fail "PROXIMA_SECRETS_DIR is required (see infra/jobs.env)"
[[ -n "$raw_dir" ]] || fail "PROXIMA_RAW_DIR is required (see infra/jobs.env)"
[[ -d "$REPOSITORY_DIR" ]] || fail "repository is missing: $REPOSITORY_DIR"
[[ -r "$analytics_token" ]] || fail "tenant analytics token file is missing or unreadable"
install -d -m 0700 -o 1010 -g 1010 "$spool_dir"

cd "$REPOSITORY_DIR"
git_sha="$(git rev-parse HEAD)"
admin_image="$(docker compose --profile jobs images -q control-plane-admin | head -n 1)"
collector_image="$(docker compose --profile jobs images -q collector | head -n 1)"
[[ -n "$admin_image" ]] || fail "control-plane-admin image is not available"
[[ -n "$collector_image" ]] || fail "collector image is not available"
admin_image="$(docker image inspect -f '{{.Id}}' "$admin_image")"
collector_image="$(docker image inspect -f '{{.Id}}' "$collector_image")"

# Phase 1 owns report creation by the explicit AD-11 exception. Both mounted
# paths contain data, not command-line values, and are readable by UID 1010.
docker compose --profile jobs run --rm \
  --env "PROXIMA_GIT_SHA=$git_sha" --env "PROXIMA_IMAGE_ID=$admin_image" \
  --volume "$analytics_token:/run/secrets/wb_analytics_token:ro" \
  --volume "$spool_dir:/work/wb-async-spool" \
  control-plane-admin python tools/wb_async_report.py \
  --env-file infra/jobs.env --tenant-id "$tenant" --period latest-closed-week

# Phase 2 always runs after phase 1 and also remains independently replayable
# from the durable task rows after delete_run.py removes its previous run.
docker compose --profile jobs run --rm \
  --env "PROXIMA_GIT_SHA=$git_sha" --env "PROXIMA_IMAGE_ID=$collector_image" \
  collector \
  npm run funnel-csv-promote -- --tenant "$tenant"
