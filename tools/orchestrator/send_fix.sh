#!/bin/bash
# send_fix.sh <conversation-id> <message-file>
# Sends a follow-up message (fix round or resume) into a live conversation.
set -uo pipefail
. "$(dirname "$0")/lib.sh"
CID="${1:?conversation id}"; MSG="${2:?message file}"
[ -f "$MSG" ] || { echo "message file not found" >&2; exit 2; }
BODY="$(mktemp)"; chmod 600 "$BODY"
python3 - "$MSG" "$BODY" <<'PY'
import json, sys
msg, out = sys.argv[1:3]
json.dump({"role": "user", "content": [{"type": "text", "text": open(msg, encoding="utf-8").read()}], "run": True},
          open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY
oh_curl POST "/api/conversations/$CID/events" "$BODY" >/dev/null
RC=$?
rm -f "$BODY"
log_json fix-round "$CID"
exit $RC
