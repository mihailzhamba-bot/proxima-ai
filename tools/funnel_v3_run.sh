#!/usr/bin/env bash
# Story 3.1 (CR to AD-6, decision 4a): the daily WB funnel v3 job runs as its
# own systemd unit (proxima-funnel-v3@<tenant>, 06:15 Europe/Moscow) with its
# own OnFailure alert. It is deliberately NOT a step of morning_run.sh: its
# failure must not cancel the morning brief, and vice versa.
set -euo pipefail

readonly REPOSITORY_DIR="/srv/proxima-ai/repo"

usage() {
  printf '%s\n' "usage: $0 <tenant> [--allow-analytics-read-write] [--dry-run]" >&2
  exit 64
}

fail() {
  printf '%s\n' "funnel_v3_run: $*" >&2
  exit 1
}

[[ $# -ge 1 && $# -le 3 ]] || usage
tenant="$1"
shift
dry_run=false
allow_read_write=false
if [[ "${PROXIMA_FUNNEL_V3_ALLOW_ANALYTICS_READ_WRITE:-}" == "1" ]]; then
  allow_read_write=true
fi
for option in "$@"; do
  case "$option" in
    --dry-run) dry_run=true ;;
    # PA-13: the server analytics token is still read-write; the job refuses
    # it unless this opt-in is passed explicitly or by the temporary systemd
    # drop-in (never by the base unit).
    --allow-analytics-read-write) allow_read_write=true ;;
    *) usage ;;
  esac
done
[[ "$tenant" =~ ^[a-z0-9][a-z0-9_-]{2,63}$ ]] || fail "invalid tenant id"

secrets_dir="${PROXIMA_SECRETS_DIR:-/etc/proxima-ai/secrets}"
analytics_token="${secrets_dir}/${tenant}_wb_analytics_token"
job_args=(--tenant "$tenant" --analytics-token-file "$analytics_token")
if [[ "$allow_read_write" == true ]]; then
  job_args+=(--allow-analytics-read-write)
fi

if [[ "$dry_run" == true ]]; then
  printf '%s\n' "docker compose --profile jobs run --rm collector npm run funnel-v3 -- ${job_args[*]}"
  exit 0
fi

[[ -n "${PROXIMA_SECRETS_DIR:-}" ]] || fail "PROXIMA_SECRETS_DIR is required (see infra/jobs.env)"
[[ -n "${PROXIMA_RAW_DIR:-}" ]] || fail "PROXIMA_RAW_DIR is required (see infra/jobs.env)"
[[ -d "$REPOSITORY_DIR" ]] || fail "repository is missing: $REPOSITORY_DIR"
[[ -r "$analytics_token" ]] || fail "tenant analytics token file is missing or unreadable"
cd "$REPOSITORY_DIR"
git_sha="$(git rev-parse HEAD)"
image_id="$(docker compose --profile jobs images -q collector | head -n 1)"
[[ -n "$image_id" ]] || fail "collector image is not available"
image_id="$(docker image inspect -f '{{.Id}}' "$image_id")"
# AD-6: env provenance as in morning_run.sh; the job command follows the
# collector Dockerfile contract (`npm run <job> -- …`).
PROXIMA_GIT_SHA="$git_sha" PROXIMA_IMAGE_ID="$image_id" \
  docker compose --profile jobs run --rm collector npm run funnel-v3 -- "${job_args[@]}"
