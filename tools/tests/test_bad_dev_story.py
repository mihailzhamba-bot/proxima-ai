"""Offline coverage for tools/orchestrator/bad_dev_story.sh.

The script's privileged calls go through a seam (BRIDGE_SUDO / BRIDGE_AGENT_USER):
with both empty it provisions, gates, collects and fetches entirely as the current
user in a temporary workspace root, so the whole git path is exercised without
sudo, without the OpenHands server and without touching /srv.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "orchestrator" / "bad_dev_story.sh"
COMMIT = "git -c user.email=w@w -c user.name=w commit -qm"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


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


def run_bridge(sandbox: dict, run_id: str, simulate: str, *extra: str) -> dict:
    env = dict(os.environ)
    env.update(
        BRIDGE_SUDO="",
        BRIDGE_AGENT_USER="",
        WORKSPACE_ROOT=str(sandbox["root"] / "ws"),
        REPO_ROOT=str(sandbox["source"]),
    )
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


def test_happy_path_fetches_commits(sandbox: dict) -> None:
    payload = run_bridge(
        sandbox, "ok-run", f"echo hi > NEW.md && git add NEW.md && {COMMIT} 'feat: add NEW.md'"
    )
    assert payload["exit_code"] == 0
    assert payload["commits"] == 1
    assert payload["local_ref"] == "refs/openhands/ok-run/1/head"
    assert all(value in {"pass", "simulated"} for value in payload["gates"].values())
    assert git(sandbox["source"], "rev-parse", payload["local_ref"]) == payload["head_sha"]


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
