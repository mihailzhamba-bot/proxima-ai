#!/bin/bash
# bad_dev_story.sh - BAD pipeline Step 3 (implementation) delegated to OpenHands.
#
#   provision -> dispatch -> wait -> collect -> fetch
#
# Reuses lib.sh from the conductor toolbox (pure helpers, no side effects). It never touches the conductor's own scripts, state or
# systemd units, and it refuses to run while the conductor is active.
#
# No secret value ever reaches argv, stdout, stderr or disk: the OpenHands key
# is only ever read and used inside lib.sh's oh_curl (curl --config).
#
# Prints one JSON object on stdout. Human progress goes to stderr.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/lib.sh"

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"

# Privilege seam. Production uses `sudo -n` and runs sandbox git as the agent
# user; the test harness sets BRIDGE_SUDO="" and BRIDGE_AGENT_USER="" so the
# same code path runs unprivileged in a temporary workspace root.
SUDO="${BRIDGE_SUDO-sudo -n}"
AGENT_USER="${BRIDGE_AGENT_USER-openhands-agent}"
priv() { if [ -n "$SUDO" ]; then $SUDO "$@"; else "$@"; fi; }
as_agent() {
  if [ -n "$SUDO" ] && [ -n "$AGENT_USER" ]; then $SUDO -u "$AGENT_USER" "$@"; else "$@"; fi
}
OWNER_FLAGS=""
[ -n "$SUDO" ] && [ -n "$AGENT_USER" ] && OWNER_FLAGS="-o $AGENT_USER -g $AGENT_USER"

# ---------------------------------------------------------------- exit codes
EX_OK=0            # done, commits fetched
EX_USAGE=2         # bad arguments / precondition on our side
EX_HUMAN=3         # needs a human: confirmation wanted, dirty tree, conductor busy
EX_AGENT=4         # agent failed: error status, stop-hook denied, zero commits
EX_TIMEOUT=5       # wait deadline hit, conversation left running
EX_INFRA=6         # sudo/key/api/git failure
EX_INTEGRITY=7     # base mismatch, ancestry, forbidden path, secret in diff

# ------------------------------------------------------------------ defaults
RUN_ID=""; BRANCH=""; BASE_REF=""; PROMPT_FILE=""; SOURCE_DIR=""
PROFILE_NAME="fedor"; ATTEMPT=1; TIMEOUT=5400; SIMULATE_WORKER=""
POLL_MIN=10; POLL_MAX=60; IDLE_CONFIRMATIONS=2; MAX_UNKNOWN=5
MAX_ITERATIONS=500; PREFLIGHT_ONLY=0; KEEP_WORKSPACE=0
ALLOW_PATHS=""; CONTRACT_FILES=""
DEFAULT_CONTRACT_FILES="AGENTS.md
_bmad-output/planning-artifacts/epics.md
_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md
docs/state/API-FACTS.md"
FORBIDDEN_GLOBS='tools/verify_.*\.py$
^\.github/workflows/
^services/collector/src/contracts/.*\.ts$
^services/control-plane/src/proxima/
^services/webapp/src/lib/auth
^services/webapp/src/app/api/auth/
^services/webapp/src/app/login/'

usage() {
  cat >&2 <<'USAGE'
usage: bad_dev_story.sh --run-id <id> --branch <feat/...> --base-ref <ref>
                        --prompt-file <path> [--source-dir <repo|worktree>]
                        [--profile fedor|glm] [--attempt N] [--timeout SEC]
                        [--allow-path <repo-path>]... [--contract-file <path>]...
                        [--keep-workspace] [--preflight-only]
                        [--simulate-worker <command>]   # offline: run <command> in the
                                                        # sandbox instead of dispatching
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --run-id) RUN_ID="${2:?}"; shift 2 ;;
    --branch) BRANCH="${2:?}"; shift 2 ;;
    --base-ref) BASE_REF="${2:?}"; shift 2 ;;
    --prompt-file) PROMPT_FILE="${2:?}"; shift 2 ;;
    --source-dir) SOURCE_DIR="${2:?}"; shift 2 ;;
    --profile) PROFILE_NAME="${2:?}"; shift 2 ;;
    --attempt) ATTEMPT="${2:?}"; shift 2 ;;
    --timeout) TIMEOUT="${2:?}"; shift 2 ;;
    --max-iterations) MAX_ITERATIONS="${2:?}"; shift 2 ;;
    --allow-path) ALLOW_PATHS="${ALLOW_PATHS}${2:?}
