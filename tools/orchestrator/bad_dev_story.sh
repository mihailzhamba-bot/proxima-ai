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
BRIDGE_RUN_ROOT="${BRIDGE_RUN_ROOT:-$REPO_ROOT}"
BRIDGE_RECEIPT_DIR="${BRIDGE_RECEIPT_DIR:-}"
BRIDGE_TEMPLATE_NAME="${BRIDGE_TEMPLATE_NAME:-}"
BRIDGE_TEMPLATE_FINGERPRINT="${BRIDGE_TEMPLATE_FINGERPRINT:-}"
BRIDGE_PROFILE_REVISION="${BRIDGE_PROFILE_REVISION:-}"
BRIDGE_SHARED_WORKSPACE="${BRIDGE_SHARED_WORKSPACE:-0}"
BRIDGE_TRUSTED_OUTPUT="${BRIDGE_TRUSTED_OUTPUT:-0}"

# Privilege seam. Production runs `sudo -n` and does sandbox git as the agent
# user. Tests set BRIDGE_SUDO="" (run everything directly) or point
# BRIDGE_SUDO_CMD at a shim, so the privileged code path itself is exercised.
#
# The elevation command is ONE word and is always quoted: this function is
# called from loops that set IFS to a newline, where an unquoted multi-word
# expansion would collapse into a single unfindable command.
SUDO_CMD="${BRIDGE_SUDO_CMD-sudo}"
case "${BRIDGE_SUDO-unset}" in "") SUDO_CMD="" ;; esac
AGENT_USER="${BRIDGE_AGENT_USER-openhands-agent}"
priv() { if [ -n "$SUDO_CMD" ]; then "$SUDO_CMD" -n "$@"; else "$@"; fi; }
as_agent() {
  if [ -n "$SUDO_CMD" ] && [ -n "$AGENT_USER" ]; then "$SUDO_CMD" -n -u "$AGENT_USER" "$@"
  else "$@"; fi
}
own_flags() {  # prints the install(1) ownership flags, empty when unprivileged
  [ -n "$SUDO_CMD" ] && [ -n "$AGENT_USER" ] && printf -- '-o %s -g %s' "$AGENT_USER" "$AGENT_USER"
}
OWNER_FLAGS="$(own_flags)"
OPENHANDS_PERSISTENCE_ROOT="${OPENHANDS_PERSISTENCE_ROOT:-/srv/openhands/persistence}"

# lib.sh's oh_key() reads the key file directly because the conductor's scripts
# run as openhands-agent. This bridge runs as the invoking user, who cannot read
# a 0600 file in that home, so route the read through the privilege seam.
# Only the PATH is ever passed as an argument; the value stays inside lib.sh.
oh_key() { priv cat "$OH_KEY_FILE" 2>/dev/null | grep '^LOCAL_BACKEND_API_KEY' | cut -d= -f2-; }

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
MAX_ITERATIONS=500; TITLE_LLM_PROFILE="${BRIDGE_TITLE_LLM_PROFILE:-glm-5.3}"; PREFLIGHT_ONLY=0; KEEP_WORKSPACE=0
EXTERNAL_COLLECT=0
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
                        [--keep-workspace] [--preflight-only] [--external-collect]
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
    --external-collect) EXTERNAL_COLLECT=1; shift ;;
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

# Event history lives in the conversation's persistence dir, which is owned by
# the agent user; the API returns nothing once a conversation dies during init.
conversation_persistence_dir() {
  oh_curl GET "/api/conversations/$1" 2>/dev/null \
    | /usr/bin/python3 -I -c 'import json, sys
try:
    value = json.load(sys.stdin).get("persistence_dir")
    print(value if isinstance(value, str) else "")
except Exception:
    print("")' 2>/dev/null
}

