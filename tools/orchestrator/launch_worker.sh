#!/bin/bash
# launch_worker.sh <branch> <base-ref> <dispatch-file> <fedor|glm>
# Provisions a workspace from the canonical clone and starts an OpenHands
# conversation on it. Prints the conversation id.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

BRANCH="${1:?branch}"; BASE="${2:?base ref}"; DISPATCH="${3:?dispatch file}"; PROFILE_NAME="${4:-fedor}"
case "$PROFILE_NAME" in
  fedor) PROFILE="$PROFILE_FEDOR" ;;
  glm)   PROFILE="$PROFILE_GLM" ;;
  *) echo "unknown profile: $PROFILE_NAME" >&2; exit 2 ;;
esac
[ -f "$DISPATCH" ] || { echo "dispatch file not found" >&2; exit 2; }

CID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
HEX="$(echo "$CID" | tr -d '-')"
WS="${WORKSPACE_ROOT}/${HEX}"
install -d -o openhands-agent -g openhands-agent "$WS" 2>/dev/null || mkdir -p "$WS"

BUNDLE="$(mktemp -u /tmp/conductor-XXXXXX.bundle)"
cgit bundle create "$BUNDLE" --all >/dev/null 2>&1 || { echo "bundle failed" >&2; exit 3; }
git -c safe.directory='*' clone -q "$BUNDLE" "$WS/proxima-ai" || { rm -f "$BUNDLE"; echo "clone failed" >&2; exit 3; }
rm -f "$BUNDLE"

G() { git -C "$WS/proxima-ai" "$@"; }
G checkout -q -b "$BRANCH" "$BASE" || { echo "branch from $BASE failed" >&2; exit 3; }
G remote set-url origin https://github.com/mihailzhamba-bot/proxima-ai.git
# reference docs stay untracked on purpose: workers read them, never stage them
G checkout -q origin/main -- docs/state _bmad-output 2>/dev/null || true
G reset -q -- docs/state _bmad-output 2>/dev/null || true
chown -R openhands-agent:openhands-agent "$WS" 2>/dev/null || true

PAYLOAD="$(mktemp)"; chmod 600 "$PAYLOAD"
python3 - "$CID" "$WS" "$DISPATCH" "$PROFILE" "$PAYLOAD" <<'PY'
import json, sys
cid, ws, dispatch, profile, out = sys.argv[1:6]
json.dump({
    "conversation_id": cid,
    "workspace": {"kind": "LocalWorkspace", "working_dir": ws},
    "agent_profile_id": profile,
    "initial_message": {"role": "user", "content": [{"type": "text", "text": open(dispatch, encoding="utf-8").read()}], "run": True},
    "max_iterations": 500,
    "stuck_detection": True,
    "confirmation_policy": {"kind": "NeverConfirm"},
    "autotitle": True,
}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY
RESP="$(oh_curl POST /api/conversations "$PAYLOAD")"
rm -f "$PAYLOAD"
echo "$RESP" | grep -q '"id"' || { echo "create failed: $(echo "$RESP" | head -c 200)" >&2; exit 4; }

# a conversation may come back idle; nudge it once
sleep 5
if [ "$(conversation_status "$CID")" = "idle" ]; then
  EMPTY="$(mktemp)"; echo '{}' >"$EMPTY"
  oh_curl POST "/api/conversations/$CID/run" "$EMPTY" >/dev/null
  rm -f "$EMPTY"
fi
log_json launch "$BRANCH via $PROFILE_NAME" >&2
echo "$CID"