"; shift 2 ;;
    --contract-file) CONTRACT_FILES="${CONTRACT_FILES}${2:?}
"; shift 2 ;;
    --simulate-worker) SIMULATE_WORKER="${2:?}"; shift 2 ;;
    --keep-workspace) KEEP_WORKSPACE=1; shift ;;
    --preflight-only) PREFLIGHT_ONLY=1; shift ;;
    -h|--help) usage; exit $EX_OK ;;
    *) echo "unknown argument: $1" >&2; usage; exit $EX_USAGE ;;
  esac
done

# ------------------------------------------------------------------ plumbing
STATUS="unknown"; CID=""; BASE_SHA=""; HEAD_SHA=""; COMMITS=0
LOCAL_REF=""; RESULT_BUNDLE=""; WS=""; PROBLEM=""
GATE_BASE="skipped"; GATE_CONTRACT="skipped"; GATE_ANCESTRY="skipped"
GATE_PATHS="skipped"; GATE_SECRETS="skipped"; GATE_DIRTY="skipped"; GATE_HOOK="skipped"

note() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }

emit() {  # emit <exit-code>
  local code="$1"
  python3 - "$code" <<PY
import json, sys
print(json.dumps({
    "tool": "bad_dev_story",
    "run_id": "${RUN_ID}",
    "attempt": ${ATTEMPT},
    "conversation_id": "${CID}",
    "branch": "${BRANCH}",
    "base_sha": "${BASE_SHA}",
    "head_sha": "${HEAD_SHA}",
    "status": "${STATUS}",
    "commits": ${COMMITS},
    "local_ref": "${LOCAL_REF}",
    "bundle": "${RESULT_BUNDLE}",
    "workspace": "${WS}",
    "gates": {
        "base_sha": "${GATE_BASE}",
        "contract_files": "${GATE_CONTRACT}",
        "sandbox_clean": "${GATE_DIRTY}",
        "stop_hook": "${GATE_HOOK}",
        "ancestry": "${GATE_ANCESTRY}",
        "forbidden_paths": "${GATE_PATHS}",
        "secret_scan": "${GATE_SECRETS}",
    },
    "problem": ${json_problem},
    "ok": ${ok},
    "exit_code": int(sys.argv[1]),
}, ensure_ascii=False))
PY
  exit "$code"
}

# a ref that failed a gate must not survive: a later step could mistake it for
# reviewed work
drop_ref() {
  [ -n "$LOCAL_REF" ] || return 0
  S update-ref -d "$LOCAL_REF" 2>/dev/null
  LOCAL_REF=""
}

fail() {  # fail <exit-code> <message>
  PROBLEM="$2"
  note "FAIL($1): $2"
  json_problem="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$PROBLEM")"
  ok=False
  emit "$1"
}

done_ok() {
  json_problem=None; ok=True
  emit $EX_OK
}

json_problem=None
ok=False

# ------------------------------------------------------------- 0. validation
[ -n "$RUN_ID" ] && [ -n "$BRANCH" ] && [ -n "$BASE_REF" ] && [ -n "$PROMPT_FILE" ] \
  || { usage; fail $EX_USAGE "missing required argument"; }
echo "$RUN_ID" | grep -Eq '^[a-z0-9][a-z0-9-]{2,40}$' \
  || fail $EX_USAGE "run-id must match ^[a-z0-9][a-z0-9-]{2,40}$"
echo "$BRANCH" | grep -Eq '^(feat|fix|docs|chore)/[a-zA-Z0-9._/-]+$' \
  || fail $EX_USAGE "branch must be feat|fix|docs|chore/<name> (same allowlist as the push wrapper)"
echo "$ATTEMPT" | grep -Eq '^[1-9][0-9]?$' || fail $EX_USAGE "attempt must be 1..99"
case "$PROFILE_NAME" in fedor|glm) : ;; *) fail $EX_USAGE "profile must be fedor or glm" ;; esac
[ -f "$PROMPT_FILE" ] || fail $EX_USAGE "prompt file not found: $PROMPT_FILE"
[ -n "$REPO_ROOT" ] || fail $EX_USAGE "not inside a git repository (set REPO_ROOT)"
SOURCE_DIR="${SOURCE_DIR:-$REPO_ROOT}"
[ -d "$SOURCE_DIR/.git" ] || fail $EX_USAGE "source dir is not a git checkout: $SOURCE_DIR"
[ -n "$CONTRACT_FILES" ] || CONTRACT_FILES="$DEFAULT_CONTRACT_FILES
"

