#!/usr/bin/env bash
set -euo pipefail

readonly SECRETS_DIR="/etc/proxima-ai/secrets"
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

printf '%s\n' \
  "url = \"https://api.telegram.org/bot${token}/sendMessage\"" \
  "data-urlencode = \"chat_id=${chat_id}\"" \
  "data-urlencode = \"text=PROXIMA AI unit failed: $1\"" \
  "fail" "silent" "show-error" "max-time = 20" | curl --config - >/dev/null
