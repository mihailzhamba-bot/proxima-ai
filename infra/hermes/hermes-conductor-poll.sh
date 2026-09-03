#!/bin/bash
# Wakes the Hermes brain when the pipeline has something to say.
# Polls the conductor over the narrow SSH channel; if there are events, drops a
# message into Mike's Telegram chat through Hermes' own bot, so Mike can answer
# right there and Hermes picks the answer up as an ordinary message.
# The bot token never leaves the container: curl runs inside it.
set -uo pipefail
umask 077

KEY=/home/hermes/.hermes/ssh/hermes_conductor
HOSTSPEC=openhands-agent@135.106.186.210
STATE=/home/hermes/.hermes/conductor-poll.json

[ -r "$KEY" ] || { echo "poll: key missing" >&2; exit 1; }

EVENTS="$(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
  -o ConnectTimeout=15 "$HOSTSPEC" poll 2>/dev/null)" || { echo "poll: channel down" >&2; exit 1; }

printf '%s' "$EVENTS" > "$STATE"
COUNT="$(printf '%s' "$EVENTS" | python3 -c "
import json,sys
try: print(json.load(sys.stdin).get('count', 0))
except Exception: print(0)")"
[ "$COUNT" -gt 0 ] 2>/dev/null || exit 0

TEXT="$(printf '%s' "$EVENTS" | python3 -c "
import json,sys
d=json.load(sys.stdin)
lines=['Конвейер PROXIMA AI: события (%d)' % d.get('count',0), '']
kinds={'question':'вопрос воркера','blocked':'блокер','ready':'ветка готова','ci-red':'красный CI','note':'заметка'}
for e in d.get('events', [])[:10]:
    lines.append('- [%s] story %s: %s' % (kinds.get(e.get('kind'), e.get('kind')), e.get('story'), (e.get('text') or '')[:400]))
lines += ['', 'Разбери это как Дирижёр (инструкция /opt/data/skills/proxima-conductor.md): что можешь решить сам - решай и доложи одной строкой, что требует моего решения - спроси.']
print('\n'.join(lines))")"

printf '%s' "$TEXT" | docker exec -i hermes sh -lc '
  CHAT="${TELEGRAM_ALLOWED_USERS%%,*}"
  CFG=$(mktemp); chmod 600 "$CFG"
  printf "url = \"https://api.telegram.org/bot%s/sendMessage\"\n" "$TELEGRAM_BOT_TOKEN" > "$CFG"
  printf "data-urlencode = \"chat_id=%s\"\n" "$CHAT" >> "$CFG"
  printf "data-urlencode = \"text@-\"\n" >> "$CFG"
  curl -sS -m 30 --config "$CFG" -o /dev/null
  rc=$?
  rm -f "$CFG"
  exit $rc'