RUN_DIR="$REPO_ROOT/logs/openhands-bridge/$RUN_ID/attempt-$ATTEMPT"
mkdir -p "$RUN_DIR" || fail $EX_INFRA "cannot create run dir $RUN_DIR"

# ------------------------------------------------------------- 1. preflight
note "preflight"
command -v git >/dev/null || fail $EX_INFRA "git not on PATH"
if [ -n "$SUDO" ]; then
  $SUDO true 2>/dev/null || fail $EX_INFRA "sudo -n unavailable"
fi
if [ -z "$SIMULATE_WORKER" ]; then
  priv test -r "$OH_KEY_FILE" 2>/dev/null || fail $EX_INFRA "session key file unreadable: $OH_KEY_FILE"
fi

# conductor guard: two orchestrators over one sprint-status would race
if [ -z "$SIMULATE_WORKER" ]; then
if systemctl is-active --quiet codex-conductor.timer 2>/dev/null \
   || systemctl is-active --quiet proxima-conductor.timer 2>/dev/null; then
  fail $EX_HUMAN "conductor timer is active - stop it before running BAD (systemctl disable --now codex-conductor.timer)"
fi
if command -v conductor >/dev/null 2>&1; then
  BUSY="$(conductor status 2>/dev/null | python3 -c 'import json,sys
try: print(len(json.load(sys.stdin).get("workers") or []))
except Exception: print(0)' 2>/dev/null || echo 0)"
  [ "${BUSY:-0}" = "0" ] || fail $EX_HUMAN "conductor still holds $BUSY worker slot(s)"
fi
oh_curl GET /api/conversations/count >/dev/null 2>&1 \
  || fail $EX_INFRA "OpenHands API not reachable at $OH_BASE"
note "preflight ok (api $OH_BASE, conductor idle)"
else
note "preflight ok (simulated worker, no API and no conductor guard)"
fi
[ "$PREFLIGHT_ONLY" = "1" ] && { STATUS="preflight-ok"; done_ok; }

# ------------------------------------------------------------ 2. provision
S() { git -C "$SOURCE_DIR" "$@"; }
BASE_SHA="$(S rev-parse --verify "${BASE_REF}^{commit}" 2>/dev/null)"
[ -n "$BASE_SHA" ] || fail $EX_USAGE "cannot resolve base-ref '$BASE_REF' in $SOURCE_DIR"

CID="$(python3 -c '
import sys, uuid
ns = uuid.uuid5(uuid.NAMESPACE_URL, "https://proxima.local/bad-dev-story")
print(uuid.uuid5(ns, "%s/%s" % (sys.argv[1], sys.argv[2])))' "$RUN_ID" "$ATTEMPT")"
HEX="$(echo "$CID" | tr -d '-')"
WS="${WORKSPACE_ROOT}/${HEX}"
REPO_IN_WS="$WS/proxima-ai"

if priv test -e "$REPO_IN_WS" 2>/dev/null; then
  fail $EX_USAGE "workspace already exists for $RUN_ID attempt $ATTEMPT ($WS) - use --attempt N+1"
fi

BASE_BUNDLE="$RUN_DIR/base.bundle"
note "bundling $SOURCE_DIR at $BASE_SHA"
S bundle create "$BASE_BUNDLE" --all >/dev/null 2>&1 \
  || fail $EX_INFRA "git bundle create failed in $SOURCE_DIR"

priv install -d -m 0755 $OWNER_FLAGS "$WS" "$WS/.bridge" \
  || fail $EX_INFRA "cannot create workspace $WS"
priv install -m 0644 $OWNER_FLAGS "$BASE_BUNDLE" "$WS/.bridge/base.bundle" \
  || fail $EX_INFRA "cannot hand the base bundle to the sandbox"

A() { as_agent git -C "$REPO_IN_WS" -c safe.directory='*' "$@"; }
as_agent git -c safe.directory='*' clone -q "$WS/.bridge/base.bundle" "$REPO_IN_WS" \
  || fail $EX_INFRA "clone from bundle failed"
priv rm -f "$WS/.bridge/base.bundle"

# zero remotes: a private-repo fetch can no longer 404 and fall back to a stale
# cache the way it did in Story 1.1 attempt 1 - any network attempt fails loudly
A remote remove origin >/dev/null 2>&1
A checkout -q -b "$BRANCH" "$BASE_SHA" || fail $EX_INTEGRITY "cannot branch $BRANCH from $BASE_SHA in the sandbox"
A config user.name "OpenHands Worker" >/dev/null 2>&1
A config user.email "openhands@proxima.local" >/dev/null 2>&1

