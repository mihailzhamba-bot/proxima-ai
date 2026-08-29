#!/bin/bash
# Stop-hook: agent cannot finish until `make verify` passes (repo verify-contract).
cd "${OPENHANDS_PROJECT_DIR:-$PWD}"

if [ -z "${DATABASE_URI:-}" ]; then
  echo '{"decision":"deny","reason":"DATABASE_URI is not set. Add secret DATABASE_URI (proxima_dev URI) in OpenHands Settings > Secrets, then retry."}'
  exit 2
fi

LOG="$(mktemp /tmp/verify-gate.XXXXXX.log)"
if make verify >"$LOG" 2>&1; then
  echo "verify-gate: make verify PASS"
  exit 0
fi
echo "verify-gate: make verify FAILED, last 60 lines:"
tail -60 "$LOG"
echo '{"decision":"deny","reason":"make verify failed. Fix all failures before finishing."}'
exit 2
