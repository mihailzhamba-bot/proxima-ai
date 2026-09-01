#!/bin/bash
# conductor_digest.sh - morning summary for Mike over the monitor's Telegram bot.
# Reads only local state; never prints secret values (token goes to curl via --config).
set -uo pipefail
. "$(dirname "$0")/lib.sh"

STATE_DIR="${CONDUCTOR_STATE_DIR:-/srv/proxima-ai/conductor}"
SECRETS="${PROXIMA_SECRETS_DIR:-/etc/proxima-ai/secrets}"
TOKEN_FILE="$SECRETS/telegram_bot_token"
CHAT_FILE="$SECRETS/telegram_chat_id"
[ -r "$TOKEN_FILE" ] && [ -r "$CHAT_FILE" ] || { echo "telegram secrets unavailable" >&2; exit 0; }

REPORT="$STATE_DIR/digest.md"
{
  printf 'Сводка Дирижёра %s\n\n' "$(date -u +%Y-%m-%d)"
  if [ -f "$STATE_DIR/state.json" ]; then
    python3 - "$STATE_DIR/state.json" <<'PY'
import json, sys
try:
    s = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    print("состояние недоступно"); raise SystemExit
for key, label in (("merged", "смержено"), ("in_progress", "в работе"),
                   ("blocked", "заблокировано"), ("waiting_mike", "ждёт Mike")):
    items = s.get(key) or []
    if items:
        print(f"{label}: " + ", ".join(str(i) for i in items))
if not any(s.get(k) for k in ("merged", "in_progress", "blocked", "waiting_mike")):
    print("за сутки изменений нет")
PY
  else
    printf 'состояние ещё не создано\n'
  fi
} >"$REPORT"

CFG="$(mktemp)"; chmod 600 "$CFG"
printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$(cat "$TOKEN_FILE")" >"$CFG"
printf 'data-urlencode = "chat_id=%s"\n' "$(cat "$CHAT_FILE")" >>"$CFG"
printf 'data-urlencode = "text@%s"\n' "$REPORT" >>"$CFG"
curl -sS -m 30 --config "$CFG" -o /dev/null
RC=$?
rm -f "$CFG"
exit $RC
