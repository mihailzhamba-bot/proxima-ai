"""Dispatch one trusted LOOP template to the local OpenHands API."""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
import urllib.request


SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SHARED_AGENT_CANVAS_ENV = Path("/home/openhands-agent/.agent-canvas.env")


def template_fingerprint(name: str,definition: dict) -> str:
    portable={key:definition.get(key) for key in ("base_sha","prompt_sha256","allowed_paths","contract_files","profile","profile_id","profile_revision")}
    for key in ("allowed_paths","contract_files"):
        if isinstance(portable[key],list):portable[key]=sorted(portable[key])
    return hashlib.sha256(json.dumps({"name":name,"contract":portable},sort_keys=True,separators=(",",":")).encode()).hexdigest()


def trusted_regular_file(path: Path, *, secret: bool = False) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SystemExit(f"invalid trusted file: {path}")
    mode = path.stat().st_mode
    if mode & 0o022:
        raise SystemExit(f"trusted file must not be group/world writable: {path}")
    if secret and mode & 0o777 != 0o600:
        raise SystemExit(f"secret file must have mode 0600: {path}")
    if secret and path.stat().st_uid != os.geteuid():
        raise SystemExit(f"secret file must belong to the LOOP runner: {path}")
    return path


def trusted_directory(path: Path, label: str, *, shared: bool = False) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise SystemExit(f"invalid {label}: {path}")
    info=path.stat()
    if info.st_mode & (0o002 if shared else 0o022):
        raise SystemExit(f"{label} must not be group/world writable: {path}")
    if shared and (info.st_gid!=os.getegid() or (sys.platform=="linux" and not info.st_mode & stat.S_ISGID)):
        raise SystemExit(f"{label} must be setgid to the LOOP shared group: {path}")
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        raise SystemExit(f"{label} is not usable by the LOOP runtime: {path}")
    return path


def openhands_base_url(value: object) -> str:
    if not isinstance(value, str) or any(character.isspace() for character in value):
        raise SystemExit("openhands_base_url is required")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise SystemExit("invalid openhands_base_url") from error
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or port != 18002:
        raise SystemExit("invalid openhands_base_url")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise SystemExit("invalid openhands_base_url")
    return value.rstrip("/")


def required_path(config: dict, name: str) -> Path:
    value = config.get(name)
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SystemExit(f"{name} is required")
    return Path(value)


def live_profile_identity(config: dict,base_url: str,session_key: str) -> tuple[str,int]:
    expected_id=config.get("profile_fedor");expected_revision=config.get("profile_fedor_revision")
    if not isinstance(expected_id,str) or not re.fullmatch(r"[0-9a-f-]{36}",expected_id) or not isinstance(expected_revision,int) or isinstance(expected_revision,bool) or expected_revision<0:
        raise SystemExit("dedicated Agent Profile binding is missing")
    request=urllib.request.Request(base_url+"/api/agent-profiles/loop-codex",headers={"X-Session-API-Key":session_key})
    try:
        with urllib.request.urlopen(request,timeout=10) as response:profile=json.load(response).get("profile",{})
    except Exception as error:
        raise SystemExit("dedicated Agent Profile cannot be verified") from error
    if profile.get("id")!=expected_id or profile.get("revision")!=expected_revision:
        raise SystemExit("dedicated Agent Profile identity changed")
    if profile.get("acp_command")!="/opt/loop-openhands-agent/bin/codex-acp" or profile.get("acp_args")!=[] or profile.get("acp_model")!="gpt-5.6-sol" or profile.get("acp_session_mode")!="agent" or profile.get("acp_startup_timeout")!=90.0 or profile.get("acp_prompt_timeout")!=1800.0 or profile.get("mcp_server_refs")!=[]:
        raise SystemExit("dedicated Agent Profile contract changed")
    return expected_id,expected_revision


def admitted_paths(template: dict) -> list[str]:
    values = template.get("allowed_paths")
    if not isinstance(values, list) or not values:
        raise SystemExit("template needs an explicit non-empty allowed_paths list")
    admitted = []
    for value in values:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise SystemExit("invalid allowed path")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or path.parts[0] == ".git":
            raise SystemExit("invalid allowed path")
        admitted.append(value)
    return admitted


