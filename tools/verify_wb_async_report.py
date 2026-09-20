"""Contract gate for Story 3.2: `tools/wb_async_report.py` as a ledger run.

Prints `wb_async_report: run ledger` when the tool and its tests still carry
the contract of AD-3 / AD-5 / AD-11 / AD-13. Standard library only; the
behaviour itself is proven by `tools/tests/test_wb_async_report.py` (offline,
`make test`) and `tools/tests/test_wb_async_report_postgres.py` (real
PostgreSQL, `pg-roundtrip` / CI) - this gate makes sure neither the contract
nor the tests that prove it quietly disappear.

Fail-closed checks:
- no tenant auto-creation: `INSERT INTO tenants` appears nowhere in the tool;
  the tenant-existence guard is present;
- the session GUC `proxima.tenant_id` is set through `set_config(…, false)`;
- the ledger: kind `funnel_csv_download`, `INSERT INTO collector_runs … RUNNING`,
  the close statement changes only `status` and `finished_at` and flips
  exactly one RUNNING row; SUCCEEDED and FAILED are the only closed statuses;
- `collector_run_id` is written to `wb_analytics_report_tasks` (INSERT + resume UPDATE);
- `--period` accepts `latest-closed-week` and an explicit `from..to`;
- the daily-report guard exists (`reports_created_on`, `_reports_created_today`)
  and the tool lists `nm-report/downloads` before the first create;
- the unit tests and the PostgreSQL tests named by the story exist;
- `make verify` runs this gate (Makefile wiring).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "wb_async_report.py"
UNIT_TESTS = ROOT / "tools" / "tests" / "test_wb_async_report.py"
POSTGRES_TESTS = ROOT / "tools" / "tests" / "test_wb_async_report_postgres.py"
MAKEFILE = ROOT / "Makefile"

GATE_LINE = "wb_async_report: run ledger"

REQUIRED_FUNCTIONS = (
    "parse_period",
    "parse_created_at",
    "reports_created_on",
    "log_run_event",
    "log_run_step",
)
REQUIRED_METHODS = {
    "PostgresReportRepository": ("bind_tenant", "_require_tenant", "open_run", "close_run", "reserve_task"),
    "AsyncReportCollector": ("collect", "_collect", "_reports_created_today"),
}
REQUIRED_MARKERS = (
    ('own_prefix = f"proxima-{tenant_id}-"', "the daily guard must count only this tenant's Proxima reports"),
    ('RUN_KIND = "funnel_csv_download"', "the ledger kind must be funnel_csv_download (AD-5)"),
    ("TENANT_GUC = \"proxima.tenant_id\"", "the session GUC must be proxima.tenant_id (AD-13)"),
    ("SELECT set_config(%s, %s, false)", "the GUC must be set with set_config(…, false) on the session (AD-3)"),
    ("INSERT INTO collector_runs (run_id, tenant_id, kind, status, git_sha, image_id)", "the run row must be inserted into collector_runs"),
    ("VALUES (%s, %s, %s, 'RUNNING', %s, %s)", "the run must open RUNNING"),
    ("UPDATE collector_runs SET status = %s, finished_at = CURRENT_TIMESTAMP", "closing a run must change only status and finished_at (AD-11)"),
    ("WHERE run_id = %s AND status = 'RUNNING'", "closing a run must flip exactly the RUNNING row"),
    ("if cursor.rowcount != 1:", "a zero-row close must be an error, never a silent success"),
    ('RUN_CLOSED_STATUSES = frozenset({"SUCCEEDED", "FAILED"})', "SUCCEEDED and FAILED are the only closed statuses"),
    ("aggregation_level, request_body, lifecycle_status, collector_run_id", "reserve_task must write collector_run_id on INSERT"),
    ("SET collector_run_id = %s, updated_at = CURRENT_TIMESTAMP", "a resuming run must take over collector_run_id"),
    ("does not exist: the collector never creates tenants", "a missing tenant must be a clear error (AD-5)"),
    ('PERIOD_LATEST_CLOSED_WEEK = "latest-closed-week"', "--period must keep latest-closed-week"),
    (r'PERIOD_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})")', "--period must accept an explicit from..to range"),
    ("period_from, period_to = parse_period(args.period, now)", "main must resolve --period through parse_period"),
    ("connect_repository(env, tenant_id=args.tenant_id)", "main must bind the tenant GUC when connecting"),
    ("self.client.get(API_ROOT, headers=self._headers())", "the daily guard must list nm-report/downloads before the first create"),
    ("created_today = self._reports_created_today(task)", "the first create must be gated by the daily guard"),
    ('self.repository.close_run(run_id, "SUCCEEDED")', "the run must close SUCCEEDED"),
    ('self.repository.close_run(run_id, "FAILED")', "the run must close FAILED on error"),
)
FORBIDDEN_MARKERS = (
    ("INSERT INTO tenants", "tenant auto-creation is removed (Story 3.2, AD-5): the tool must never insert into tenants"),
    ('choices=("latest-closed-week",)', "--period must not be restricted to latest-closed-week"),
)
REQUIRED_UNIT_TESTS = (
    "test_missing_tenant_fails_closed_before_any_run_row_or_network",
    "test_run_is_opened_running_and_closed_succeeded",
    "test_failed_run_is_closed_failed_and_the_original_error_surfaces",
    "test_second_run_in_a_day_does_not_create_a_report",
    "test_unreadable_downloads_list_fails_closed_without_creating",
    "test_reports_created_on_reads_utc_timestamps_into_the_moscow_day",
    "test_parse_period_accepts_explicit_closed_range_and_keeps_latest_closed_week",
)
REQUIRED_POSTGRES_TESTS = (
    "test_real_postgres_preserves_raw_bytes_and_task_idempotency",
    "test_real_postgres_run_ledger_for_funnel_csv_download",
    "test_real_postgres_collect_closes_the_run_and_guards_daily_creation",
)
REQUIRED_POSTGRES_MARKERS = (
    "INSERT INTO tenants (tenant_id) VALUES (%s)",
    "FROM collector_runs",
    "funnel_csv_download",
    "current_setting('proxima.tenant_id', true)",
)
MAKEFILE_TARGET = "wb-async-report"
MAKEFILE_COMMAND = "python tools/verify_wb_async_report.py"
NETWORK_RE = re.compile(r"seller-analytics-api\.wildberries\.ru")


def _defined_functions(tree: ast.Module) -> tuple[set[str], dict[str, set[str]]]:
    functions: set[str] = set()
    methods: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            methods[node.name] = {
                item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return functions, methods


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


def verify_tool(tool_path: Path = TOOL) -> list[str]:
    errors: list[str] = []
    if not tool_path.is_file():
        return [f"missing tool: {tool_path}"]
    source = tool_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(tool_path))
    except SyntaxError as error:
        return [f"{tool_path.name}: syntax error: {error}"]
    functions, methods = _defined_functions(tree)
    for name in REQUIRED_FUNCTIONS:
        if name not in functions:
            errors.append(f"{tool_path.name}: missing function {name}()")
    for class_name, names in REQUIRED_METHODS.items():
        present = methods.get(class_name)
        if present is None:
            errors.append(f"{tool_path.name}: missing class {class_name}")
            continue
        for name in names:
            if name not in present:
                errors.append(f"{tool_path.name}: {class_name} lost method {name}()")
    for marker, reason in REQUIRED_MARKERS:
        if marker not in source:
            errors.append(f"{tool_path.name}: {reason} (expected {marker!r})")
    for marker, reason in FORBIDDEN_MARKERS:
        if marker in source:
            line = source[: source.index(marker)].count("\n") + 1
            errors.append(f"{tool_path.name}:{line}: {reason}")
    # the GUC must be the first statement after connect: bind_tenant is called
    # inside connect_repository, before the repository is handed out
    connect = source.find("def connect_repository(")
    parse_args = source.find("def parse_args(")
    if connect == -1 or parse_args == -1 or "repository.bind_tenant(tenant_id)" not in source[connect:parse_args]:
        errors.append(f"{tool_path.name}: connect_repository must bind the tenant GUC before returning the repository")
    return errors


def verify_tests(unit_tests: Path = UNIT_TESTS, postgres_tests: Path = POSTGRES_TESTS) -> list[str]:
    errors: list[str] = []
    for path, required in ((unit_tests, REQUIRED_UNIT_TESTS), (postgres_tests, REQUIRED_POSTGRES_TESTS)):
        if not path.is_file():
            errors.append(f"missing tests: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
            continue
        names = _test_names(path)
        for name in required:
            if name not in names:
                errors.append(f"{path.name}: missing test {name}")
        content = path.read_text(encoding="utf-8")
        if NETWORK_RE.search(content):
            errors.append(f"{path.name}: tests must not reach the live WB API (AD-4)")
    if postgres_tests.is_file():
        content = postgres_tests.read_text(encoding="utf-8")
        for marker in REQUIRED_POSTGRES_MARKERS:
            if marker not in content:
                errors.append(f"{postgres_tests.name}: lost the real-PostgreSQL check {marker!r}")
    return errors


def verify_makefile(makefile: Path = MAKEFILE) -> list[str]:
    if not makefile.is_file():
        return [f"missing Makefile: {makefile}"]
    content = makefile.read_text(encoding="utf-8")
    errors: list[str] = []
    verify_line = next((line for line in content.splitlines() if line.startswith("verify:")), None)
    if verify_line is None:
        errors.append("Makefile: no verify target")
    elif MAKEFILE_TARGET not in verify_line.split():
        errors.append(f"Makefile: verify must include the {MAKEFILE_TARGET} target")
    if not re.search(rf"^{MAKEFILE_TARGET}:\n\t.*{re.escape(MAKEFILE_COMMAND)}", content, re.MULTILINE):
        errors.append(f"Makefile: target {MAKEFILE_TARGET} must run {MAKEFILE_COMMAND}")
    return errors


def verify(
    tool_path: Path = TOOL,
    unit_tests: Path = UNIT_TESTS,
    postgres_tests: Path = POSTGRES_TESTS,
    makefile: Path = MAKEFILE,
) -> None:
    errors = verify_tool(tool_path) + verify_tests(unit_tests, postgres_tests) + verify_makefile(makefile)
    if errors:
        raise ValueError("wb_async_report run-ledger contract violations:\n" + "\n".join(sorted(set(errors))))


if __name__ == "__main__":
    verify()
    print(GATE_LINE)