# ------------------------------------------------------- 3. provisioning gate
WS_HEAD="$(A rev-parse HEAD 2>/dev/null)"
[ "$WS_HEAD" = "$BASE_SHA" ] || { GATE_BASE="fail"; fail $EX_INTEGRITY "sandbox HEAD $WS_HEAD != base $BASE_SHA"; }
GATE_BASE="pass"
[ "$(A rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || fail $EX_INTEGRITY "sandbox is not on $BRANCH"
[ -z "$(A status --porcelain 2>/dev/null)" ] || fail $EX_INTEGRITY "sandbox tree is not clean right after clone"
[ -z "$(A remote 2>/dev/null)" ] || fail $EX_INTEGRITY "sandbox still has a git remote"

MISMATCH=""
OLDIFS="$IFS"; IFS='
'
for f in $CONTRACT_FILES; do
  [ -n "$f" ] || continue
  [ -f "$SOURCE_DIR/$f" ] || continue
  LOCAL_H="$(sha256sum "$SOURCE_DIR/$f" | cut -d' ' -f1)"
  WS_H="$(as_agent sha256sum "$REPO_IN_WS/$f" 2>/dev/null | cut -d' ' -f1)"
  if [ "$LOCAL_H" != "$WS_H" ]; then MISMATCH="$MISMATCH $f"; fi
done
IFS="$OLDIFS"
[ -z "$MISMATCH" ] || { GATE_CONTRACT="fail"; fail $EX_INTEGRITY "contract files differ in the sandbox:$MISMATCH"; }
GATE_CONTRACT="pass"
note "provisioned $WS at $BASE_SHA, branch $BRANCH, 0 remotes, contracts match"

PROMPT_SHA="$(sha256sum "$PROMPT_FILE" | cut -d' ' -f1)"
cp "$PROMPT_FILE" "$RUN_DIR/prompt.md"

# --------------------------------------------------------------- 4. dispatch
if [ -n "$SIMULATE_WORKER" ]; then
  note "simulating the worker: $SIMULATE_WORKER"
  ( cd "$REPO_IN_WS" && eval "$SIMULATE_WORKER" ) >&2 \
    || fail $EX_AGENT "simulated worker command failed"
  STATUS="finished"; GATE_HOOK="simulated"
else
case "$PROFILE_NAME" in fedor) PROFILE="$PROFILE_FEDOR" ;; glm) PROFILE="$PROFILE_GLM" ;; esac
PAYLOAD="$(mktemp)"; chmod 600 "$PAYLOAD"
python3 - "$CID" "$WS" "$PROMPT_FILE" "$PROFILE" "$PAYLOAD" "$RUN_ID" "$ATTEMPT" "$MAX_ITERATIONS" <<'PY'
import json, re, sys
cid, ws, prompt, profile, out, run_id, attempt, max_iter = sys.argv[1:9]
json.dump({
    "conversation_id": cid,
    "workspace": {"kind": "LocalWorkspace", "working_dir": ws},
    "agent_profile_id": profile,
    "initial_message": {
        "role": "user",
        "content": [{"type": "text", "text": open(prompt, encoding="utf-8").read()}],
        "run": True,
    },
    "max_iterations": int(max_iter),
    "stuck_detection": True,
    "confirmation_policy": {"kind": "NeverConfirm"},
    "tags": {"bridge": "baddevstory", "run": re.sub(r"[^a-z0-9]", "", run_id), "attempt": str(attempt)},
    "autotitle": True,
}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY
RESP="$(oh_curl POST /api/conversations "$PAYLOAD")"
rm -f "$PAYLOAD"
echo "$RESP" | grep -q '"id"' || fail $EX_INFRA "conversation create failed: $(echo "$RESP" | head -c 200)"
note "dispatched $CID (profile $PROFILE_NAME, prompt sha256 ${PROMPT_SHA})"

sleep 5
if [ "$(conversation_status "$CID")" = "idle" ]; then
  EMPTY="$(mktemp)"; echo '{}' >"$EMPTY"
  oh_curl POST "/api/conversations/$CID/run" "$EMPTY" >/dev/null
  rm -f "$EMPTY"
  note "nudged an idle conversation"
fi

# ------------------------------------------------------------------- 5. wait
DEADLINE=$(( $(date +%s) + TIMEOUT ))
SLEEP=$POLL_MIN; IDLE_SEEN=0; UNKNOWN_SEEN=0
while :; do
  STATUS="$(conversation_status "$CID")"
  case "$STATUS" in
    running|paused_for_tool) IDLE_SEEN=0; UNKNOWN_SEEN=0 ;;
    idle)
      UNKNOWN_SEEN=0
      FINAL="$(agent_final_response "$CID" 2>/dev/null | head -c 40)"
      if [ -n "$FINAL" ]; then
        IDLE_SEEN=$((IDLE_SEEN + 1))
        [ "$IDLE_SEEN" -ge "$IDLE_CONFIRMATIONS" ] && { STATUS="finished"; break; }
      else
        IDLE_SEEN=0
      fi
      ;;
    finished|stopped) break ;;
    error) fail $EX_AGENT "conversation ended with execution_status=error" ;;
    stuck) fail $EX_AGENT "stuck detection fired; intervene with: sudo -u $AGENT_USER $HERE/send_fix.sh $CID <message-file>" ;;
    waiting_for_confirmation|paused)
      fail $EX_HUMAN "conversation needs a human ($STATUS); confirmation is never granted automatically" ;;
    *)
      UNKNOWN_SEEN=$((UNKNOWN_SEEN + 1))
      [ "$UNKNOWN_SEEN" -ge "$MAX_UNKNOWN" ] && fail $EX_INFRA "unknown execution_status repeated: $STATUS"
      ;;
  esac
  [ "$(date +%s)" -lt "$DEADLINE" ] || { STATUS="timeout"; fail $EX_TIMEOUT "wait deadline of ${TIMEOUT}s hit; conversation $CID left running"; }
  note "wait: $STATUS, $(conversation_events "$CID") events, $(( DEADLINE - $(date +%s) ))s left"
  sleep "$SLEEP"
  SLEEP=$(( SLEEP * 2 )); [ "$SLEEP" -gt "$POLL_MAX" ] && SLEEP=$POLL_MAX
