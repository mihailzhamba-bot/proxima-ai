"""Offline coverage for tools/orchestrator/bad_dev_story.sh.

The script's privileged calls go through a seam (BRIDGE_SUDO / BRIDGE_AGENT_USER):
with both empty it provisions, gates, collects and fetches entirely as the current
user in a temporary workspace root, so the whole git path is exercised without
sudo, without the OpenHands server and without touching /srv.
"""

from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import worker_dispatch as worker_dispatch_module

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "orchestrator" / "bad_dev_story.sh"
WORKER_DISPATCH = ROOT / "tools" / "loop" / "worker_dispatch.py"
COMMIT = "git -c user.email=w@w -c user.name=w commit -qm"
PROFILE_ID = "11111111-1111-4111-8111-111111111111"
PROFILE_REVISION = 3

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


@contextmanager
def profile_server(*,revision: int = PROFILE_REVISION):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!="/api/agent-profiles/loop-codex" or self.headers.get("X-Session-API-Key")!="k"*48:
                self.send_response(404);self.end_headers();return
            raw=json.dumps({"name":"loop-codex","profile":{"id":PROFILE_ID,"revision":revision,"acp_command":"/opt/loop-openhands-agent/bin/codex-acp","acp_args":[],"acp_model":"gpt-5.6-sol","acp_session_mode":"agent","acp_startup_timeout":90.0,"acp_prompt_timeout":1800.0,"mcp_server_refs":[]}}).encode()
            self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,*_args):pass
    server=ThreadingHTTPServer(("127.0.0.1",18002),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield
    finally:server.shutdown();server.server_close();thread.join(timeout=2)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture()
def sandbox(tmp_path: Path) -> dict:
    source = tmp_path / "src"
    (source / "tools").mkdir(parents=True)
    (source / "db" / "migrations").mkdir(parents=True)
    git(tmp_path, "init", "-q", str(source))
    git(source, "config", "user.email", "t@t")
    git(source, "config", "user.name", "t")
    (source / "AGENTS.md").write_text("AGENTS\n", encoding="utf-8")
    (source / "db" / "migrations" / "001_init.sql").write_text("BEGIN; COMMIT;\n", encoding="utf-8")
    shutil.copy(ROOT / "tools" / "secret_scan.py", source / "tools" / "secret_scan.py")
    git(source, "add", "-A")
    git(source, "commit", "-qm", "base")
    git(source, "checkout", "-qb", "feat/base-line")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("unit of work\n", encoding="utf-8")
    return {"root": tmp_path, "source": source, "prompt": prompt}


SUDO_SHIM = """#!/bin/bash
# Stands in for sudo: drops -n and -u <user>, runs the rest as the current user.
while [ $# -gt 0 ]; do
  case "$1" in
    -n) shift ;;
    -u) shift 2 ;;
    *) break ;;
  esac
done
if [ "$1" = "install" ]; then
  shift
  args=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -o|-g) shift 2 ;;
      *) args+=("$1"); shift ;;
    esac
  done
  exec install "${args[@]}"
fi
if [ "$1" = "chown" ]; then
  exit 0
fi
exec "$@"
"""


def run_bridge(
    sandbox: dict,
    run_id: str,
    simulate: str,
    *extra: str,
    privileged: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> dict:
    env = dict(os.environ)
    if privileged:
        # exercise the real elevation code path, including its quoting
        shim = sandbox["root"] / "fake-sudo"
        shim.write_text(SUDO_SHIM, encoding="utf-8")
        shim.chmod(0o755)
        env.update(BRIDGE_SUDO_CMD=str(shim), BRIDGE_AGENT_USER=os.environ.get("USER", "root"))
        env.pop("BRIDGE_SUDO", None)
    else:
        env.update(BRIDGE_SUDO="", BRIDGE_AGENT_USER="")
    env.update(
        WORKSPACE_ROOT=str(sandbox["root"] / "ws"),
        REPO_ROOT=str(sandbox["source"]),
    )
    env.update(env_overrides or {})
    result = subprocess.run(
        [
            str(SCRIPT),
            "--run-id", run_id,
            "--branch", "feat/smoke",
            "--base-ref", "feat/base-line",
            "--prompt-file", str(sandbox["prompt"]),
            "--source-dir", str(sandbox["source"]),
            "--contract-file", "AGENTS.md",
            "--simulate-worker", simulate,
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.stdout.strip(), f"no JSON on stdout; stderr:\n{result.stderr}"
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["exit_code"] == result.returncode
    return payload


FAKE_CURL = r"""#!/usr/bin/env python3
import json
import os
import sys
from urllib.parse import urlsplit

method = sys.argv[sys.argv.index("-X") + 1]
request = urlsplit(sys.argv[-1])
path = request.path
body = {}
if "-d" in sys.argv:
    value=sys.argv[sys.argv.index("-d")+1]
    if value.startswith("@"):
        body=json.load(open(value[1:],encoding="utf-8"))
if method == "GET" and path == "/api/conversations/count":
    print("0")
elif method == "POST" and path == "/api/conversations":
    revision=int(os.environ.get("FAKE_LAUNCHED_REVISION",os.environ["BRIDGE_PROFILE_REVISION"]))
    print(json.dumps({"id":body["conversation_id"],"launched_agent_profile":{"agent_profile_id":body["agent_profile_id"],"revision":revision}}))
elif method == "POST" and path.endswith("/events"):
    print(json.dumps({"success":True}))
elif method == "GET" and path == "/api/conversations":
    print(json.dumps([{"execution_status": "error"}]))
elif method == "GET" and path.endswith("/agent_final_response"):
    print(json.dumps({"response": ""}))
elif method == "GET" and path.endswith("/events"):
    print("[]")
elif method == "GET" and path.startswith("/api/conversations/"):
    print(json.dumps({"persistence_dir": os.environ["FAKE_PERSISTENCE_DIR"]}))
else:
    print("{}")
"""


def conversation_id(run_id: str, attempt: int = 1) -> str:
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "https://proxima.local/bad-dev-story")
    return str(uuid.uuid5(namespace, f"{run_id}/{attempt}"))


def run_api_error(
    sandbox: dict,
    run_id: str,
    persistence_dir: Path | str,
    persistence_root: Path,
    launched_revision: int | None = None,
    dedicated: bool = False,
) -> dict:
    fake_bin = sandbox["root"] / "fake-bin"
    fake_bin.mkdir()
    for name, content in {
        "curl": FAKE_CURL,
        "conductor": "#!/bin/bash\nprintf '{\"workers\":[]}\\n'\n",
        "sleep": "#!/bin/bash\nexit 0\n",
    }.items():
        executable = fake_bin / name
        executable.write_text("#!/bin/bash\nexit 1\n" if dedicated and name == "conductor" else content, encoding="utf-8")
        executable.chmod(0o755)
    key_file = sandbox["root"] / "openhands-loop.env"
    key_file.write_text("LOCAL_BACKEND_API_KEY=fixture-only\n", encoding="utf-8")
    key_file.chmod(0o600)
    env = dict(os.environ)
    env.update(
        BRIDGE_SUDO="",
        BRIDGE_AGENT_USER="",
        WORKSPACE_ROOT=str(sandbox["root"] / "api-ws"),
        REPO_ROOT=str(sandbox["source"]),
        OH_BASE="http://fixture.invalid",
        OH_KEY_FILE=str(key_file),
        OPENHANDS_PERSISTENCE_ROOT=str(persistence_root),
        FAKE_PERSISTENCE_DIR=str(persistence_dir),
        BRIDGE_PROFILE_REVISION=str(PROFILE_REVISION),
        PATH=f"{fake_bin}:{env['PATH']}",
    )
    if launched_revision is not None:env["FAKE_LAUNCHED_REVISION"]=str(launched_revision)
    if dedicated:env["BRIDGE_TRUSTED_OUTPUT"]="1"
    result = subprocess.run(
        [
            str(SCRIPT),
            "--run-id",
            run_id,
            "--branch",
            "feat/smoke",
            "--base-ref",
            "feat/base-line",
            "--prompt-file",
            str(sandbox["prompt"]),
            "--source-dir",
            str(sandbox["source"]),
            "--contract-file",
            "AGENTS.md",
            *(["--external-collect"] if dedicated else []),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.stdout.strip(), result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_happy_path_fetches_commits(sandbox: dict) -> None:
    payload = run_bridge(
        sandbox, "ok-run", f"echo hi > NEW.md && git add NEW.md && {COMMIT} 'feat: add NEW.md'"
    )
    assert payload["exit_code"] == 0, payload["problem"]
    assert payload["commits"] == 1
    assert payload["local_ref"] == "refs/openhands/ok-run/1/head"
    assert all(value in {"pass", "simulated"} for value in payload["gates"].values())
    assert git(sandbox["source"], "rev-parse", payload["local_ref"]) == payload["head_sha"]


def test_approved_repo_cannot_shadow_privileged_python_stdlib(sandbox: dict) -> None:
    marker=sandbox["root"]/"python-shadow-owned"
    (sandbox["source"]/"json.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('shadow executed')\n",encoding="utf-8")
    payload=run_bridge(sandbox,"isolated-python",f"echo ok > SAFE.md && git add SAFE.md && {COMMIT} 'test: isolated python'")
    assert payload["exit_code"]==0,payload["problem"]
    assert not marker.exists()


def test_emit_treats_shell_and_python_syntax_as_workspace_data(sandbox: dict) -> None:
    marker = sandbox["root"] / "emit-shell-owned"
    hostile_root = sandbox["root"] / (
        f'ws"$(touch {marker})__import__("pathlib").Path("owned").touch()'
    )
    payload = run_bridge(
        sandbox,
        "emit-data",
        f"echo hi > NEW.md && git add NEW.md && {COMMIT} 'feat: data transport'",
        env_overrides={"WORKSPACE_ROOT": str(hostile_root)},
    )
    expected = hostile_root / conversation_id("emit-data").replace("-", "")
    assert payload["workspace"] == str(expected)
    assert payload["exit_code"] == 0, payload["problem"]
    assert not marker.exists()


def test_api_persistence_path_cannot_inject_a_shell_command(sandbox: dict) -> None:
    persistence_root = sandbox["root"] / "persistence"
    persistence_root.mkdir()
    marker = sandbox["root"] / "persistence-shell-owned"
    hostile_path = f"{sandbox['root']}/outside'; touch {marker}; #"
    payload = run_api_error(sandbox, "api-inject", hostile_path, persistence_root)
    assert payload["exit_code"] == 4
    assert not marker.exists()


def test_conversation_profile_revision_is_verified_before_run(sandbox: dict) -> None:
    persistence_root=sandbox["root"]/"profile-race-persistence";persistence_root.mkdir()
    payload=run_api_error(sandbox,"profile-race",persistence_root,persistence_root,PROFILE_REVISION+1)
    assert payload["exit_code"]!=0 and "Agent Profile differs" in payload["problem"]


def test_trusted_persisted_error_is_read_as_data(sandbox: dict) -> None:
    run_id = "api-event"
    persistence_root = sandbox["root"] / "persistence"
    event_dir = persistence_root / conversation_id(run_id) / "events"
    event_dir.mkdir(parents=True)
    marker = sandbox["root"] / "event-python-owned"
    detail = f'quote " and newline\n__import__("pathlib").Path("{marker}").touch()'
    (event_dir / "001.json").write_text(
        json.dumps({"kind": "ErrorEvent", "code": "E_TEST", "detail": detail}),
        encoding="utf-8",
    )
    payload = run_api_error(sandbox, run_id, event_dir.parent, persistence_root)
    assert payload["exit_code"] == 4
    assert "E_TEST: quote \" and newline" in payload["problem"]
    assert not marker.exists()


def test_sandbox_has_no_remote(sandbox: dict) -> None:
    """Story 1.1 attempt 1 failed because a 404 fetch fell back to a stale cache."""
    payload = run_bridge(
        sandbox,
        "no-remote",
        f"test -z \"$(git remote)\" && echo ok > R.md && git add R.md && {COMMIT} 'chore: no remote'",
    )
    assert payload["exit_code"] == 0


def test_forbidden_path_blocks(sandbox: dict) -> None:
    payload = run_bridge(
        sandbox, "forbid", f"echo x > tools/verify_wb_client.py && git add -A && {COMMIT} 'chore: gate'"
    )
    assert payload["exit_code"] == 7
    assert payload["gates"]["forbidden_paths"] == "fail"
    assert "tools/verify_wb_client.py" in payload["problem"]
    assert not payload["local_ref"], "a ref that failed a gate must be dropped"


def test_allow_path_overrides_the_denylist(sandbox: dict) -> None:
    payload = run_bridge(
        sandbox,
        "allowed",
        f"echo x > tools/verify_wb_client.py && git add -A && {COMMIT} 'chore: gate'",
        "--allow-path",
        "tools/verify_wb_client.py",
    )
    assert payload["exit_code"] == 0


def test_existing_migration_is_immutable_but_new_one_passes(sandbox: dict) -> None:
    edited = run_bridge(
        sandbox, "mig-edit", f"echo BAD >> db/migrations/001_init.sql && git add -A && {COMMIT} 'chore: edit'"
    )
    assert edited["exit_code"] == 7
    assert "001_init.sql" in edited["problem"]

    added = run_bridge(
        sandbox,
        "mig-new",
        f"printf 'BEGIN; COMMIT;\\n' > db/migrations/002_new.sql && git add -A && {COMMIT} 'feat: migration'",
    )
    assert added["exit_code"] == 0


def test_secret_in_incoming_commits_blocks(sandbox: dict) -> None:
    token = "ghp_" + "A" * 36
    payload = run_bridge(
        sandbox, "secret", f"printf 'tok=%s\\n' {token} > cfg.txt && git add -A && {COMMIT} 'chore: cfg'"
    )
    assert payload["exit_code"] == 7
    assert payload["gates"]["secret_scan"] == "fail"
    assert "github-token" in payload["problem"]
    assert not payload["local_ref"], "a ref that failed a gate must be dropped"


def test_dirty_sandbox_needs_a_human(sandbox: dict) -> None:
    payload = run_bridge(sandbox, "dirty", "echo x > NEW.md && git add NEW.md")
    assert payload["exit_code"] == 3
    assert payload["gates"]["sandbox_clean"] == "fail"


def test_no_commits_is_an_agent_failure(sandbox: dict) -> None:
    payload = run_bridge(sandbox, "empty", "true")
    assert payload["exit_code"] == 4


def test_foreign_base_fails_ancestry(sandbox: dict) -> None:
    payload = run_bridge(
        sandbox,
        "foreign",
        "git checkout -q --orphan tmproot && git rm -rqf . && echo z > Z.md && git add Z.md && "
        f"{COMMIT} 'chore: orphan' && git branch -qf feat/smoke tmproot && git checkout -q feat/smoke",
    )
    assert payload["exit_code"] == 7
    assert payload["gates"]["ancestry"] == "fail"
    assert not payload["local_ref"], "a ref that failed a gate must be dropped"
    missing = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "refs/openhands/foreign/1/head"],
        cwd=sandbox["source"], capture_output=True, text=True,
    )
    assert missing.returncode != 0, "the failed ref must not survive in the local clone"


def test_contract_drift_blocks_before_dispatch(sandbox: dict) -> None:
    """A file present locally but absent from the base commit must not silently differ."""
    (sandbox["source"] / "DRIFT.md").write_text("local draft\n", encoding="utf-8")
    payload = run_bridge(sandbox, "drift", "true", "--contract-file", "DRIFT.md")
    assert payload["exit_code"] == 7
    assert payload["gates"]["contract_files"] == "fail"
    assert payload["conversation_id"], "the gate must run after the workspace is identified"


def test_workspace_collision_refuses(sandbox: dict) -> None:
    first = run_bridge(
        sandbox, "collide", f"echo a > A.md && git add -A && {COMMIT} 'chore: a'", "--keep-workspace"
    )
    assert first["exit_code"] == 0
    again = run_bridge(sandbox, "collide", "true")
    assert again["exit_code"] == 2
    assert "--attempt" in again["problem"]


def test_argument_validation() -> None:
    for args, reason in [
        (["--run-id", "BAD ID", "--branch", "feat/x", "--base-ref", "HEAD", "--prompt-file", "/dev/null"], "run-id"),
        (["--run-id", "ok-id", "--branch", "main", "--base-ref", "HEAD", "--prompt-file", "/dev/null"], "branch"),
    ]:
        result = subprocess.run([str(SCRIPT), *args], capture_output=True, text=True)
        assert result.returncode == 2, reason


def test_contract_gate_passes_through_the_privileged_path(sandbox: dict) -> None:
    """Regression: the elevation command must survive a newline IFS.

    The contract-file loop sets IFS to a newline. An unquoted multi-word
    elevation command collapses into one unfindable word there, every sandbox
    hash comes back empty, and the gate fails on files that actually match.
    """
    payload = run_bridge(
        sandbox,
        "privileged",
        f"echo hi > NEW.md && git add NEW.md && {COMMIT} 'feat: add NEW.md'",
        privileged=True,
    )
    assert payload["gates"]["contract_files"] == "pass", payload["problem"]
    assert payload["exit_code"] == 0
    assert payload["commits"] == 1


def test_seed_bundle_excludes_unrelated_refs_and_objects(sandbox: dict) -> None:
    source=sandbox["source"]
    base=git(source,"rev-parse","HEAD")
    original=git(source,"rev-parse","--abbrev-ref","HEAD")
    git(source,"checkout","-qb","unrelated-secret")
    (source/"SIDE.txt").write_text("ghp_"+"Z"*36+"\n",encoding="utf-8")
    git(source,"add","SIDE.txt");git(source,"commit","-qm","side only")
    side=git(source,"rev-parse","HEAD")
    git(source,"checkout","-q",original)
    assert git(source,"rev-parse","HEAD")==base
    payload=run_bridge(sandbox,"scoped-seed",f"echo hi > NEW.md && git add NEW.md && {COMMIT} 'feat: scoped seed'","--keep-workspace")
    assert payload["exit_code"]==0,payload["problem"]
    probe=subprocess.run(["git","-C",payload["workspace"]+"/proxima-ai","cat-file","-e",side],capture_output=True)
    assert probe.returncode!=0


def test_external_collect_never_runs_git_after_model_terminal(sandbox: dict) -> None:
    marker=sandbox["root"]/"runner-secret-context-executed"
    command=(
        f"echo hi > NEW.md && git add NEW.md && {COMMIT} 'feat: external collect' && "
        f"git config core.fsmonitor 'touch {marker}'"
    )
    payload=run_bridge(sandbox,"external-collect",command,"--external-collect","--keep-workspace")
    assert payload["exit_code"]==0,payload["problem"]
    assert payload["gates"]["ancestry"]=="deferred-to-harper"
    assert not marker.exists()


def worker_dispatch_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "worker-source"
    script = source / "tools" / "orchestrator" / "bad_dev_story.sh"
    script.parent.mkdir(parents=True)
    (source / ".git").mkdir()
    capture = tmp_path / "child-env.txt"
    arguments = tmp_path / "child-arguments.txt"
    script.write_text(
        "#!/bin/bash\n"
        f"/usr/bin/env > {shlex.quote(str(capture))}\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(str(arguments))}\n",
        encoding="utf-8",
    )

    runtime_home = tmp_path / "runtime-home"
    workspace_root = tmp_path / "model-workspaces"
    workspace_root.mkdir(parents=True)
    os.chown(workspace_root,-1,os.getegid())
    workspace_root.chmod(0o2770)
    runtime_home.mkdir()
    run_root = tmp_path / "runner-state"
    run_root.mkdir()
    (run_root/"tmp").mkdir()
    persistence = tmp_path / "persistence"
    persistence.mkdir()
    key_file = tmp_path / "loop-openhands.env"
    key_file.write_text("LOCAL_BACKEND_API_KEY="+"k"*48+"\n", encoding="utf-8")
    key_file.chmod(0o600)
    prompt = tmp_path / "trusted-prompt.txt"
    prompt.write_text("trusted job\n", encoding="utf-8")
    delivery_root=tmp_path/"delivery-prompts";delivery_root.mkdir()
    template={"base_sha":"a"*40,"prompt_file":str(prompt),"prompt_sha256":hashlib.sha256(prompt.read_bytes()).hexdigest(),
              "allowed_paths":["services/webapp/src/lib/fixture.ts"],"profile":"fedor","profile_id":PROFILE_ID,"profile_revision":PROFILE_REVISION}
    (delivery_root/"fixture-job.txt").write_bytes(worker_dispatch_module.delivery_prompt_bytes(prompt.read_bytes(),template))
    (delivery_root/"fixture-job.txt").chmod(0o640)
    config = tmp_path / "worker-config.json"
    config.write_text(
        json.dumps(
            {
                "source_repo": str(source),
                "runtime_home": str(runtime_home),
                "runtime_user": "loop-worker-runner",
                "run_root": str(run_root),
                "prompt_root": str(tmp_path),
                "workspace_root": str(workspace_root),
                "delivery_prompt_root": str(delivery_root),
                "openhands_base_url": "http://127.0.0.1:18002",
                "openhands_key_file": str(key_file),
                "openhands_persistence_root": str(persistence),
                "profile_fedor": PROFILE_ID,
                "profile_fedor_revision": PROFILE_REVISION,
                "lang": "C",
                "templates": {
                    "fixture": template
                },
            }
        ),
        encoding="utf-8",
    )
    return config, capture, key_file


def test_worker_dispatch_uses_only_dedicated_runtime_environment(tmp_path: Path) -> None:
    config, capture, key_file = worker_dispatch_fixture(tmp_path)
    bash_env = tmp_path / "hostile-bash-env"
    bash_marker = tmp_path / "inherited-bash-env-owned"
    bash_env.write_text(f"touch {shlex.quote(str(bash_marker))}\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(
        OPENAI_API_KEY="shared-openai-must-not-leak",
        LOCAL_BACKEND_API_KEY="shared-session-must-not-leak",
        OH_KEY_FILE="/home/openhands-agent/.agent-canvas.env",
        BRIDGE_SUDO_CMD="/tmp/shared-sudo-must-not-leak",
        PYTHONPATH="/tmp/shared-pythonpath-must-not-leak",
        BASH_ENV=str(bash_env),
        GIT_CONFIG_GLOBAL="/tmp/shared-git-config-must-not-leak",
    )
    with profile_server():
        result = subprocess.run(
            [
                sys.executable,
                str(WORKER_DISPATCH),
                "--config",
                str(config),
                "--job",
                "fixture-job",
                "--template",
                "fixture",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
    assert result.returncode == 0, result.stderr
    child_env = dict(
        line.split("=", 1) for line in capture.read_text(encoding="utf-8").splitlines()
    )
    assert child_env["OH_KEY_FILE"] == str(key_file)
    assert child_env["BRIDGE_SUDO"] == ""
    assert child_env["BRIDGE_AGENT_USER"] == ""
    assert child_env["HOME"].endswith("runtime-home")
    assert child_env["TMPDIR"].endswith("runner-state/tmp")
    assert child_env["BRIDGE_TRUSTED_OUTPUT"] == "1"
    assert child_env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert child_env["GIT_CONFIG_SYSTEM"] == "/dev/null"
    assert child_env["GIT_CONFIG_NOSYSTEM"] == "1"
    child_args=(tmp_path/"child-arguments.txt").read_text().splitlines()
    delivered=Path(json.loads(config.read_text())["delivery_prompt_root"])/"fixture-job.txt"
    assert child_args[child_args.index("--prompt-file")+1]==str(delivered)
    raw=Path(json.loads(config.read_text())["templates"]["fixture"]["prompt_file"]).read_bytes()
    assert child_env["BRIDGE_RAW_PROMPT_SHA256"]==hashlib.sha256(raw).hexdigest()
    assert child_env["BRIDGE_DELIVERY_PROMPT_SHA256"]==hashlib.sha256(delivered.read_bytes()).hexdigest()
    for forbidden in (
        "OPENAI_API_KEY",
        "LOCAL_BACKEND_API_KEY",
        "BRIDGE_SUDO_CMD",
        "PYTHONPATH",
        "BASH_ENV",
    ):
        assert forbidden not in child_env
    assert not bash_marker.exists()


def test_worker_dispatch_rejects_changed_live_profile_revision(tmp_path: Path) -> None:
    config,_,_=worker_dispatch_fixture(tmp_path)
    with profile_server(revision=PROFILE_REVISION+1):
        result=subprocess.run([sys.executable,str(WORKER_DISPATCH),"--config",str(config),"--job","fixture-job","--template","fixture"],capture_output=True,text=True)
    assert result.returncode!=0 and "identity changed" in result.stderr


def test_worker_dispatch_rejects_shared_agent_canvas_key(tmp_path: Path) -> None:
    config, _, _ = worker_dispatch_fixture(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["openhands_key_file"] = "/home/openhands-agent/.agent-canvas.env"
    config.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(WORKER_DISPATCH),
            "--config",
            str(config),
            "--job",
            "fixture-job",
            "--template",
            "fixture",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "shared Agent Canvas env is forbidden" in result.stderr


@pytest.mark.parametrize("url",[
    "https://127.0.0.1:18002",
    "http://135.106.186.210:18002",
    "http://127.0.0.1:18000",
    "http://user:secret@127.0.0.1:18002",
])
def test_worker_dispatch_rejects_non_dedicated_openhands_url(tmp_path: Path,url: str) -> None:
    config, _, _ = worker_dispatch_fixture(tmp_path)
    payload=json.loads(config.read_text(encoding="utf-8"))
    payload["openhands_base_url"]=url
    config.write_text(json.dumps(payload),encoding="utf-8")
    result=subprocess.run([sys.executable,str(WORKER_DISPATCH),"--config",str(config),"--job","fixture-job","--template","fixture"],capture_output=True,text=True)
    assert result.returncode != 0
    assert "invalid openhands_base_url" in result.stderr


def test_worker_dispatch_rejects_prompt_drift_and_empty_allowlist(tmp_path: Path) -> None:
    config, _, _ = worker_dispatch_fixture(tmp_path)
    payload=json.loads(config.read_text(encoding="utf-8"))
    Path(payload["templates"]["fixture"]["prompt_file"]).write_text("changed after approval\n",encoding="utf-8")
    config.write_text(json.dumps(payload),encoding="utf-8")
    command=[sys.executable,str(WORKER_DISPATCH),"--config",str(config),"--job","fixture-job","--template","fixture"]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode != 0 and "prompt hash differs" in result.stderr
    prompt=Path(payload["templates"]["fixture"]["prompt_file"])
    payload["templates"]["fixture"]["prompt_sha256"]=hashlib.sha256(prompt.read_bytes()).hexdigest()
    payload["templates"]["fixture"]["allowed_paths"]=[]
    config.write_text(json.dumps(payload),encoding="utf-8")
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode != 0 and "non-empty allowed_paths" in result.stderr


def test_isolated_dispatch_does_not_read_shared_conductor(sandbox: dict) -> None:
    persistence=sandbox['root']/'persistence';persistence.mkdir()
    result=run_api_error(sandbox,'isolated-conductor',persistence,persistence,dedicated=True)
    assert result['exit_code']==4
    assert 'conductor' not in result['problem']
