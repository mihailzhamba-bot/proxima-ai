#!/bin/bash
# conductor_tick.sh - one heartbeat of the conductor loop.
# Ensures a live conductor conversation exists (recreated daily) and sends it
# a tick message. All judgement lives in the conductor itself; this script is
# deliberately dumb so a stuck LLM cannot break the schedule.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

STATE_DIR="${CONDUCTOR_STATE_DIR:-/srv/proxima-ai/conductor}"
STATE_FILE="$STATE_DIR/conversation.json"
REPO_WS="$STATE_DIR/workspace"
MAX_AGE_HOURS="${CONDUCTOR_MAX_AGE_HOURS:-24}"

mkdir -p "$STATE_DIR"

conductor_is_fresh() {
  [ -f "$STATE_FILE" ] || return 1
  local cid started now age
  cid="$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['id'])" 2>/dev/null)" || return 1
  started="$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['started'])" 2>/dev/null)" || return 1
  now="$(date -u +%s)"
  age=$(( (now - started) / 3600 ))
  [ "$age" -lt "$MAX_AGE_HOURS" ] || return 1
  case "$(conversation_status "$cid")" in
    running|idle|finished) return 0 ;;
    *) return 1 ;;
  esac
}

start_conductor() {
  local cid hex ws payload resp bundle
  cid="$(python3 -c 'import uuid; print(uuid.uuid4())')"
  hex="$(echo "$cid" | tr -d '-')"
  ws="${WORKSPACE_ROOT}/${hex}"
  install -d -o openhands-agent -g openhands-agent "$ws" 2>/dev/null || mkdir -p "$ws"
  bundle="$(mktemp -u /tmp/conductor-boot-XXXXXX.bundle)"
  cgit bundle create "$bundle" --all >/dev/null 2>&1 \
    || { echo "canonical bundle failed" >&2; return 3; }
  git -c safe.directory='*' clone -q "$bundle" "$ws/proxima-ai" || { rm -f "$bundle"; return 3; }
  rm -f "$bundle"
  git -C "$ws/proxima-ai" checkout -q main 2>/dev/null || true
  chown -R openhands-agent:openhands-agent "$ws" 2>/dev/null || true

  payload="$(mktemp)"; chmod 600 "$payload"
  python3 - "$cid" "$ws" "$PROFILE_FEDOR" "$payload" <<'PY'
import json, sys
cid, ws, profile, out = sys.argv[1:5]
boot = (
"Ты - Дирижёр конвейера PROXIMA AI на сервере. Твой контракт - docs/agent-system/ORCHESTRATOR.md "
"в ./proxima-ai: прочитай его ПОЛНОСТЬЮ и следуй дословно; менять его тебе запрещено.\n\n"
"Каждый раз, когда тебе приходит сообщение 'tick', выполняй ровно один тик по разделу «Один тик» "
"этого файла: свериться с состоянием, принять готовых воркеров, прогнать кросс-модельное ревью, "
"решить фикс/PR, при наличии слота запустить следующую историю из очереди, обновить учёт.\n\n"
"Инструменты - tools/orchestrator/*.sh (launch_worker, worker_status, send_fix, collect_branch) "
"и три sudo-обёртки: sudo /usr/local/sbin/proxima-git-push, proxima-pr, proxima-pr-merge. "
"Прямой git push, gh, правки .github/workflows и любые действия на /srv/proxima-ai/repo запрещены.\n\n"
"ВАЖНО на первые сутки: automerge ВЫКЛЮЧЕН - доводи истории до PR и останавливайся, "
"proxima-pr-merge не вызывай, пока в ORCHESTRATOR.md не появится строка 'automerge: on'.\n\n"
"Сейчас: прочитай контракт и состояние (sprint-status.yaml, STATE.md), затем ответь одним абзацем - "
"что ты видишь в очереди и что сделаешь первым тиком. Ничего не запускай в этом сообщении."
)
json.dump({
    "conversation_id": cid,
    "workspace": {"kind": "LocalWorkspace", "working_dir": ws},
    "agent_profile_id": profile,
    "initial_message": {"role": "user", "content": [{"type": "text", "text": boot}], "run": True},
    "max_iterations": 500,
    "stuck_detection": True,
    "confirmation_policy": {"kind": "NeverConfirm"},
    "autotitle": True,
}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY
  resp="$(oh_curl POST /api/conversations "$payload")"
  rm -f "$payload"
  echo "$resp" | grep -q '"id"' || { echo "conductor create failed" >&2; return 4; }
  python3 -c "
import json
json.dump({'id': '$cid', 'started': $(date -u +%s)}, open('$STATE_FILE','w'))"
  log_json conductor-start "$cid"
  echo "$cid"
}

CID=""
if conductor_is_fresh; then
  CID="$(python3 -c "import json;print(json.load(open('$STATE_FILE'))['id'])")"
else
  CID="$(start_conductor)" || exit $?
  exit 0   # boot message counts as this tick
fi

MSG="$(mktemp)"; chmod 600 "$MSG"
printf 'tick %s\n\nВыполни один тик по docs/agent-system/ORCHESTRATOR.md. Кратко отчитайся: что принял, что запустил, что заблокировано.\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$MSG"
"$(dirname "$0")/send_fix.sh" "$CID" "$MSG"
RC=$?
rm -f "$MSG"
log_json tick "$CID rc=$RC"
exit $RC
