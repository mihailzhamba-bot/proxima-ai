"""Gate: live WB network is opted in by the collector job container only (AD-4).

`make verify` must show `live-network: PASS`.

AD-4 makes the WB transport fail-closed: `networkTransport()` in
services/collector/src/wb/transport.ts throws WB_NETWORK_FORBIDDEN unless
WB_ALLOW_LIVE_NETWORK=1, and tests inject FixtureTransport instead of setting
the flag. Until 08.09.2026 nothing in the deploy contour set it, so the first
real `collect` on the server (runbook §3 live tail, every morning run) failed
on its first HTTP call. The production jobs (`collect`, `backfill`,
`funnel-v3`, `funnel-csv-promote`) all run in the `collector` service of
infra/compose.yaml through `docker compose --profile jobs run collector`
(tools/morning_run.sh, tools/funnel_v3_run.sh, tools/funnel_csv_run.sh,
runbook §3), so the flag lives in that service's `environment:` and nowhere
else. This script pins exactly that:

- infra/compose.yaml: `collector` sets WB_ALLOW_LIVE_NETWORK "1" with an AD-4
  note; `control-plane`, `control-plane-admin` and `postgres` do not;
- infra/jobs.env and infra/local.env.example never assign the key (a comment
  may mention it): jobs.env is loaded by all three job services and
  tools/wb_async_report.py:read_env_file() rejects keys outside SAFE_ENV_KEYS,
  so the flag there would break apply-migrations and FUNNEL_CSV_DOWNLOAD; the
  allowlist itself must not learn the key either;
- infra/systemd/*: no unit or drop-in mentions the flag - a unit edit must not
  be able to disable or widen it silently; units only run the compose runners;
- services/collector/tests and services/webapp/src/tests: no test sets the
  flag to 1 (AD-4), except the one seam test that sets and restores it inside
  `finally` to prove the missing-token check fires before any transport call;
  the test runners (Makefile, package.json scripts) do not set it either;
- transport.ts keeps the fail-closed check ahead of the real fetch transport.

Standard library only: compose.yaml is read with the same block regexes as
tools/tests/test_compose_collector_mounts.py (PyYAML is not a dependency).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "infra" / "compose.yaml"
JOBS_ENV = ROOT / "infra" / "jobs.env"
LOCAL_ENV_EXAMPLE = ROOT / "infra" / "local.env.example"
SYSTEMD = ROOT / "infra" / "systemd"
TRANSPORT = ROOT / "services" / "collector" / "src" / "wb" / "transport.ts"
WB_ASYNC_REPORT = ROOT / "tools" / "wb_async_report.py"
TEST_DIRS = (ROOT / "services" / "collector" / "tests", ROOT / "services" / "webapp" / "src" / "tests")
TEST_RUNNERS = (ROOT / "Makefile", ROOT / "package.json", ROOT / "services" / "collector" / "package.json", ROOT / "services" / "webapp" / "package.json")

GATE = "live-network"
FLAG = "WB_ALLOW_LIVE_NETWORK"
LIVE_SERVICE = "collector"
# The only test allowed to set the flag: it proves WB_TOKEN_NOT_CONFIGURED fires before the
# transport even when the flag is on, and restores the previous value in `finally`.
SEAM_TESTS = frozenset({"services/collector/tests/wb-client.test.ts"})
TEST_SUFFIXES = frozenset({".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs"})

SET_TO_ONE = re.compile(r"""WB_ALLOW_LIVE_NETWORK['"\]]*\s*(?:=|:|,)\s*['"]?1(?![0-9])""")
JS_COMMENT = re.compile(r"^\s*(?://|/\*|\*)")
ENV_ASSIGNMENT = re.compile(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)")