done
note "terminal status: $STATUS"

# stop-hook verdict: a red `make verify` makes verify-gate.sh deny, and a denied
# stop must never be reported as success
agent_final_response "$CID" >"$RUN_DIR/final-response.md" 2>/dev/null
oh_curl GET "/api/conversations/$CID/events?limit=400" >"$RUN_DIR/events.json" 2>/dev/null
if grep -qi 'verify-gate: make verify PASS' "$RUN_DIR/events.json" 2>/dev/null; then
  GATE_HOOK="pass"
elif grep -qi '"decision"[^}]*"deny"\|make verify failed' "$RUN_DIR/events.json" 2>/dev/null; then
  GATE_HOOK="deny"
  fail $EX_AGENT "stop hook denied the finish: make verify was red in the sandbox"
else
  GATE_HOOK="unknown"
fi
fi

# ---------------------------------------------------------------- 6. collect
DIRTY="$(A status --porcelain 2>/dev/null | grep -v '^??' | wc -l | tr -d ' ')"
if [ "${DIRTY:-0}" != "0" ]; then
  GATE_DIRTY="fail"
  fail $EX_HUMAN "$DIRTY tracked file(s) uncommitted in the sandbox; ask the worker to commit via send_fix.sh"
fi
GATE_DIRTY="pass"

HEAD_SHA="$(A rev-parse "$BRANCH" 2>/dev/null)"
COMMITS="$(A rev-list --count "$BASE_SHA..$BRANCH" 2>/dev/null | tr -d ' ')"
COMMITS="${COMMITS:-0}"
[ "$COMMITS" != "0" ] || fail $EX_AGENT "worker produced no commits on $BRANCH above $BASE_SHA"

SANDBOX_BUNDLE="$WS/.bridge/result.bundle"
# same `base..branch` form collect_branch.sh uses; that script itself cannot be
# invoked here because it lives under /home/proxima-admin (0750) where
# openhands-agent has no traverse rights
A bundle create "$SANDBOX_BUNDLE" "$BASE_SHA..$BRANCH" >/dev/null 2>&1 \
  || fail $EX_INFRA "bundle create failed in the sandbox"
A bundle verify "$SANDBOX_BUNDLE" >/dev/null 2>&1 \
  || fail $EX_INTEGRITY "bundle does not verify inside the sandbox"
