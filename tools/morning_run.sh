#!/usr/bin/env bash
# Run the implemented morning jobs in order.  Later epics append their steps here.
set -euo pipefail

readonly REPOSITORY_DIR="/srv/proxima-ai/repo"

usage() {
  printf '%s\n' "usage: $0 <tenant> [--dry-run]" >&2
  exit 64
}

fail() {
  printf '%s\n' "morning_run: $*" >&2
  exit 1
}

[[ $# -ge 1 && $# -le 2 ]] || usage
tenant="$1"
dry_run=false
if [[ $# -eq 2 ]]; then
  [[ "$2" == "--dry-run" ]] || usage
  dry_run=true
fi
[[ "$tenant" =~ ^[a-z0-9][a-z0-9_-]{2,63}$ ]] || fail "invalid tenant id"

run_collect() {
  local git_sha image_id statistics_token host_statistics_token secrets_dir
  secrets_dir="${PROXIMA_SECRETS_DIR:-/etc/proxima-ai/secrets}"
  host_statistics_token="${secrets_dir}/${tenant}_wb_statistics_token"
  statistics_token="/run/secrets/${tenant}_wb_statistics_token"

  if [[ "$dry_run" == true ]]; then
    printf '%s\n' "docker compose --profile jobs run --rm collector npm run collect -- --tenant ${tenant} --statistics-token-file ${statistics_token}"
    return
  fi

  [[ -n "${PROXIMA_SECRETS_DIR:-}" ]] || fail "PROXIMA_SECRETS_DIR is required (see infra/jobs.env)"
  [[ -n "${PROXIMA_RAW_DIR:-}" ]] || fail "PROXIMA_RAW_DIR is required (see infra/jobs.env)"
  [[ -d "$REPOSITORY_DIR" ]] || fail "repository is missing: $REPOSITORY_DIR"
  [[ -r "$host_statistics_token" ]] || fail "tenant statistics token file is missing or unreadable"
  cd "$REPOSITORY_DIR"
  git_sha="$(git rev-parse HEAD)"
  image_id="$(docker compose --profile jobs images -q collector | head -n 1)"
  [[ -n "$image_id" ]] || fail "collector image is not available"
  image_id="$(docker image inspect -f '{{.Id}}' "$image_id")"
  PROXIMA_GIT_SHA="$git_sha" PROXIMA_IMAGE_ID="$image_id" \
    docker compose --profile jobs run --rm collector npm run collect -- --tenant "$tenant" \
      --statistics-token-file "$statistics_token"
}

# Control-plane step (AD-6/AD-8/AD-9): one docker compose run per step, the
# NORM_DATABASE_URI_FILE secret arrives through the control-plane service
# definition in infra/compose.yaml; env provenance is the same as collect.
run_control_plane_step() {
  local step_module="$1" git_sha image_id

  if [[ "$dry_run" == true ]]; then
    printf '%s\n' "docker compose --profile jobs run --rm control-plane python -m ${step_module} run --tenant ${tenant}"
    return
  fi

  [[ -n "${PROXIMA_SECRETS_DIR:-}" ]] || fail "PROXIMA_SECRETS_DIR is required (see infra/jobs.env)"
  [[ -d "$REPOSITORY_DIR" ]] || fail "repository is missing: $REPOSITORY_DIR"
  cd "$REPOSITORY_DIR"
  git_sha="$(git rev-parse HEAD)"
  image_id="$(docker compose --profile jobs images -q control-plane | head -n 1)"
  [[ -n "$image_id" ]] || fail "control-plane image is not available"
  image_id="$(docker image inspect -f '{{.Id}}' "$image_id")"
  PROXIMA_GIT_SHA="$git_sha" PROXIMA_IMAGE_ID="$image_id" \
    docker compose --profile jobs run --rm control-plane \
    python -m "$step_module" run --tenant "$tenant"
}

run_norm() {
  run_control_plane_step "proxima_control_plane.norm"
}

run_brief() {
  run_control_plane_step "proxima_control_plane.brief"
}

# Mandatory morning chain (AD-6): collect -> norm -> brief, strictly in order,
# each step is its own run; set -e stops on the first failure.
run_collect
run_norm
run_brief