class LiveNetworkGateError(AssertionError):
    """The live-network opt-in drifted away from the collector job container (AD-4)."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LiveNetworkGateError(message)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def read(path: Path) -> str:
    require(path.is_file(), f"missing artifact: {rel(path)}")
    return path.read_text(encoding="utf-8")


def compose_services(compose_text: str) -> dict[str, str]:
    """Top-level `services:` entries as name -> body (same block regex as the compose tests)."""
    match = re.search(r"(?ms)^services:\n(?P<body>.*?)(?=^[a-zA-Z]|\Z)", compose_text)
    require(match is not None, "compose: `services:` block missing")
    services = {
        entry.group("name"): entry.group("body")
        for entry in re.finditer(r"(?ms)^  (?P<name>[a-zA-Z][a-zA-Z0-9_-]*):\n(?P<body>.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n|\Z)", match.group("body"))
    }
    require(bool(services), "compose: no services found")
    return services


def service_environment(body: str) -> dict[str, str]:
    """`environment:` of one service (map or `- KEY=value` list form), comments dropped, quotes stripped."""
    match = re.search(r"(?ms)^    environment:\n(?P<body>.*?)(?=^    [a-zA-Z]|\Z)", body)
    if match is None:
        return {}
    values: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entry = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", line) or re.fullmatch(r"-\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        require(entry is not None, f"compose: unsupported environment entry: {line}")
        key, value = entry.groups()
        values[key] = value.strip().strip("'\"")
    return values


def without_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def check_compose(compose: Path = COMPOSE) -> dict[str, str | None]:
    """`collector` opts in with "1" (string or int) and an AD-4 note; every other service stays out."""
    services = compose_services(read(compose))
    require(LIVE_SERVICE in services, f"compose: service `{LIVE_SERVICE}` missing")
    flags: dict[str, str | None] = {}
    for name, body in services.items():
        value = service_environment(body).get(FLAG)
        flags[name] = value
        if name == LIVE_SERVICE:
            require(value == "1", f"compose: service `{LIVE_SERVICE}` must set {FLAG}: \"1\" in environment - live WB jobs opt in there (AD-4), got {value!r}")
            require(without_comments(body).count(FLAG) == 1, f"compose: {FLAG} must appear exactly once in `{LIVE_SERVICE}` (no list/env_file duplicate)")
            require("AD-4" in body, f"compose: the {FLAG} line in `{LIVE_SERVICE}` must carry its AD-4 note")
        else:
            require(FLAG not in without_comments(body), f"compose: service `{name}` must not set {FLAG} - only `{LIVE_SERVICE}` talks to WB (AD-4)")
    return flags


def env_assignments(text: str) -> list[tuple[int, str, str]]:
    assignments: list[tuple[int, str, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entry = ENV_ASSIGNMENT.fullmatch(line)
        if entry is not None:
            assignments.append((line_number, entry.group(1), entry.group(2).strip().strip("'\"")))
    return assignments


def check_env_files(jobs_env: Path = JOBS_ENV, example: Path = LOCAL_ENV_EXAMPLE, wb_async_report: Path = WB_ASYNC_REPORT) -> None:
    """Env files never assign the flag (comments may mention it); SAFE_ENV_KEYS must not admit it."""
    for path in (jobs_env, example):
        for line_number, key, _value in env_assignments(read(path)):
            require(key != FLAG, f"{rel(path)}:{line_number}: {FLAG} must not be set in env files - it is compose-only (AD-4); jobs.env is read through SAFE_ENV_KEYS by apply-migrations and wb_async_report")
    source = read(wb_async_report)
    require("SAFE_ENV_KEYS = frozenset(" in source, f"{rel(wb_async_report)}: SAFE_ENV_KEYS allowlist missing")
    start = source.index("SAFE_ENV_KEYS = frozenset(")
    block = source[start : source.index("\n)", start)]
    require(FLAG not in block, f"{rel(wb_async_report)}: SAFE_ENV_KEYS must not admit {FLAG} - that is the road back into jobs.env (AD-4)")


def check_systemd(systemd: Path = SYSTEMD) -> int:
    """No unit or drop-in mentions the flag: the value comes from compose, units cannot silently change it."""
    require(systemd.is_dir(), f"missing directory: {rel(systemd)}")
    files = sorted(path for path in systemd.rglob("*") if path.is_file())
    require(bool(files), f"{rel(systemd)} holds no units")
    for path in files:
        for line_number, raw_line in enumerate(read(path).splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            require(FLAG not in line, f"{rel(path)}:{line_number}: {FLAG} must not come from a systemd unit - compose sets it for the `{LIVE_SERVICE}` service (AD-4)")
    return len(files)


def check_tests(test_dirs: tuple[Path, ...] = TEST_DIRS, seam_tests: frozenset[str] = SEAM_TESTS, root: Path = ROOT) -> int:
    """Tests are network-free (AD-4): no test file sets the flag to 1, except the restoring seam test."""
    scanned = 0
    for directory in test_dirs:
        require(directory.is_dir(), f"missing test directory: {rel(directory)}")
        for path in sorted(entry for entry in directory.rglob("*") if entry.is_file() and entry.suffix in TEST_SUFFIXES):
            scanned += 1
            text = read(path)
            hits = [number for number, line in enumerate(text.splitlines(), start=1) if not JS_COMMENT.match(line) and SET_TO_ONE.search(line)]
            if not hits:
                continue
            relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
            require(relative in seam_tests, f"{relative}:{hits[0]}: a test must not set {FLAG}=1 - tests are network-free (AD-4), WB calls go through FixtureTransport")
            require("finally {" in text and f"delete process.env.{FLAG}" in text, f"{relative}: the seam test must restore {FLAG} in `finally` (delete process.env.{FLAG})")
    require(scanned > 0, "no test files scanned")
    return scanned


def check_test_runners(runners: tuple[Path, ...] = TEST_RUNNERS) -> None:
    """Makefile and package.json scripts never inject the flag into a test or verify run."""
    for path in runners:
        for line_number, raw_line in enumerate(read(path).splitlines(), start=1):
            if raw_line.lstrip().startswith("#"):
                continue
            require(FLAG not in raw_line, f"{rel(path)}:{line_number}: {FLAG} must not be set by a test/verify runner (AD-4)")


def check_transport(transport: Path = TRANSPORT) -> None:
    """The seam itself: networkTransport stays fail-closed and checks the flag before the real fetch."""
    source = read(transport)
    require("export function networkTransport(" in source, f"{rel(transport)}: networkTransport() missing (AD-4 seam)")
    body = source[source.index("export function networkTransport(") :]
    require(f"process.env['{FLAG}'] !== '1'" in body or f"process.env.{FLAG} !== '1'" in body, f"{rel(transport)}: networkTransport must stay fail-closed on {FLAG} !== '1' (AD-4)")
    require("WB_NETWORK_FORBIDDEN" in body, f"{rel(transport)}: the refusal must be WB_NETWORK_FORBIDDEN")
    require("fetchTransport" in body and body.index("WB_NETWORK_FORBIDDEN") < body.index("fetchTransport"), f"{rel(transport)}: the flag check must run before the real fetch transport is reached")


def verify() -> dict[str, str | int]:
    flags = check_compose()
    check_env_files()
    units = check_systemd()
    test_files = check_tests()
    check_test_runners()
    check_transport()
    return {"collector": str(flags[LIVE_SERVICE]), "other_services": len(flags) - 1, "units": units, "test_files": test_files}


def main() -> None:
    summary = verify()
    print(f"{GATE}: PASS ({LIVE_SERVICE} {FLAG}={summary['collector']} in infra/compose.yaml; {summary['other_services']} other services, {summary['units']} units, {summary['test_files']} test files clean)")


if __name__ == "__main__":
    try:
        main()
    except (LiveNetworkGateError, KeyError, ValueError, OSError) as exc:
        print(f"{GATE}: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
