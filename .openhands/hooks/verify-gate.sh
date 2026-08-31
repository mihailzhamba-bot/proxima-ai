#!/bin/bash
cd "${OPENHANDS_PROJECT_DIR:-$PWD}"
[ -f .env.task ] && set -a && . ./.env.task && set +a
LOG="$(mktemp /tmp/verify-gate.XXXXXX.log)"
if make verify >"$LOG" 2>&1; then
  echo "verify-gate: make verify PASS"
  exit 0
fi
echo "verify-gate: make verify FAILED, last 60 lines:"
tail -60 "$LOG"
echo '{"decision":"deny","reason":"make verify failed. Fix all failures before finishing."}'
exit 2
