#!/usr/bin/env bash
set -euo pipefail

readonly TENANT_ID="${1:-}"
readonly SOURCE_DIR="${2:-}"
readonly ANALYTICS_ACCESS_FLAG="${3:-}"
readonly REPOSITORY_DIR="/srv/proxima-ai/repo"
readonly SECRETS_DIR="/etc/proxima-ai/secrets"
readonly CONFIG_DIR="/etc/proxima-ai/business-signal"

fail() {
  printf '%s\n' "install-business-signal-inputs: $*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root via sudo"
[[ "${TENANT_ID}" =~ ^[a-z0-9][a-z0-9_-]{2,63}$ ]] || fail "first argument must be the tenant ID"
[[ "${SOURCE_DIR}" == /* && -d "${SOURCE_DIR}" && ! -L "${SOURCE_DIR}" ]] || fail "second argument must be an absolute regular directory"
[[ "$#" -le 3 ]] || fail "expected tenant ID, source directory and optional --allow-analytics-read-write"
[[ -z "${ANALYTICS_ACCESS_FLAG}" || "${ANALYTICS_ACCESS_FLAG}" == "--allow-analytics-read-write" ]] || fail "unknown third argument"
[[ -f "${REPOSITORY_DIR}/services/collector/dist/cli/validate-signal-inputs.js" ]] || fail "build the collector first"
[[ -d "${SECRETS_DIR}" && -d "${CONFIG_DIR}" ]] || fail "prepare the business-signal runtime first"

readonly -a SECRET_FILES=(wb_statistics_token wb_analytics_token wb_finance_token telegram_bot_token)
readonly -a CONFIG_FILES=(founder-chat.json products.csv warehouses.csv)

for filename in "${SECRET_FILES[@]}" "${CONFIG_FILES[@]}"; do
  source_path="${SOURCE_DIR}/${filename}"
  [[ -f "${source_path}" && ! -L "${source_path}" ]] || fail "missing private regular source: ${filename}"
  [[ "$(stat --format '%a' "${source_path}")" == "600" ]] || fail "source must have mode 0600: ${filename}"
done

stage_dir="$(mktemp --directory /etc/proxima-ai/.business-signal-inputs.XXXXXX)"
stage_secrets="${stage_dir}/secrets"
stage_config="${stage_dir}/config"

cleanup() {
  for filename in "${SECRET_FILES[@]}"; do
    [[ ! -f "${stage_secrets}/${filename}" ]] || rm -- "${stage_secrets}/${filename}"
  done
  for filename in "${CONFIG_FILES[@]}"; do
    [[ ! -f "${stage_config}/${filename}" ]] || rm -- "${stage_config}/${filename}"
  done
  rmdir "${stage_secrets}" "${stage_config}" "${stage_dir}" 2>/dev/null || true
}
trap cleanup EXIT

install --directory --mode 0700 --owner proxima-admin --group proxima-admin "${stage_dir}" "${stage_secrets}" "${stage_config}"
for filename in "${SECRET_FILES[@]}"; do
  install --mode 0600 --owner proxima-admin --group proxima-admin "${SOURCE_DIR}/${filename}" "${stage_secrets}/${filename}"
done
for filename in "${CONFIG_FILES[@]}"; do
  install --mode 0600 --owner proxima-admin --group proxima-admin "${SOURCE_DIR}/${filename}" "${stage_config}/${filename}"
done

analytics_access_args=()
[[ -z "${ANALYTICS_ACCESS_FLAG}" ]] || analytics_access_args+=("${ANALYTICS_ACCESS_FLAG}")

validation="$({
  runuser --user proxima-admin -- node "${REPOSITORY_DIR}/services/collector/dist/cli/validate-signal-inputs.js" \
    --tenant "${TENANT_ID}" \
    --statistics-token-file "${stage_secrets}/wb_statistics_token" \
    --analytics-token-file "${stage_secrets}/wb_analytics_token" \
    --finance-token-file "${stage_secrets}/wb_finance_token" \
    --telegram-token-file "${stage_secrets}/telegram_bot_token" \
    --founder-chat-source "${stage_config}/founder-chat.json" \
    --products-csv "${stage_config}/products.csv" \
    --warehouses-csv "${stage_config}/warehouses.csv" \
    "${analytics_access_args[@]}"
} 2>&1)" || fail "validation failed: ${validation}"

for filename in "${SECRET_FILES[@]}"; do
  install --mode 0600 --owner proxima-admin --group proxima-admin "${stage_secrets}/${filename}" "${SECRETS_DIR}/${filename}"
done
for filename in "${CONFIG_FILES[@]}"; do
  install --mode 0600 --owner proxima-admin --group proxima-admin "${stage_config}/${filename}" "${CONFIG_DIR}/${filename}"
done

printf '%s\n' "${validation}"
