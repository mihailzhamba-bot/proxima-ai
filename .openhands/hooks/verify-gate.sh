#!/bin/bash
cd "${OPENHANDS_PROJECT_DIR:-$PWD}"
[ -f .env.task ] && set -a && . ./.env.task && set +a
if [ -f .env.task ]; then
  case "${DATABASE_URI:-}" in
    postgresql://*/*proxima_test | postgres://*/*proxima_test) ;;
    *)
      echo "verify-gate: .env.task must load DATABASE_URI for proxima_test" >&2
      echo '{"decision":"deny","reason":"OpenHands DATABASE_URI is missing or does not target proxima_test."}'
      exit 2
      ;;
  esac
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