# The conversation API is not a trusted source of filesystem paths. Read event
# files without a shell, only below the configured persistence root, and only
# from the directory for the requested conversation. Symlinked files and
# directories are rejected so a worker cannot make a privileged reader follow
# them outside the event store.
read_persisted_events() {
  local persistence_dir="$1" conversation_id="$2"
  priv /usr/bin/python3 -I - "$OPENHANDS_PERSISTENCE_ROOT" "$persistence_dir" "$conversation_id" <<'PY'
import os
import stat
import sys
from pathlib import Path

root_raw, persistence_raw, conversation_id = sys.argv[1:4]
directory_fd = None
try:
    root = Path(root_raw).resolve(strict=True)
    candidate = Path(persistence_raw)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("untrusted persistence path")
    relative = candidate.relative_to(root)
    conversation_names = {conversation_id, conversation_id.replace("-", "")}
    if not conversation_names.intersection(relative.parts):
        raise ValueError("conversation path mismatch")

    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory_fd = os.open(root, directory_flags)
    for component in (*relative.parts, "events"):
        next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
        os.close(directory_fd)
        directory_fd = next_fd
except (OSError, RuntimeError, ValueError):
    if directory_fd is not None:
        os.close(directory_fd)
    raise SystemExit(65)

try:
    total = 0
    for name in sorted(os.listdir(directory_fd)):
        if not name.endswith(".json") or "/" in name or name in {".", ".."}:
            continue
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            file_fd = os.open(name, flags, dir_fd=directory_fd)
        except OSError:
            continue
        try:
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024 * 1024:
                continue
            total += info.st_size
            if total > 64 * 1024 * 1024:
                raise SystemExit(65)
            chunks = []
            while True:
                chunk = os.read(file_fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b"".join(chunks)
            sys.stdout.buffer.write(data)
            if data and not data.endswith(b"\n"):
                sys.stdout.buffer.write(b"\n")
        finally:
            os.close(file_fd)
finally:
    os.close(directory_fd)
PY
}

dump_diagnostics() {
  local pdir
  [ -n "$CID" ] || return 0
  agent_final_response "$CID" >"$RUN_DIR/final-response.md" 2>/dev/null
  oh_curl GET "/api/conversations/$CID/events" >"$RUN_DIR/events.json" 2>/dev/null
  pdir="$(conversation_persistence_dir "$CID")"
  if [ -n "$pdir" ]; then
    read_persisted_events "$pdir" "$CID" >"$RUN_DIR/persisted-events.json" 2>/dev/null || :
  fi
  note "diagnostics in $RUN_DIR"
}

# first error the conversation recorded, for the failure message
conversation_error() {
  local pdir
  pdir="$(conversation_persistence_dir "$1")"
  [ -n "$pdir" ] || return 0
  read_persisted_events "$pdir" "$1" | /usr/bin/python3 -I -c '
import json, re, sys
raw = sys.stdin.read()
for blob in re.findall(r"\{.*?\}(?=\s*\{|\s*$)", raw, re.S) or [raw]:
    try: event = json.loads(blob)
    except Exception: continue
    if event.get("code") or "Error" in str(event.get("kind", "")):
        print((event.get("code", "") + ": " + str(event.get("detail", ""))).replace("\n", " ")[:300])
        break' 2>/dev/null
}

emit() {  # emit <exit-code>
  local code="$1"
  /usr/bin/python3 -I - "$code" "$RUN_ID" "$ATTEMPT" "$CID" "$BRANCH" "$BASE_SHA" \
    "$HEAD_SHA" "$STATUS" "$COMMITS" "$LOCAL_REF" "$RESULT_BUNDLE" "$WS" \
    "$GATE_BASE" "$GATE_CONTRACT" "$GATE_DIRTY" "$GATE_HOOK" "$GATE_ANCESTRY" \
    "$GATE_PATHS" "$GATE_SECRETS" "$PROBLEM" "$ok" "$BRIDGE_TEMPLATE_NAME" "$BRIDGE_TEMPLATE_FINGERPRINT" "$BRIDGE_RECEIPT_DIR" <<'PY'
import json, os, pathlib, sys, uuid
(
    code, run_id, attempt, conversation_id, branch, base_sha, head_sha,
    status, commits, local_ref, bundle, workspace, gate_base,
    gate_contract, gate_dirty, gate_hook, gate_ancestry, gate_paths,
    gate_secrets, problem, ok, template, template_fingerprint, receipt_dir,
) = sys.argv[1:]
payload = {
    "tool": "bad_dev_story",
    "run_id": run_id,
    "template": template or None,
    "template_fingerprint": template_fingerprint or None,
    "attempt": int(attempt),
    "conversation_id": conversation_id,
    "branch": branch,
    "base_sha": base_sha,
    "head_sha": head_sha,
    "status": status,
    "commits": int(commits),
    "local_ref": local_ref,
    "bundle": bundle,
    "workspace": workspace,
    "gates": {
        "base_sha": gate_base,
        "contract_files": gate_contract,
        "sandbox_clean": gate_dirty,
        "stop_hook": gate_hook,
        "ancestry": gate_ancestry,
        "forbidden_paths": gate_paths,
        "secret_scan": gate_secrets,
    },
    "problem": problem or None,
    "ok": ok == "True",
    "exit_code": int(code),
}
encoded = json.dumps(payload, ensure_ascii=False)
if receipt_dir:
    root = pathlib.Path(receipt_dir)
    if not root.is_absolute() or root.is_symlink():
        raise SystemExit("invalid receipt directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    target = root / (run_id + ".json")
    temporary = root / (run_id + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        data = memoryview(encoded.encode())
        while data:
            written = os.write(descriptor, data)
            data = data[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, target)
print(encoded)
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
  ok=False
  emit "$1"
}

done_ok() {
  PROBLEM=""; ok=True
  emit $EX_OK
}

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
case "$BRIDGE_RUN_ROOT" in /*) : ;; *) fail $EX_USAGE "bridge run root must be absolute" ;; esac
[ -d "$BRIDGE_RUN_ROOT" ] && [ ! -L "$BRIDGE_RUN_ROOT" ] && [ -w "$BRIDGE_RUN_ROOT" ] \
  || fail $EX_USAGE "bridge run root is not a trusted writable directory"
[ -n "$CONTRACT_FILES" ] || CONTRACT_FILES="$DEFAULT_CONTRACT_FILES
"

RUN_DIR="$BRIDGE_RUN_ROOT/logs/openhands-bridge/$RUN_ID/attempt-$ATTEMPT"
mkdir -p "$RUN_DIR" || fail $EX_INFRA "cannot create run dir $RUN_DIR"
[ "$BRIDGE_TRUSTED_OUTPUT" != "1" ] || chmod 700 "$RUN_DIR" \
  || fail $EX_INFRA "cannot protect run dir $RUN_DIR"

# ------------------------------------------------------------- 1. preflight
note "preflight"
command -v git >/dev/null || fail $EX_INFRA "git not on PATH"
if [ -n "$SUDO_CMD" ]; then
  priv true 2>/dev/null || fail $EX_INFRA "sudo -n unavailable"
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
# A slot held by a worker that has already finished is not live work: the
# conductor was stopped before collecting it, and that state never clears on its
# own. Block only on workers that are still moving, and say so for the rest.
if command -v conductor >/dev/null 2>&1; then
  SLOTS="$(conductor status 2>/dev/null | /usr/bin/python3 -I -c '
import json, re, sys
try:
    workers = json.load(sys.stdin).get("workers") or []
except Exception:
    print("unknown 0 0"); raise SystemExit
TERMINAL = {"finished", "stopped", "error", "stuck"}
live, done = [], []
for w in workers:
    match = re.search(r"status=(\w+)", w.get("detail") or "")
    state = match.group(1) if match else "unknown"
    (done if state in TERMINAL else live).append("%s(%s)" % (w.get("story"), state))
print("ok", ",".join(live) or "-", ",".join(done) or "-")' 2>/dev/null || echo "unknown 0 0")"
  set -- $SLOTS
  SLOT_OK="${1:-unknown}"; SLOT_LIVE="${2:--}"; SLOT_DONE="${3:--}"
  [ "$SLOT_OK" = "ok" ] || fail $EX_HUMAN "cannot read conductor status - resolve it before running BAD"
  [ "$SLOT_LIVE" = "-" ] || fail $EX_HUMAN "conductor workers still running: $SLOT_LIVE"
  [ "$SLOT_DONE" = "-" ] || note "conductor holds finished, uncollected work: $SLOT_DONE (not blocking; harvest it before re-enabling the timer)"
fi
COUNT_BODY="$(oh_curl GET /api/conversations/count 2>/dev/null)"
case "$COUNT_BODY" in
  ''|*Unauthorized*|*unauthorized*)
    fail $EX_INFRA "OpenHands API at $OH_BASE rejected the session key or is unreachable" ;;
esac
echo "$COUNT_BODY" | grep -Eq '^[0-9]+$|"[a-z_]+"' \
  || fail $EX_INFRA "unexpected reply from $OH_BASE: $(echo "$COUNT_BODY" | head -c 120)"
note "preflight ok (api $OH_BASE, conductor idle)"
else
note "preflight ok (simulated worker, no API and no conductor guard)"
fi
[ "$PREFLIGHT_ONLY" = "1" ] && { STATUS="preflight-ok"; done_ok; }

# ------------------------------------------------------------ 2. provision
S() { git -c core.hooksPath=/dev/null -c safe.directory='*' -C "$SOURCE_DIR" "$@"; }
BASE_SHA="$(S rev-parse --verify "${BASE_REF}^{commit}" 2>/dev/null)"
[ -n "$BASE_SHA" ] || fail $EX_USAGE "cannot resolve base-ref '$BASE_REF' in $SOURCE_DIR"

CID="$(/usr/bin/python3 -I -c '
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
SEED_BRANCH="loop-seed-$RUN_ID-$ATTEMPT"
SEED_REF="refs/heads/$SEED_BRANCH"
S update-ref "$SEED_REF" "$BASE_SHA" "" >/dev/null 2>&1 \
  || fail $EX_INFRA "cannot create isolated seed ref"
if ! S bundle create "$BASE_BUNDLE" "$SEED_REF" >/dev/null 2>&1; then
  S update-ref -d "$SEED_REF" >/dev/null 2>&1
  fail $EX_INFRA "git bundle create failed in $SOURCE_DIR"
fi
S update-ref -d "$SEED_REF" >/dev/null 2>&1 \
  || fail $EX_INFRA "cannot remove isolated seed ref"

WS_DIR_MODE=0755; WS_FILE_MODE=0644
if [ "$BRIDGE_SHARED_WORKSPACE" = "1" ]; then WS_DIR_MODE=2770; WS_FILE_MODE=0660; fi
priv install -d -m "$WS_DIR_MODE" $OWNER_FLAGS "$WS" "$WS/.bridge" \
  || fail $EX_INFRA "cannot create workspace $WS"
priv install -m "$WS_FILE_MODE" $OWNER_FLAGS "$BASE_BUNDLE" "$WS/.bridge/base.bundle" \
  || fail $EX_INFRA "cannot hand the base bundle to the sandbox"

A() { as_agent git -c core.hooksPath=/dev/null -c safe.directory='*' -C "$REPO_IN_WS" "$@"; }
as_agent git -c core.hooksPath=/dev/null -c safe.directory='*' clone -q "$WS/.bridge/base.bundle" "$REPO_IN_WS" \
  || fail $EX_INFRA "clone from bundle failed"
priv rm -f "$WS/.bridge/base.bundle"

# zero remotes: a private-repo fetch can no longer 404 and fall back to a stale
# cache the way it did in Story 1.1 attempt 1 - any network attempt fails loudly
A remote remove origin >/dev/null 2>&1
A checkout -q -b "$BRANCH" "$BASE_SHA" || fail $EX_INTEGRITY "cannot branch $BRANCH from $BASE_SHA in the sandbox"
A branch -D "$SEED_BRANCH" >/dev/null 2>&1 || :
A config user.name "OpenHands Worker" >/dev/null 2>&1
A config user.email "openhands@proxima.local" >/dev/null 2>&1

# ------------------------------------------------------- 3. provisioning gate
WS_HEAD="$(A rev-parse HEAD 2>/dev/null)"
[ "$WS_HEAD" = "$BASE_SHA" ] || { GATE_BASE="fail"; fail $EX_INTEGRITY "sandbox HEAD $WS_HEAD != base $BASE_SHA"; }
GATE_BASE="pass"
[ "$(A rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || fail $EX_INTEGRITY "sandbox is not on $BRANCH"
[ -z "$(A status --porcelain 2>/dev/null)" ] || fail $EX_INTEGRITY "sandbox tree is not clean right after clone"
[ -z "$(A remote 2>/dev/null)" ] || fail $EX_INTEGRITY "sandbox still has a git remote"
EXTRA_REFS="$(A for-each-ref --format='%(refname)' | grep -v "^refs/heads/$BRANCH$" || :)"
[ -z "$EXTRA_REFS" ] || fail $EX_INTEGRITY "sandbox seed exposed unrelated refs"

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
chmod 600 "$RUN_DIR/prompt.md"

# --------------------------------------------------------------- 4. dispatch
if [ -n "$SIMULATE_WORKER" ]; then
  note "simulating the worker: $SIMULATE_WORKER"
  ( cd "$REPO_IN_WS" && eval "$SIMULATE_WORKER" ) >&2 \
    || fail $EX_AGENT "simulated worker command failed"
  STATUS="finished"; GATE_HOOK="simulated"
else
case "$PROFILE_NAME" in fedor) PROFILE="$PROFILE_FEDOR" ;; glm) PROFILE="$PROFILE_GLM" ;; esac
echo "$BRIDGE_PROFILE_REVISION" | grep -Eq '^[1-9][0-9]*$' || fail $EX_INTEGRITY "bound Agent Profile revision is required"
# working_dir is the workspace ROOT, not the checkout inside it - same as
# launch_worker.sh, and not an accident. The fedor profile is Codex over ACP;
# started inside the checkout it loads the project .codex/config.toml, whose
# transport-less `enabled = false` blocks are fatal unless the same servers
# exist in the agent user's ~/.codex (AGENTS.md, Known pitfalls, 27.08). From
# the workspace root that file is out of scope. The dispatch prompt therefore
# has to name the checkout subdirectory explicitly.
PAYLOAD="$(mktemp)"; MESSAGE_PAYLOAD="$(mktemp)"; RESPONSE="$(mktemp)"; chmod 600 "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RESPONSE"
/usr/bin/python3 -I - "$CID" "$WS" "$PROMPT_FILE" "$PROFILE" "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RUN_ID" "$ATTEMPT" "$MAX_ITERATIONS" "$TITLE_LLM_PROFILE" "$EXTERNAL_COLLECT" <<'PY'
import json, re, sys
cid, ws, prompt, profile, out, message_out, run_id, attempt, max_iter, title_profile, external_collect = sys.argv[1:12]
payload = {
    "conversation_id": cid,
    "workspace": {"kind": "LocalWorkspace", "working_dir": ws},
    "agent_profile_id": profile,
    "max_iterations": int(max_iter),
    "stuck_detection": True,
    "confirmation_policy": {"kind": "NeverConfirm"},
    "tags": {"bridge": "baddevstory", "run": re.sub(r"[^a-z0-9]", "", run_id), "attempt": str(attempt)},
    "autotitle": external_collect != "1",
    # ACP profiles (Codex over ACP) carry no LLM of their own, so without an
    # explicit title profile the server falls back to OpenAI with no key and
    # logs "Missing credentials" on every dispatch. Titles go through the
    # GLM LLM profile that every worker conversation can reach.
}
if external_collect != "1":
    payload["title_llm_profile"] = title_profile
json.dump(payload, open(out, "w", encoding="utf-8"), ensure_ascii=False)
message={"role":"user","content":[{"type":"text","text":open(prompt,encoding="utf-8").read()}],"run":True}
json.dump(message,open(message_out,"w",encoding="utf-8"),ensure_ascii=False)
PY
oh_curl POST /api/conversations "$PAYLOAD" >"$RESPONSE" || { rm -f "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RESPONSE"; fail $EX_INFRA "conversation create transport failed"; }
/usr/bin/python3 -I - "$CID" "$PROFILE" "$BRIDGE_PROFILE_REVISION" "$RESPONSE" <<'PY' || { rm -f "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RESPONSE"; fail $EX_INTEGRITY "conversation launched Agent Profile differs from approved revision"; }
import json,sys
cid,profile,revision,path=sys.argv[1:5]
data=json.load(open(path,encoding="utf-8"));launched=data.get("launched_agent_profile") or {}
if data.get("id")!=cid or launched.get("agent_profile_id")!=profile or launched.get("revision")!=int(revision):raise SystemExit(1)
PY
oh_curl POST "/api/conversations/$CID/events" "$MESSAGE_PAYLOAD" >"$RESPONSE" || { rm -f "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RESPONSE"; fail $EX_INFRA "conversation message transport failed"; }
/usr/bin/python3 -I - "$RESPONSE" <<'PY' || { rm -f "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RESPONSE"; fail $EX_INFRA "conversation message rejected"; }
import json,sys
if json.load(open(sys.argv[1],encoding="utf-8")).get("success") is not True:raise SystemExit(1)
PY
rm -f "$PAYLOAD" "$MESSAGE_PAYLOAD" "$RESPONSE"
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
    error) dump_diagnostics; fail $EX_AGENT "conversation ended with execution_status=error: $(conversation_error "$CID")" ;;
    stuck) dump_diagnostics; fail $EX_AGENT "stuck detection fired; intervene with: sudo -u $AGENT_USER $HERE/send_fix.sh $CID <message-file>" ;;
    waiting_for_confirmation|paused)
      dump_diagnostics; fail $EX_HUMAN "conversation needs a human ($STATUS); confirmation is never granted automatically" ;;
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
# the events endpoint takes no query parameters; /events/search is the paginated
# listing and is used as a fallback when the plain dump comes back empty
oh_curl GET "/api/conversations/$CID/events" >"$RUN_DIR/events.json" 2>/dev/null
[ -s "$RUN_DIR/events.json" ] \
  || oh_curl GET "/api/conversations/$CID/events/search" >"$RUN_DIR/events.json" 2>/dev/null
if grep -qi 'verify-gate: make verify PASS' "$RUN_DIR/events.json" 2>/dev/null; then
  GATE_HOOK="pass"
elif grep -qi '"decision"[^}]*"deny"\|make verify failed' "$RUN_DIR/events.json" 2>/dev/null; then
  GATE_HOOK="deny"
  fail $EX_AGENT "stop hook denied the finish: make verify was red in the sandbox"
else
  GATE_HOOK="unknown"
fi
fi

if [ "$EXTERNAL_COLLECT" = "1" ]; then
  # From this point the workspace is model-controlled. This credential-bearing
  # runner must never execute Git there; a separate no-network/no-secret UID
  # creates raw transport bytes and Harper performs every trust gate.
  GATE_DIRTY="deferred-to-harper"
  GATE_ANCESTRY="deferred-to-harper"
  GATE_PATHS="deferred-to-harper"
  GATE_SECRETS="deferred-to-harper"
  done_ok
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
[ "$BRIDGE_TRUSTED_OUTPUT" != "1" ] || SANDBOX_BUNDLE="$RUN_DIR/result.bundle"
# same `base..branch` form collect_branch.sh uses; that script itself cannot be
# invoked here because it lives under /home/proxima-admin (0750) where
# openhands-agent has no traverse rights
A bundle create "$SANDBOX_BUNDLE" "$BASE_SHA..$BRANCH" >/dev/null 2>&1 \
  || fail $EX_INFRA "bundle create failed in the sandbox"
A bundle verify "$SANDBOX_BUNDLE" >/dev/null 2>&1 \
  || fail $EX_INTEGRITY "bundle does not verify inside the sandbox"
# freeze before copying: same uid could otherwise swap the file underneath us
if [ "$BRIDGE_TRUSTED_OUTPUT" = "1" ]; then
  RESULT_BUNDLE="$SANDBOX_BUNDLE"
  chmod 600 "$RESULT_BUNDLE" || fail $EX_INFRA "cannot protect trusted result bundle"
  SANDBOX_SHA="$(sha256sum "$RESULT_BUNDLE" | cut -d' ' -f1)"
else
  if [ -n "$SUDO_CMD" ]; then priv chown root:root "$SANDBOX_BUNDLE"; fi
  priv chmod 600 "$SANDBOX_BUNDLE"
  SANDBOX_SHA="$(priv sha256sum "$SANDBOX_BUNDLE" | cut -d' ' -f1)"
  RESULT_BUNDLE="$RUN_DIR/result.bundle"
  priv install -m 0600 -o "$(id -un)" -g "$(id -gn)" "$SANDBOX_BUNDLE" "$RESULT_BUNDLE" \
    || fail $EX_INFRA "cannot copy the result bundle out of the sandbox"
  priv rm -f "$SANDBOX_BUNDLE"
fi
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

SECRET_HIT="$(REPO_ROOT="$REPO_ROOT" /usr/bin/python3 -I - "$SOURCE_DIR" "$BASE_SHA" "$LOCAL_REF" <<'PY'
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
