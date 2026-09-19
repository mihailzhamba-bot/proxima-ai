#!/bin/bash
# Shared helpers for the conductor loop (bash 3.2 compatible).
# No secret values are ever printed: the OpenHands key is read into a variable
# and passed through a curl config file on stdin.
set -uo pipefail

OH_BASE="${OH_BASE:-http://127.0.0.1:18000}"
OH_KEY_FILE="${OH_KEY_FILE:-/home/openhands-agent/.agent-canvas.env}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/srv/openhands/persistence/workspace/project}"
CANONICAL_REPO="${CANONICAL_REPO:-/srv/proxima-ai/conductor-repo}"
PROFILE_FEDOR="${PROFILE_FEDOR:-027234ef-bda1-4ce2-bc4a-c363961ea8d1}"
PROFILE_GLM="${PROFILE_GLM:-dca3198c-d56f-4346-940a-b04b9ad049a0}"

# git wrapper for the canonical bare repo (safe.directory: it is owned by the
# agent but git refuses cross-owner access when called through sudo helpers)
cgit() { git -C "$CANONICAL_REPO" -c safe.directory="$CANONICAL_REPO" "$@"; }

oh_key() {
  grep '^LOCAL_BACKEND_API_KEY' "$OH_KEY_FILE" | cut -d= -f2-
}

# oh_curl <method> <path> [body-file]
oh_curl() {
  local method="$1" path="$2" body="${3:-}"
  local key cfg code
  key="$(oh_key)"
  cfg="$(mktemp)"
  chmod 600 "$cfg"
  printf 'header = "X-Session-API-Key: %s"\n' "$key" >"$cfg"
  printf 'header = "Content-Type: application/json"\n' >>"$cfg"
  if [ -n "$body" ]; then
    curl -sS -m 60 --config "$cfg" -X "$method" -d @"$body" "${OH_BASE}${path}"
    code=$?
  else
    curl -sS -m 60 --config "$cfg" -X "$method" "${OH_BASE}${path}"
    code=$?
  fi
  rm -f "$cfg"
  return $code
}

conversation_status() {
  oh_curl GET "/api/conversations?ids=$1" | /usr/bin/python3 -I -c "
import json,sys
d=json.load(sys.stdin)
c=d[0] if isinstance(d,list) else (d.get('items') or [d])[0]
print(c.get('execution_status') or 'unknown')" 2>/dev/null || echo unknown
}

conversation_events() {
  oh_curl GET "/api/conversations/$1/events/count" 2>/dev/null | head -c 12
}

agent_final_response() {
  oh_curl GET "/api/conversations/$1/agent_final_response" | /usr/bin/python3 -I -c "
import json,sys
raw=sys.stdin.read()
try:
    d=json.loads(raw)
    print(d.get('response') if isinstance(d,dict) else raw)
except Exception:
    print(raw)"
}

# workspace_repo <conversation-id> -> path of the checkout inside the workspace
workspace_repo() {
  local hex
  hex="$(echo "$1" | tr -d '-')"
  echo "${WORKSPACE_ROOT}/${hex}/proxima-ai"
}

log_json() {
  printf '{"ts":"%s","component":"conductor","step":"%s","msg":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"
}
