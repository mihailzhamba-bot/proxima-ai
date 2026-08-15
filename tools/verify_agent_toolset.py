from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = Path("docs/operations/agent-toolset.md")
EXPECTED_INTEGRATIONS = {
    "Sentry",
    "GitHub",
    "Chrome DevTools",
    "PostgreSQL",
    "Jira",
    "Confluence",
    "jq / rg",
}
ALLOWED_STATUSES = {"configured", "missing", "N/A"}
ENABLED_MCP_SERVERS = {"jira-atlassian", "node_repl"}
JIRA_READ_TOOLS = {
    "getAccessibleAtlassianResources",
    "getJiraIssue",
    "searchJiraIssuesUsingJql",
}
BROAD_GITHUB_SCOPES = {"gist", "read:org", "repo", "workflow"}


@dataclass(frozen=True)
class Integration:
    name: str
    status: str
    evidence: str
    owner_action: str


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_inventory(path: Path) -> dict[str, Integration]:
    integrations: dict[str, Integration] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in raw_line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in {"Интеграция", "---"} or set(cells[0]) == {"-"}:
            continue
        integration = Integration(*cells)
        integrations[integration.name] = integration
    return integrations


def broad_github_scopes(output: str) -> set[str]:
    lowered = output.lower()
    return {scope for scope in BROAD_GITHUB_SCOPES if re.search(rf"(?:^|[\s,'\"]){re.escape(scope)}(?:$|[\s,'\"])", lowered)}


def validate_inventory(inventory: dict[str, Integration], errors: list[str]) -> None:
    require(set(inventory) == EXPECTED_INTEGRATIONS, "integration matrix must contain the exact PA-30 toolset", errors)
    for integration in inventory.values():
        require(integration.status in ALLOWED_STATUSES, f"{integration.name}: invalid status {integration.status}", errors)
        require(bool(integration.evidence), f"{integration.name}: evidence or reason is required", errors)
        if integration.status == "missing":
            require("Owner:" in integration.owner_action and "Next:" in integration.owner_action, f"{integration.name}: missing requires Owner and Next", errors)
        if integration.status == "N/A":
            require("Reason:" in integration.owner_action, f"{integration.name}: N/A requires Reason", errors)


def verify_static(root: Path = ROOT) -> dict[str, Integration]:
    errors: list[str] = []
    config_path = root / ".codex" / "config.toml"
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))

    apps = config.get("apps", {})
    require(apps.get("_default", {}).get("enabled") is False, "project apps must default to disabled", errors)

    servers = config.get("mcp_servers", {})
    enabled = {name for name, value in servers.items() if value.get("enabled", True)}
    require(enabled == ENABLED_MCP_SERVERS, f"enabled MCP servers must be {sorted(ENABLED_MCP_SERVERS)}", errors)

    jira = servers.get("jira-atlassian", {})
    require(jira.get("required") is True, "Jira MCP must fail closed when unavailable", errors)
    require(set(jira.get("enabled_tools", [])) == JIRA_READ_TOOLS, "Jira MCP must expose only the read allowlist", errors)

    node_repl = servers.get("node_repl", {})
    require(node_repl.get("required") is True, "node_repl must fail closed when Chrome diagnostics are unavailable", errors)
    require(node_repl.get("enabled_tools") == ["js"], "node_repl must expose only js", errors)

    forbidden_config_keys = {"args", "bearer_token_env_var", "command", "env", "env_http_headers", "http_headers", "url"}
    for server_name, server in servers.items():
        leaked = forbidden_config_keys.intersection(server)
        require(not leaked, f"{server_name}: project config must not duplicate auth or transport fields: {sorted(leaked)}", errors)

    inventory = parse_inventory(root / INVENTORY_PATH)
    validate_inventory(inventory, errors)

    provision = (root / "infra" / "bootstrap" / "provision-postgres-diagnostics.sh").read_text(encoding="utf-8")
    wrapper = (root / "infra" / "bootstrap" / "proxima-psql-readonly").read_text(encoding="utf-8")
    for required in (
        "postgres_diagnostics_password",
        "proxima_diagnostics",
        "NOSUPERUSER",
        "NOCREATEDB",
        "NOCREATEROLE",
        "NOREPLICATION",
        "NOBYPASSRLS",
        "default_transaction_read_only",
        "GRANT SELECT ON ALL TABLES IN SCHEMA public",
        "ALTER DEFAULT PRIVILEGES FOR ROLE proxima",
    ):
        require(required in provision, f"PostgreSQL diagnostic provisioning missing: {required}", errors)
    require('--username "${DIAGNOSTIC_ROLE}"' in wrapper, "read-only wrapper must authenticate directly as the diagnostic role", errors)
    require("SET ROLE" not in wrapper and "RESET ROLE" not in wrapper, "read-only wrapper must not inherit a privileged session role", errors)
    require("ON_ERROR_STOP=1" in wrapper, "read-only wrapper must fail closed on SQL errors", errors)

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    require("agent-toolset:" in makefile, "Makefile must expose agent-toolset smoke", errors)

    if errors:
        raise ValueError("Agent toolset contract violations:\n" + "\n".join(sorted(errors)))
    return inventory