def admitted_relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SystemExit(f"invalid {label}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.parts[0] == ".git":
        raise SystemExit(f"invalid {label}")
    return value


def child_environment(config: dict, root: Path) -> dict[str, str]:
    runtime_home = trusted_directory(required_path(config, "runtime_home"), "runtime_home")
    workspace_root = trusted_directory(required_path(config, "workspace_root"), "workspace_root", shared=True)
    run_root = trusted_directory(required_path(config, "run_root"), "run_root")
    runtime_tmp=trusted_directory(run_root/"tmp","runtime tmp")
    if config.get("runtime_user") != "loop-worker-runner":
        raise SystemExit("runtime_user must be loop-worker-runner")
    key_path = required_path(config, "openhands_key_file")
    if key_path == SHARED_AGENT_CANVAS_ENV:
        raise SystemExit("shared Agent Canvas env is forbidden; configure a dedicated LOOP key file")
    key_file = trusted_regular_file(key_path, secret=True)
    values={}
    for line in key_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            name,value=line.split("=",1);values[name]=value
    session_key=values.get("LOCAL_BACKEND_API_KEY","")
    if len(session_key)<32 or session_key.strip()!=session_key:
        raise SystemExit("dedicated LOOP OpenHands key is malformed")
    persistence_root = required_path(config, "openhands_persistence_root")
    if not persistence_root.is_absolute() or persistence_root.is_symlink() or not persistence_root.is_dir():
        raise SystemExit("openhands_persistence_root must be absolute")

    base_url=openhands_base_url(config.get("openhands_base_url"));profile_id,profile_revision=live_profile_identity(config,base_url,session_key)
    env = {
        "PATH": SAFE_PATH,
        "HOME": str(runtime_home),
        "USER": str(config.get("runtime_user", "loop-worker")),
        "LOGNAME": str(config.get("runtime_user", "loop-worker")),
        "LANG": str(config.get("lang", "C.UTF-8")),
        "LC_ALL": str(config.get("lang", "C.UTF-8")),
        "TMPDIR": str(runtime_tmp),
        "REPO_ROOT": str(root),
        "WORKSPACE_ROOT": str(workspace_root),
        "OH_BASE": base_url,
        "OH_KEY_FILE": str(key_file),
        "OPENHANDS_PERSISTENCE_ROOT": str(persistence_root),
        "BRIDGE_SUDO": "",
        "BRIDGE_AGENT_USER": "",
        "BRIDGE_RUN_ROOT": str(run_root),
        "BRIDGE_RECEIPT_DIR": str(run_root / "receipts"),
        "BRIDGE_SHARED_WORKSPACE": "1",
        "BRIDGE_TRUSTED_OUTPUT": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "PROFILE_FEDOR": profile_id,
        "BRIDGE_PROFILE_REVISION": str(profile_revision),
    }
    for config_name, env_name in (
        ("profile_fedor", "PROFILE_FEDOR"),
        ("profile_glm", "PROFILE_GLM"),
        ("title_llm_profile", "BRIDGE_TITLE_LLM_PROFILE"),
    ):
        value = config.get(config_name)
        if value is not None:
            if not isinstance(value, str) or not value or "\x00" in value:
                raise SystemExit(f"invalid {config_name}")
            env[env_name] = value
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--template", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", args.job):
        raise SystemExit("invalid job")

    config_path = trusted_regular_file(Path(args.config))
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit("invalid worker config") from error
    template = config.get("templates", {}).get(args.template)
    if not isinstance(template, dict):
        raise SystemExit("unknown template")
    if not re.fullmatch(r"[0-9a-f]{40}", str(template.get("base_sha", ""))):
        raise SystemExit("base must be immutable SHA")
    if template.get("profile","fedor")!="fedor":raise SystemExit("only the bound LOOP profile is admitted")

    root = required_path(config, "source_repo")
    if not root.is_absolute() or not (root / ".git").is_dir():
        raise SystemExit("dedicated full source checkout required")
    workspace_root = required_path(config, "workspace_root").resolve()
    if root.resolve() == workspace_root or workspace_root in root.resolve().parents or root.resolve() in workspace_root.parents:
        raise SystemExit("trusted source and model workspace must be separate trees")
    script = trusted_regular_file(root / "tools" / "orchestrator" / "bad_dev_story.sh")
    prompt_file = trusted_regular_file(required_path(template, "prompt_file"))
    prompt_root = required_path(config, "prompt_root")
    if not prompt_root.is_absolute() or prompt_root.is_symlink() or not prompt_root.is_dir():
        raise SystemExit("invalid prompt_root")
    try:
        prompt_file.relative_to(prompt_root)
    except ValueError as error:
        raise SystemExit("prompt must be below prompt_root") from error
    expected_prompt = template.get("prompt_sha256")
    if not isinstance(expected_prompt, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_prompt):
        raise SystemExit("template needs prompt_sha256")
    if hashlib.sha256(prompt_file.read_bytes()).hexdigest() != expected_prompt:
        raise SystemExit("prompt hash differs from approved template")
    allowed_paths = admitted_paths(template)
    environment = child_environment(config, root)
    if template.get("profile_id")!=environment["PROFILE_FEDOR"] or template.get("profile_revision")!=int(environment["BRIDGE_PROFILE_REVISION"]):raise SystemExit("approved template Agent Profile binding changed")
    environment["BRIDGE_TEMPLATE_NAME"] = args.template
    environment["BRIDGE_TEMPLATE_FINGERPRINT"] = template_fingerprint(args.template,template)
    command = [
        "/bin/bash",
        str(script),
        "--source-dir",
        str(root),
        "--run-id",
        args.job,
        "--branch",
        "feat/loop-" + args.job,
        "--base-ref",
        template["base_sha"],
        "--prompt-file",
        str(prompt_file),
        "--profile",
        template.get("profile", "fedor"),
        "--attempt",
        "1",
        "--timeout",
        "1800",
        "--max-iterations",
        "30",
        "--keep-workspace",
        "--external-collect",
    ]
    for allowed_path in allowed_paths:
        command.extend(("--allow-path", allowed_path))
    contract_files = template.get("contract_files", [])
    if not isinstance(contract_files, list):
        raise SystemExit("invalid contract_files")
    for contract_file in contract_files:
        command.extend(("--contract-file", admitted_relative_path(contract_file, "contract file")))
    # No incoming shell fragments, paths, flags or secrets. All task choices come
    # from operator-reviewed templates stored outside the worker checkout.
    result = subprocess.run(
        command,
        cwd=root,
        env=environment,
        timeout=5500,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