# freeze before copying: same uid could otherwise swap the file underneath us
if [ -n "$SUDO" ]; then priv chown root:root "$SANDBOX_BUNDLE"; fi
priv chmod 600 "$SANDBOX_BUNDLE"
SANDBOX_SHA="$(priv sha256sum "$SANDBOX_BUNDLE" | cut -d' ' -f1)"
RESULT_BUNDLE="$RUN_DIR/result.bundle"
priv install -m 0600 -o "$(id -un)" -g "$(id -gn)" "$SANDBOX_BUNDLE" "$RESULT_BUNDLE" \
  || fail $EX_INFRA "cannot copy the result bundle out of the sandbox"
priv rm -f "$SANDBOX_BUNDLE"
[ "$(sha256sum "$RESULT_BUNDLE" | cut -d' ' -f1)" = "$SANDBOX_SHA" ] \
  || fail $EX_INTEGRITY "result bundle sha256 changed while crossing the boundary"

# ------------------------------------------------------------------ 7. fetch
# `base..branch` records base_sha as a bundle prerequisite, so verify proves the
# worker built on our base using git's own object graph, not anyone's claim
S bundle verify "$RESULT_BUNDLE" >/dev/null 2>&1 \
  || fail $EX_INTEGRITY "result bundle does not verify locally (base $BASE_SHA missing = wrong base)"
LOCAL_REF="refs/openhands/$RUN_ID/$ATTEMPT/head"
S fetch -q "$RESULT_BUNDLE" "refs/heads/$BRANCH:$LOCAL_REF" \
  || fail $EX_INFRA "git fetch from the result bundle failed"

S merge-base --is-ancestor "$BASE_SHA" "$LOCAL_REF" \
  || { GATE_ANCESTRY="fail"; drop_ref; fail $EX_INTEGRITY "fetched commits do not descend from $BASE_SHA"; }
GATE_ANCESTRY="pass"
[ "$(S rev-parse "$LOCAL_REF")" = "$HEAD_SHA" ] \
  || { drop_ref; fail $EX_INTEGRITY "fetched tip differs from the sandbox tip"; }

CHANGED="$(S diff --name-only "$BASE_SHA..$LOCAL_REF")"
VIOLATIONS=""
OLDIFS="$IFS"; IFS='
'
for p in $CHANGED; do
  [ -n "$p" ] || continue
  case "
$ALLOW_PATHS" in *"
$p
"*) continue ;; esac
  for rx in $FORBIDDEN_GLOBS; do
    echo "$p" | grep -Eq "$rx" && VIOLATIONS="$VIOLATIONS $p"
  done
  # existing migrations are immutable; a brand new NNN_*.sql is fine
  case "$p" in db/migrations/*.sql)
    if S cat-file -e "$BASE_SHA:$p" 2>/dev/null; then VIOLATIONS="$VIOLATIONS $p"; fi ;;
  esac
done
IFS="$OLDIFS"
if [ -n "$VIOLATIONS" ]; then
  GATE_PATHS="fail"; drop_ref
  fail $EX_INTEGRITY "worker touched protected paths:$VIOLATIONS"
fi
GATE_PATHS="pass"

SECRET_HIT="$(REPO_ROOT="$REPO_ROOT" python3 - "$SOURCE_DIR" "$BASE_SHA" "$LOCAL_REF" <<'PY'
import importlib.util, pathlib, subprocess, sys
source_dir, base, ref = sys.argv[1:4]
root = pathlib.Path(source_dir)
spec = importlib.util.spec_from_file_location("secret_scan", root / "tools" / "secret_scan.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
names = subprocess.run(["git", "-C", source_dir, "diff", "--name-only", f"{base}..{ref}"],
                       capture_output=True, text=True, check=True).stdout.split()
found = []
for name in names:
    if mod.FORBIDDEN_NAMES.search(name):
        found.append(f"{name}: forbidden filename")
        continue
    blob = subprocess.run(["git", "-C", source_dir, "show", f"{ref}:{name}"], capture_output=True)
    if blob.returncode:
        continue
    found.extend(mod.inspect("incoming", name, blob.stdout))
print("; ".join(sorted(set(found))))
PY
)"
if [ -n "$SECRET_HIT" ]; then
  GATE_SECRETS="fail"; drop_ref
  fail $EX_INTEGRITY "secret pattern in incoming commits: $SECRET_HIT"
fi
GATE_SECRETS="pass"

if [ "$KEEP_WORKSPACE" = "0" ]; then
  priv rm -rf "$WS" 2>/dev/null && note "workspace removed"
fi

note "done: $COMMITS commit(s) at $LOCAL_REF"
done_ok