def run_checked(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    input_text: str | None = None,
    expect_failure: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    result = runner(
        list(command),
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if expect_failure:
        if result.returncode == 0:
            raise ValueError(f"expected command to fail: {' '.join(command)}")
    elif result.returncode != 0:
        diagnostic = (result.stderr or result.stdout or "no diagnostic").strip()
        raise ValueError(f"command failed: {' '.join(command)}: {diagnostic}")
    return result


def smoke_cli() -> None:
    for executable in ("gh", "jq", "psql", "rg", "ssh"):
        if shutil.which(executable) is None:
            raise ValueError(f"required CLI is missing: {executable}")
    run_checked(["jq", "--version"])
    run_checked(["rg", "--version"])
    run_checked(["psql", "--version"])


def smoke_github() -> None:
    auth = run_checked(["gh", "auth", "status"])
    broad = broad_github_scopes(auth.stdout + auth.stderr)
    if broad:
        raise ValueError(f"GitHub auth still has broad scopes: {sorted(broad)}")
    run_checked(["gh", "repo", "view", "mihailzhamba-bot/proxima-ai", "--json", "nameWithOwner,visibility"])
    run_checked(["gh", "run", "list", "--repo", "mihailzhamba-bot/proxima-ai", "--limit", "1"])
    run_checked(["git", "ls-remote", "origin", "HEAD"])
    run_checked(["git", "push", "--dry-run", "origin", "HEAD:refs/heads/pa-30-agent-toolset-smoke"])


def smoke_postgres(root: Path = ROOT) -> None:
    contract = json.loads((root / "infra" / "vps-contract.json").read_text(encoding="utf-8"))
    host = contract["decision"]["host_ipv4"]
    user = contract["access"]["admin_user"]
    remote = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        f"{user}@{host}",
        "sudo",
        "-n",
        "/usr/local/sbin/proxima-psql-readonly",
    ]
    positive = run_checked(
        remote,
        input_text=(
            "SELECT current_user = 'proxima_diagnostics', "
            "current_database() = 'proxima', "
            "current_setting('default_transaction_read_only') = 'on';\n"
        ),
    )
    if "t|t|t" not in positive.stdout:
        raise ValueError("PostgreSQL diagnostic session did not prove role, database and read-only default")
    run_checked(remote, input_text="UPDATE schema_migrations SET version = version WHERE false;\n", expect_failure=True)
    run_checked(remote, input_text="CREATE TABLE public.pa30_write_probe(id integer);\n", expect_failure=True)
    absent = run_checked(remote, input_text="SELECT to_regclass('public.pa30_write_probe') IS NULL;\n")
    if "t" not in absent.stdout:
        raise ValueError("PostgreSQL DDL probe left an object behind")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the PA-30 agent toolset without exposing credentials")
    parser.add_argument("--static-only", action="store_true", help="verify tracked contracts only")
    args = parser.parse_args()

    inventory = verify_static()
    if args.static_only:
        print("Agent toolset static verification passed")
        return

    smoke_cli()
    if inventory["GitHub"].status == "configured":
        smoke_github()
    if inventory["PostgreSQL"].status == "configured":
        smoke_postgres()
    print("Agent toolset verification passed")


if __name__ == "__main__":
    main()
