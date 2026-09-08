"""Offline tests for tools/rehearsal_run.sh and infra/compose.rehearsal.yaml (D35).

Everything runs with --dry-run: no docker, no sudo, nothing created on disk. The
tests pin the shape of the printed commands (project name, override file, no
production bindings) and the refusal rules (tail without --live, a root inside
the checkout or inside the production tree). The compose rendering test is the
only one that needs docker and skips wherever `docker compose` cannot run.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "rehearsal_run.sh"
OVERRIDE = ROOT / "infra" / "compose.rehearsal.yaml"
API_FACTS = ROOT / "docs" / "state" / "API-FACTS.md"

PROJECT = "proxima-rehearsal"
TEST_ROOT = "/tmp/rehearsal-test-root"
TOKEN_SRC = "/etc/proxima-ai/secrets/wb_statistics_token"
SALES_SHA = "d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96"
ORDERS_SHA = "0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40"

SUBCOMMANDS = {
    "init": ["init", "--statistics-token-src", TOKEN_SRC],
    "up": ["up"],
    "backfill": ["backfill"],
    "tail": ["tail", "--live"],
    "steps": ["steps"],
    "check": ["check"],
    "down": ["down"],
    "all": ["all", "--live"],
}


def run(*args: str, root: str = TEST_ROOT, dry_run: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["bash", str(SCRIPT)]
    if dry_run:
        command.append("--dry-run")
    command.extend(args)
    if root:
        command.extend(["--root", root])
    return subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)


def printed_commands(output: str) -> list[str]:
    return [line[2:] for line in output.splitlines() if line.startswith("+ ")]


@pytest.mark.parametrize("name", sorted(SUBCOMMANDS))
def test_dry_run_prints_isolated_compose_commands(name: str) -> None:
    """Every docker compose call carries the project name, the override file and the
    rehearsal env file; nothing points at the production bridge port, checkout or
    container."""

    result = run(*SUBCOMMANDS[name])
    assert result.returncode == 0, result.stderr
    commands = printed_commands(result.stdout)
    assert commands, result.stdout
    compose_calls = [line for line in commands if "docker compose" in line]
    if name == "check":
        # check talks to the container directly (runbook `psqlp` form), never to production.
        assert f"docker exec -i {PROJECT}-postgres-1" in result.stdout
    elif name != "init":
        assert compose_calls, result.stdout
    for line in compose_calls:
        assert f"-p {PROJECT}" in line
        assert "-f infra/compose.yaml -f infra/compose.rehearsal.yaml" in line
        assert f"--env-file {TEST_ROOT}/.env" in line
    assert "172.17.0.1" not in result.stdout
    assert "/srv/proxima-ai/repo" not in result.stdout
    assert "proxima-ai-postgres-1" not in result.stdout
    assert "/etc/proxima-ai/secrets" not in result.stdout.replace(TOKEN_SRC, "")


def test_dry_run_creates_nothing(tmp_path: Path) -> None:
    root = tmp_path / "rehearsal"
    result = run(*SUBCOMMANDS["init"], root=str(root))
    assert result.returncode == 0, result.stderr
    assert not root.exists()
    result = run(*SUBCOMMANDS["all"], root=str(root))
    assert result.returncode == 0, result.stderr
    assert not root.exists()


def test_tail_refuses_without_live() -> None:
    result = run("tail")
    assert result.returncode != 0
    assert "--live" in result.stderr
    assert "2 live WB read calls" in result.stderr
    assert "npm run collect" not in result.stdout


def test_tail_with_live_enables_network_for_that_run_only() -> None:
    result = run("tail", "--live")
    assert result.returncode == 0, result.stderr
    collect = [line for line in printed_commands(result.stdout) if "npm run collect" in line]
    assert len(collect) == 1
    line = collect[0]
    assert line.startswith("sudo -n env PROXIMA_REHEARSAL_LIVE=1 docker compose ") or line.startswith(
        "env PROXIMA_REHEARSAL_LIVE=1 docker compose "
    )
    assert "--tenant amirova-test --date-from 2026-08-27" in line
    assert "--statistics-token-file /run/secrets/amirova-test_wb_statistics_token" in line
    assert "2 read calls" in result.stdout


def test_all_without_live_skips_the_tail() -> None:
    result = run("all")
    assert result.returncode == 0, result.stderr
    assert "npm run collect" not in result.stdout
    assert "PROXIMA_REHEARSAL_LIVE=1" not in result.stdout
    assert "tail skipped" in result.stdout


def test_all_live_prints_the_whole_chain_in_runbook_order() -> None:
    result = run(*SUBCOMMANDS["all"])
    assert result.returncode == 0, result.stderr
    text = result.stdout

    def first(fragment: str) -> int:
        position = text.find(fragment)
        assert position >= 0, f"missing: {fragment}\n{text}"
        return position

    order = [
        first("--profile jobs build"),
        first("up -d --wait"),
        first("make apply-migrations ENV_FILE=infra/jobs.env"),
        first("FROM schema_migrations"),
        first("provision-runtime-roles.sh"),
        first("cas_import.ts"),
        first("INSERT INTO tenants"),
        first("npm run backfill"),
        first("npm run collect"),
        first("proxima_control_plane.norm run --tenant amirova-test"),
        first("proxima_control_plane.brief run --tenant amirova-test"),
        first("fact_cabinet_daily_current"),
    ]
    assert order == sorted(order), order
    assert text.count("provision-runtime-roles.sh") == 2
    assert text.count("cas_import.ts") == 2


def test_backfill_uses_the_31_08_pair_and_control_plane_admin_runs_migrations() -> None:
    result = run("backfill")
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json" in text
    assert "supplier-orders/20260831T155341Z__dateFrom-2023-01-01_flag-0.json" in text
    assert f"--source artifact:{SALES_SHA},{ORDERS_SHA}" in text
    assert "--retrieved-at 2026-08-31T15:53:41Z --source official_wb_statistics" in text
    assert f"chown -R 1010:1010 {TEST_ROOT}/raw" in text

    result = run("up")
    assert result.returncode == 0, result.stderr
    assert "run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env" in result.stdout
    assert f"--psql {TEST_ROOT}/bin/psql-owner --secrets-dir {TEST_ROOT}/secrets" in result.stdout
    assert "--host postgres --port 5432 --database proxima" in result.stdout


def test_backfill_honours_artifacts_dir() -> None:
    result = run("backfill", "--artifacts-dir", "/data/wb")
    assert result.returncode == 0, result.stderr
    assert "/data/wb/supplier-sales/" in result.stdout
    assert "/data/wb/supplier-orders/" in result.stdout


def test_init_prepares_private_dirs_secrets_and_env_without_values() -> None:
    result = run(*SUBCOMMANDS["init"])
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert f"install -d -m 0700 -o 1010 -g 1010 {TEST_ROOT}/secrets {TEST_ROOT}/raw" in text
    for name in (
        "postgres_user",
        "postgres_password",
        "proxima_collector_uri",
        "proxima_norm_uri",
        "proxima_janitor_uri",
        "proxima_sandbox_uri",
    ):
        assert f"write-secret {TEST_ROOT}/secrets/{name} owner 1010:1010" in text
    # The webapp image runs as uid 1001 (services/webapp/Dockerfile), so its two files get that
    # owner - a 1010:1010 file is unreadable for the container (rehearsal finding, 08.09).
    for name in ("proxima_webapp_password", "proxima_webapp_uri"):
        assert f"write-secret {TEST_ROOT}/secrets/{name} owner 1001:1001" in text
    assert "owner 1001:1001" not in "\n".join(
        line for line in text.splitlines() if "proxima_webapp_" not in line
    )
    assert f"install -m 0600 -o 1010 -g 1010 {TOKEN_SRC} {TEST_ROOT}/secrets/amirova-test_wb_statistics_token" in text
    assert f"install -m 0600 -o 1010 -g 1010 /dev/null {TEST_ROOT}/secrets/amirova-test_wb_analytics_token" in text
    assert f"docker exec -i {PROJECT}-postgres-1" in text
    for line in (
        f"COMPOSE_PROJECT_NAME={PROJECT}",
        "COMPOSE_FILE=infra/compose.yaml:infra/compose.rehearsal.yaml",
        f"PROXIMA_SECRETS_DIR={TEST_ROOT}/secrets",
        f"PROXIMA_RAW_DIR={TEST_ROOT}/raw",
        "PROXIMA_REHEARSAL_PG_PORT=5434",
        "WEBAPP_DATA_MODE=postgres",
        "WEBAPP_TENANT_ID=amirova-test",
    ):
        assert line in text
    assert "openssl" not in text


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["up"], "--root"),
        (["init"], "--statistics-token-src"),
        (["frobnicate"], "unknown subcommand"),
        (["up", "--bogus"], "unknown option"),
    ],
)
def test_argument_errors(args: list[str], message: str) -> None:
    root = "" if args == ["up"] else TEST_ROOT
    result = run(*args, root=root)
    assert result.returncode != 0
    assert message in result.stderr


@pytest.mark.parametrize(
    ("root", "message"),
    [
        (str(ROOT / "rehearsal"), "outside the git checkout"),
        (str(ROOT), "outside the git checkout"),
        ("/srv/proxima-ai/rehearsal", "production tree"),
        ("/etc/proxima-ai/secrets", "production tree"),
        ("relative/path", "absolute"),
    ],
)
def test_root_guards(root: str, message: str) -> None:
    result = run("up", root=root)
    assert result.returncode != 0
    assert message in result.stderr


def test_check_embeds_the_api_facts_reference_sums() -> None:
    """The expected W10/W35 values in the script are the API-FACTS table, not a copy
    that can drift silently."""

    table = API_FACTS.read_text(encoding="utf-8")
    facts: dict[str, tuple[str, str]] = {}
    for week in ("W10", "W35"):
        # Revenue is written «700 860.50» (kopecks, since 08.09) or «263 089» (whole rubles).
        match = re.search(rf"^\| {week} \| [^|]+\| (\d+) \| ([\d ]+?(?:\.\d{{2}})?) \|", table, re.MULTILINE)
        assert match is not None, f"{week} row missing in API-FACTS.md"
        revenue = match.group(2).replace(" ", "")
        if "." not in revenue:
            revenue += ".00"
        facts[week] = (match.group(1), revenue)

    script = SCRIPT.read_text(encoding="utf-8")
    for week, (orders, revenue) in facts.items():
        assert f'{week}_EXPECTED="{week}|{orders}|{revenue}"' in script

    result = run("check")
    assert result.returncode == 0, result.stderr
    # The SQL is shell-quoted in the dry-run echo, so match the pieces, not the literal.
    for day in ("2026-03-02", "2026-03-08", "2026-08-24", "2026-08-30"):
        assert day in result.stdout
    assert result.stdout.count("sum(orders_count), sum(revenue_rub) FROM fact_cabinet_daily_current") == 2
    for table_name in ("collector_runs", "data_status_current", "norm_daily_current", "brief_current"):
        assert table_name in result.stdout


def test_override_file_replaces_ports_and_isolates_names() -> None:
    text = OVERRIDE.read_text(encoding="utf-8")
    assert re.search(r"^name: proxima-rehearsal$", text, re.MULTILINE)
    assert "ports: !override" in text
    port_lines = [line for line in text.splitlines() if re.match(r'^\s+- "127\.0\.0\.1:', line)]
    assert port_lines == ['      - "127.0.0.1:${PROXIMA_REHEARSAL_PG_PORT:-5434}:5432"']
    assert "172.17.0.1" not in text
    assert "name: proxima-rehearsal-private" in text
    assert "WB_ALLOW_LIVE_NETWORK: ${PROXIMA_REHEARSAL_LIVE:-0}" in text
    assert 'restart: "no"' in text
    # The override never redefines secrets or volumes: those stay project-prefixed defaults.
    assert "\nsecrets:" not in text
    assert "\nvolumes:" not in text


def docker_compose_usable() -> bool:
    if shutil.which("docker") is None:
        return False
    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, check=False)
    return probe.returncode == 0


@pytest.mark.skipif(not docker_compose_usable(), reason="docker compose is not usable here")
def test_rendered_config_has_one_loopback_port_and_no_bridge_binding(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets"
    raw = tmp_path / "raw"
    secrets.mkdir()
    raw.mkdir()
    for name in (
        "postgres_user",
        "postgres_password",
        "proxima_collector_uri",
        "proxima_norm_uri",
        "amirova-test_wb_statistics_token",
        "amirova-test_wb_analytics_token",
    ):
        (secrets / name).write_text("placeholder\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"PROXIMA_SECRETS_DIR={secrets}\nPROXIMA_RAW_DIR={raw}\nPROXIMA_REHEARSAL_PG_PORT=5434\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "docker", "compose", "-p", PROJECT,
            "-f", "infra/compose.yaml", "-f", "infra/compose.rehearsal.yaml",
            "--env-file", str(env_file), "--profile", "jobs", "config",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    rendered = result.stdout
    assert rendered.startswith(f"name: {PROJECT}\n")
    assert rendered.count('published: "5434"') == 1
    assert "172.17.0.1" not in rendered
    assert re.search(r'published: "5432"', rendered) is None
    assert "name: proxima-rehearsal-private" in rendered
    assert f"name: {PROJECT}_postgres-data" in rendered
    assert 'WB_ALLOW_LIVE_NETWORK: "0"' in rendered
