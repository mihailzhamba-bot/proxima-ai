#!/usr/bin/env bash
set -euo pipefail

# PROXIMA_ALERT_SECRETS_DIR exists only for offline tests; production path
# is /etc/proxima-ai/secrets (0600), see AGENTS.md.
readonly SECRETS_DIR="${PROXIMA_ALERT_SECRETS_DIR:-/etc/proxima-ai/secrets}"
readonly TOKEN_FILE="${SECRETS_DIR}/telegram_bot_token"
readonly CHAT_ID_FILE="${SECRETS_DIR}/telegram_chat_id"

[[ $# -eq 1 ]] || { printf '%s\n' "usage: $0 <failed-unit>" >&2; exit 64; }
[[ -r "$TOKEN_FILE" && -r "$CHAT_ID_FILE" ]] || {
  printf '%s\n' "proxima-alert: Telegram secret files are unavailable" >&2
  exit 1
}

token="$(tr -d '\r\n' < "$TOKEN_FILE")"
chat_id="$(tr -d '\r\n' < "$CHAT_ID_FILE")"
[[ -n "$token" && -n "$chat_id" ]] || { printf '%s\n' "proxima-alert: empty Telegram secret file" >&2; exit 1; }

# curl config (curl --config -): blank lines and '#' comments are allowed,
# which lets us label the retry settings readably. The runbook (release-m01,
# section 6) verifies the setup with `grep -n retry` on this file and expects
# the "--retry 3 --retry-delay 5" wording, so it is kept as a comment here.
# retry 3 / retry-delay 5 (D25 solution 4a / AD-6): the send is not one-shot.
# curl retries transport errors itself, including max-time timeouts, and
# HTTP responses 408/429/5xx; other 4xx answers (e.g. 401 bad token, 404)
# are not retried — with `fail` they stop the script with exit 22.
# retry-all-errors is deliberately not used: 4xx must stay fail-fast.
printf '%s\n' \
  "url = \"https://api.telegram.org/bot${token}/sendMessage\"" \
  "data-urlencode = \"chat_id=${chat_id}\"" \
  "data-urlencode = \"text=PROXIMA AI unit failed: $1\"" \
  "fail" "silent" "show-error" "max-time = 20" \
  \
  "retry = 3" \
  "retry-delay = 5" | curl --config - >/dev/null
