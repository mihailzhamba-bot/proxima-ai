from __future__ import annotations

import base64
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]

# D40: публичное дерево без ops-композита не содержит приватный контракт сервера
# и agent-конфигов - соответствующие гейты там skip-аются и в Makefile.
VPS_CONTRACT_PRESENT = (ROOT / "infra" / "vps-contract.json").exists()
CODEX_CONFIG_PRESENT = (ROOT / ".codex" / "config.toml").exists()
needs_vps_contract = pytest.mark.skipif(
    not VPS_CONTRACT_PRESENT, reason="infra/vps-contract.json живёт в ops-репо (D40)"
)
needs_codex_config = pytest.mark.skipif(
    not CODEX_CONFIG_PRESENT, reason=".codex/config.toml живёт в ops-репо (D40)"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_tool(name: str):
    return load_module(ROOT / "tools" / f"{name}.py", name)


def test_migration_checksum_rejects_changed_content() -> None:
    migrations = load_tool("verify_migrations")
    content = (ROOT / "db" / "migrations" / "001_bootstrap.sql").read_bytes()
    assert migrations.normalized_sha256(content) in content.decode()
    changed = content.replace(b"name text NOT NULL UNIQUE", b"name text UNIQUE")
    assert migrations.normalized_sha256(changed) not in changed.decode()


def test_source_path_rejects_parent_traversal() -> None:
    provenance = load_tool("verify_provenance")
    with pytest.raises(ValueError, match="unsafe source path"):
        provenance.safe_source_path("../dirty-secret")


def test_provenance_attestation_rejects_tampered_tree_object() -> None:
    provenance = load_tool("verify_provenance")
    path = ROOT / "provenance" / "torgstat-collector-610169a.attestation.json"
    attestation = json.loads(path.read_text(encoding="utf-8"))
    tampered = copy.deepcopy(attestation)
    tree_id = tampered["root_tree"]
    content = bytearray(base64.b64decode(tampered["objects"][tree_id]["content_base64"] ))
    content[0] ^= 1
    tampered["objects"][tree_id]["content_base64"] = base64.b64encode(content).decode()

    with pytest.raises(ValueError, match="attested Git object hash mismatch"):
        provenance.attested_paths(tampered)


def test_provenance_uses_locked_commit_bytes_not_later_worktree_state() -> None:
    provenance = load_tool("verify_provenance")

    provenance.verify()


def test_cross_language_contracts_accept_only_fail_closed_examples() -> None:
    contracts = load_tool("verify_contracts")
    contracts.verify()


def test_contract_verifier_reports_invalid_schema_without_traceback(tmp_path: Path) -> None:
    tool = tmp_path / "tools"
    tool.mkdir()
    shutil.copyfile(ROOT / "tools" / "verify_contracts.py", tool / "verify_contracts.py")
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    (contracts_dir / "broken.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://proxima.local/contracts/broken/v1",
                "type": "object",
                "properties": {"value": {"type": "string", "pattern": "("}},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(tool / "verify_contracts.py")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "contract verification failed: invalid schema" in result.stderr
    assert "is not a 'regex'" in result.stderr


def test_runtime_boundary_has_no_live_torgstat_path() -> None:
    boundary = load_tool("verify_runtime_boundary")
    boundary.verify()


def test_secret_scanner_patterns_are_live() -> None:
    scanner = load_tool("secret_scan")
    scanner.self_test()


def test_secret_scanner_detects_jwt_tokens() -> None:
    scanner = load_tool("secret_scan")
    sample = b"eyJ" + b"a" * 20 + b"." + b"b" * 20 + b"." + b"c" * 20

    assert scanner.inspect("worktree", "probe.txt", sample) == ["worktree:probe.txt:1: jwt-token"]


def test_secret_scanner_reads_staged_blob_when_worktree_is_safe(tmp_path: Path) -> None:
    scanner = load_tool("secret_scan")
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
    path = repository / "probe.txt"
    path.write_bytes(b"sk-proj-" + b"a" * 36)
    subprocess.run(["git", "add", "probe.txt"], cwd=repository, check=True)
    path.write_text("safe worktree content\n", encoding="utf-8")

    result = scanner.findings(repository)

    assert result == ["index:probe.txt:1: openai-key"]


@needs_vps_contract
def test_vps_contract_is_fail_closed() -> None:
    vps = load_tool("verify_vps_contract")
    vps.verify()


def test_business_signal_contract_is_fail_closed() -> None:
    signal = load_tool("verify_business_signal")
    signal.verify()


def test_wb_client_contract_is_fail_closed() -> None:
    wb_client = load_tool("verify_wb_client")
    wb_client.verify()


def test_wb_client_gate_rejects_forbidden_endpoint_in_registry() -> None:
    wb_client = load_tool("verify_wb_client")
    registry = ROOT / "services" / "collector" / "src" / "wb" / "registry.ts"
    original = registry.read_text(encoding="utf-8")
    try:
        registry.write_text(
            original.replace(
                "https://statistics-api.wildberries.ru/api/v1/supplier/orders",
                "https://statistics-api.wildberries.ru/api/v1/supplier/stocks",
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="forbidden endpoint|URL set differs"):
            wb_client.verify()
    finally:
        registry.write_text(original, encoding="utf-8")


def test_wb_client_gate_rejects_budget_drift() -> None:
    wb_client = load_tool("verify_wb_client")
    registry = ROOT / "services" / "collector" / "src" / "wb" / "registry.ts"
    original = registry.read_text(encoding="utf-8")
    try:
        assert "limitPerMinute: 1," in original
        registry.write_text(
            original.replace("limitPerMinute: 1,", "limitPerMinute: 5,", 1),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="budget mismatch"):
            wb_client.verify()
    finally:
        registry.write_text(original, encoding="utf-8")


def test_wb_client_gate_rejects_url_outside_registry() -> None:
    wb_client = load_tool("verify_wb_client")
    client = ROOT / "services" / "collector" / "src" / "wb" / "client.ts"
    original = client.read_text(encoding="utf-8")
    try:
        client.write_text(
            original.replace(
                "import { endpointLimit, WB_ENDPOINTS } from './registry.js';",
                "import { endpointLimit, WB_ENDPOINTS } from './registry.js';\nconst DRIFT = 'https://statistics-api.wildberries.ru/api/v1/supplier/incomes';\nvoid DRIFT;",
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="WB URL literal outside the registry"):
            wb_client.verify()
    finally:
        client.write_text(original, encoding="utf-8")


def test_wb_client_gate_rejects_fifth_endpoint_with_duplicated_url() -> None:
    """Regression: an extra registry entry reusing an allowed URL and a wild
    budget must fail the gate, not slip through as a "known" URL."""
    wb_client = load_tool("verify_wb_client")
    original = (ROOT / "services" / "collector" / "src" / "wb" / "registry.ts").read_text(
        encoding="utf-8"
    )
    injected = original.replace(
        "  'statistics.sales': {",
        "\n".join(
            [
                "  'statistics.orders_burst': {",
                "    id: 'statistics.orders_burst',",
                "    method: 'GET',",
                "    url: 'https://statistics-api.wildberries.ru/api/v1/supplier/orders',",
                "    token: 'statistics',",
                "    api: 'statistics',",
                "    fixtureDir: 'statistics/orders_burst',",
                "    limitPerMinute: 100,",
                "  },",
                "  'statistics.sales': {",
            ]
        ),
        1,
    )
    assert injected != original, "fixture injection anchor disappeared"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src" / "wb").mkdir(parents=True)
        (root / "src" / "wb" / "registry.ts").write_text(injected, encoding="utf-8")
        with pytest.raises(ValueError, match="endpoints outside the allowed four"):
            wb_client.verify(
                registry_path=root / "src" / "wb" / "registry.ts",
                collector_src=root / "src",
            )


def test_wb_client_gate_rejects_wb_host_fragment_in_cli_source() -> None:
    """Regression: `.wildberries` reached through string concatenation anywhere
    in collector src (incl. cli/) must fail, not just full URL literals."""
    wb_client = load_tool("verify_wb_client")
    drift = ROOT / "services" / "collector" / "src" / "cli" / "wb-collect.ts"
    original = drift.read_text(encoding="utf-8")
    try:
        drift.write_text(
            original.replace(
                "export function parseWbCollectArgs",
                "const HOST_SUFFIX = '.wildberries' + '.ru/api/v1/supplier/incomes';\nvoid HOST_SUFFIX;\n\nexport function parseWbCollectArgs",
                1,
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="WB host fragment outside the registry"):
            wb_client.verify()
    finally:
        drift.write_text(original, encoding="utf-8")


@needs_codex_config
def test_agent_toolset_contract_is_fail_closed() -> None:
    toolset = load_tool("verify_agent_toolset")
    toolset.verify_static()


def test_agent_toolset_requires_owner_and_next_action_for_missing(tmp_path: Path) -> None:
    toolset = load_tool("verify_agent_toolset")
    inventory = tmp_path / "inventory.md"
    inventory.write_text(
        "| Интеграция | Статус | Evidence / limitation | Owner / action |\n"
        "|---|---|---|---|\n"
        "| Sentry | missing | not configured | no owner |\n",
        encoding="utf-8",
    )

    parsed = toolset.parse_inventory(inventory)
    errors: list[str] = []
    toolset.validate_inventory(parsed, errors)

    assert parsed["Sentry"].status == "missing"
    assert any("Sentry: missing requires Owner and Next" in error for error in errors)


def test_agent_toolset_detects_broad_github_scopes() -> None:
    toolset = load_tool("verify_agent_toolset")

    assert toolset.broad_github_scopes("Token scopes: 'gist', 'read:org', 'repo', 'workflow'") == {
        "gist",
        "read:org",
        "repo",
        "workflow",
    }
    assert toolset.broad_github_scopes("fine-grained token") == set()


def monitor_samples(monitor, count: int, *, cpu: float, memory: float, disk: float, minute_offset: int = 0):
    return [
        monitor.MetricSnapshot(f"2026-08-12T00:{minute + minute_offset:02d}:00+00:00", cpu, memory, disk)
        for minute in range(count)
    ]


@needs_vps_contract
def test_host_monitor_requires_sustained_cpu_and_memory_pressure() -> None:
    monitor = load_module(ROOT / "infra" / "monitoring" / "host_monitor.py", "host_monitor")
    contract = json.loads((ROOT / "infra" / "vps-contract.json").read_text(encoding="utf-8"))
    thresholds = monitor.Thresholds.from_contract(contract)
    samples = monitor_samples(monitor, monitor.required_samples(contract), cpu=71.0, memory=19.0, disk=10.0)

    alerts = monitor.classify(samples, thresholds, contract["monitoring"]["sustained_seconds"], contract["monitoring"]["interval_seconds"])

    assert {(alert.metric, alert.severity) for alert in alerts} == {
        ("cpu_percent", "warning"),
        ("memory_available_percent", "warning"),
    }
    short_history = samples[:-1]
    assert monitor.classify(short_history, thresholds, contract["monitoring"]["sustained_seconds"], contract["monitoring"]["interval_seconds"]) == []


@needs_vps_contract
def test_host_monitor_thresholds_are_strict() -> None:
    monitor = load_module(ROOT / "infra" / "monitoring" / "host_monitor.py", "host_monitor_strict_thresholds")
    contract = json.loads((ROOT / "infra" / "vps-contract.json").read_text(encoding="utf-8"))
    thresholds = monitor.Thresholds.from_contract(contract)
    samples = monitor_samples(monitor, monitor.required_samples(contract), cpu=70.0, memory=20.0, disk=70.0)

    assert monitor.classify(samples, thresholds, contract["monitoring"]["sustained_seconds"], contract["monitoring"]["interval_seconds"]) == []
    disk_at_resize_threshold = monitor.MetricSnapshot("2026-08-12T00:00:00+00:00", 70.0, 20.0, 80.0)
    alerts = monitor.classify([disk_at_resize_threshold], thresholds, contract["monitoring"]["sustained_seconds"], contract["monitoring"]["interval_seconds"])
    assert {(alert.metric, alert.severity) for alert in alerts} == {("disk_used_percent", "warning")}


@needs_vps_contract
def test_host_monitor_does_not_join_pressure_across_timer_gap() -> None:
    monitor = load_module(ROOT / "infra" / "monitoring" / "host_monitor.py", "host_monitor_timer_gap")
    contract = json.loads((ROOT / "infra" / "vps-contract.json").read_text(encoding="utf-8"))
    thresholds = monitor.Thresholds.from_contract(contract)
    samples = monitor_samples(monitor, monitor.required_samples(contract), cpu=86.0, memory=9.0, disk=10.0)
    samples[8] = monitor.MetricSnapshot("2026-08-12T02:00:00+00:00", 86.0, 9.0, 10.0)

    alerts = monitor.classify(samples, thresholds, contract["monitoring"]["sustained_seconds"], contract["monitoring"]["interval_seconds"])

    assert alerts == []


@needs_vps_contract
def test_host_monitor_escalates_and_recommends_without_resizing() -> None:
    monitor = load_module(ROOT / "infra" / "monitoring" / "host_monitor.py", "host_monitor_escalation")
    contract = json.loads((ROOT / "infra" / "vps-contract.json").read_text(encoding="utf-8"))
    thresholds = monitor.Thresholds.from_contract(contract)
    urgent_samples = monitor_samples(monitor, monitor.required_samples(contract), cpu=86.0, memory=9.0, disk=81.0)

    alerts = monitor.classify(urgent_samples, thresholds, contract["monitoring"]["sustained_seconds"], contract["monitoring"]["interval_seconds"])
    by_metric = {alert.metric: alert for alert in alerts}

    assert by_metric["cpu_percent"].severity == "urgent"
    assert by_metric["memory_available_percent"].severity == "urgent"
    assert by_metric["disk_used_percent"].severity == "resize_recommendation"
    assert "manual" in by_metric["disk_used_percent"].action


def test_migration_verifier_rejects_destructive_statements() -> None:
    migrations = load_tool("verify_migrations")
    banned = [
        "BEGIN;\nDROP TABLE tenants;\nCOMMIT;\n",
        "BEGIN;\nTRUNCATE fact_order_counts;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts DROP COLUMN order_count;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts ALTER COLUMN order_count TYPE text;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts RENAME COLUMN order_count TO orders;\nCOMMIT;\n",
        "BEGIN;\nDROP INDEX IF EXISTS some_index;\nCOMMIT;\n",
        "BEGIN;\nCREATE OR REPLACE VIEW v AS SELECT 1;\nCOMMIT;\n",
        "BEGIN;\ncreate or replace view v as select 1;\nCOMMIT;\n",
        "BEGIN;\nalter table t alter column c type text;\nCOMMIT;\n",
        "BEGIN;\n/* don't */ DROP TABLE t;\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO log VALUES ('/*'); DROP TABLE t;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts DISABLE ROW LEVEL SECURITY;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts OWNER TO someone_else;\nCOMMIT;\n",
        "BEGIN;\nDO $$ BEGIN DROP TABLE t; END $$;\nCOMMIT;\n",
        "BEGIN;\nDO $$ BEGIN EXECUTE 'DROP TABLE tenants'; END $$;\nCOMMIT;\n",
        "BEGIN;\nexecute 'TRUNCATE ' || 'fact_order_counts';\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts SET UNLOGGED;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE fact_order_counts SET SCHEMA elsewhere;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE parents DETACH PARTITION kids;\nCOMMIT;\n",
        "BEGIN;\nALTER POLICY tenant_isolation ON fact_order_counts USING (true);\nCOMMIT;\n",
        "BEGIN;\nALTER VIEW public_order_counts_operational RENAME TO leaked;\nCOMMIT;\n",
        "BEGIN;\nALTER ROLE proxima_data_health_read BYPASSRLS;\nCOMMIT;\n",
        "BEGIN;\nREVOKE SELECT ON fact_order_counts FROM proxima_data_health_read;\nCOMMIT;\n",
        "BEGIN;\nCREATE RULE r AS ON SELECT TO t DO INSTEAD SELECT 1;\nCOMMIT;\n",
        "BEGIN;\nCOMMENT ON TABLE t IS 'overwritten';\nCOMMIT;\n",
        "BEGIN;\nCALL some_procedure();\nCOMMIT;\n",
        "BEGIN;\nLOCK TABLE t IN ACCESS EXCLUSIVE MODE;\nCOMMIT;\n",
        "BEGIN;\nCREATE FUNCTION f() RETURNS void LANGUAGE plpgsql AS $$ BEGIN NULL; END $$ SECURITY DEFINER;\nCOMMIT;\n",
        "BEGIN;\nCREATE EXTENSION dblink;\nCOMMIT;\n",
        "BEGIN;\nGRANT ALL ON DATABASE proxima TO PUBLIC;\nCOMMIT;\n",
        "BEGIN;\nGRANT proxima_migration_owner TO proxima_source_publisher;\nCOMMIT;\n",
        "BEGIN;\nCREATE ROLE oops LOGIN SUPERUSER BYPASSRLS;\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id) VALUES (1) ON CONFLICT (id) DO UPDATE SET id = 2;\nCOMMIT;\n",
        "BEGIN;\nSET ROLE proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nSET SESSION AUTHORIZATION proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nSET LOCAL ROLE proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nSET SESSION ROLE proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nSET LOCAL SESSION AUTHORIZATION proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nRESET ROLE;\nCOMMIT;\n",
        "BEGIN;\nRESET SESSION AUTHORIZATION;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN x int, ALTER COLUMN y TYPE text;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN x int, DISABLE ROW LEVEL SECURITY;\nCOMMIT;\n",
        "BEGIN;\nCREATE USER oops SUPERUSER;\nCOMMIT;\n",
        "BEGIN;\nCREATE GROUP oops;\nCOMMIT;\n",
        "BEGIN;\nCREATE LANGUAGE plpgsql3u;\nCOMMIT;\n",
        "BEGIN;\nCREATE ACCESS METHOD am TYPE INDEX HANDLER h;\nCOMMIT;\n",
        "BEGIN;\nCREATE AGGREGATE a (int) (SFUNC = f, STYPE = int);\nCOMMIT;\n",
        "BEGIN;\nCREATE CAST (int AS text) WITH FUNCTION f;\nCOMMIT;\n",
        "BEGIN;\nCREATE SERVER s FOREIGN DATA WRAPPER w;\nCOMMIT;\n",
        "BEGIN;\nCREATE FOREIGN TABLE ft (id int) SERVER s;\nCOMMIT;\n",
        "BEGIN;\nGRANT ALL PRIVILEGES ON t TO proxima_x;\nCOMMIT;\n",
        "BEGIN;\nGRANT DELETE ON t TO proxima_x;\nCOMMIT;\n",
        "BEGIN;\nGRANT TRIGGER ON t TO proxima_x;\nCOMMIT;\n",
        "BEGIN;\nGRANT REFERENCES ON t TO proxima_x;\nCOMMIT;\n",
        "BEGIN;\nCREATE SCHEMA extra AUTHORIZATION proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nCREATE SCHEMA extra CREATE TABLE t (id int) GRANT SELECT ON t TO PUBLIC;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN x int DEFAULT (1), NO FORCE ROW LEVEL SECURITY;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ATTACH PARTITION p FOR VALUES FROM (1) TO (2);\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t RESET (fillfactor);\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN x int, ALTER COLUMN y TYPE text;\nCOMMIT;\n",
        "BEGIN;\nSET LOCAL session_replication_role = replica;\nCOMMIT;\n",
        "BEGIN;\nSET LOCAL \"role\" = 'proxima_migration_owner';\nCOMMIT;\n",
        "BEGIN;\nSELECT pg_catalog.set_config('role', 'proxima_migration_owner', true);\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id) VALUES (set_config('role', 'oops', true));\nCOMMIT;\n",
        "BEGIN;\nCREATE VIEW leaky AS SELECT * FROM fact_order_counts;\nCOMMIT;\n",
        "BEGIN;\nCREATE VIEW leaky WITH (security_invoker = false) AS SELECT * FROM fact_order_counts;\nCOMMIT;\n",
        "BEGIN;\nCREATE TABLE leaked AS SELECT * FROM fact_order_counts;\nCOMMIT;\n",
        "BEGIN;\nCREATE MATERIALIZED VIEW leaked_mv AS SELECT * FROM fact_order_counts;\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO log VALUES (pg_catalog.\"set_config\"('role', 'oops', true));\nCOMMIT;\n",
        "BEGIN;\nGRANT INSERT, UPDATE ON schema_migrations TO proxima_data_health_read;\nCOMMIT;\n",
        "BEGIN;\nGRANT UPDATE ON fact_order_counts TO proxima_data_health_read;\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY open_sesame ON t FOR SELECT USING (true);\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY p2 ON t FOR SELECT USING (tenant_id = 1);\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t SELECT * FROM other;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN x int, ENABLE ROW LEVEL SECURITY;\nCOMMIT;\n",
        "CREATE TABLE t (id int);\nBEGIN;\nCOMMIT;\n",
        "BEGIN;\nCOMMIT;\nBEGIN;\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY current_setting ON t FOR SELECT USING (true);\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY p ON t FOR SELECT USING ('mentions current_setting in a string');\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY p ON t FOR ALL TO proxima_source_publisher WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id) VALUES ((SELECT secret FROM other LIMIT 1));\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO seq VALUES (setval('s', 100));\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t VALUES (lo_unlink(12345));\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id) VALUES (1) ON CONFLICT (id) DO UPDATE SET id = 2;\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY p ON t FOR ALL TO proxima_source_publisher USING (tenant_id = current_setting('evil.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));\nCOMMIT;\n",
        "BEGIN;\nGRANT UPDATE ON public.schema_migrations TO proxima_source_publisher;\nCOMMIT;\n",
        "BEGIN;\nCREATE TABLE leaked (id) AS SELECT secret FROM other;\nCOMMIT;\n",
        "BEGIN;\nCREATE INDEX CONCURRENTLY i ON t (id);\nCOMMIT;\n",
        "BEGIN;\nCREATE TABLE leaked (id) AS VALUES (1);\nCOMMIT;\n",
        "BEGIN;\nCREATE TABLE leaked (id) AS TABLE source_table;\nCOMMIT;\n",
        "BEGIN;\nCREATE TABLE leaked (id) AS (SELECT secret FROM other);\nCOMMIT;\n",
        "BEGIN;\nCREATE TABLE leaked (id) AS WITH c AS (SELECT 1) SELECT * FROM c;\nCOMMIT;\n",
    ]
    for sql in banned:
        with pytest.raises(ValueError, match="migration"):
            migrations.assert_additive_only(sql, "999_fixture.sql")

    allowed = [
        "BEGIN;\nCREATE TABLE t (id int);\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN note text;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD CONSTRAINT c CHECK (id > 0);\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ENABLE ROW LEVEL SECURITY;\nCOMMIT;\n",
        "BEGIN;\nCREATE INDEX t_note_idx ON t (note);\nCOMMIT;\n",
        "BEGIN;\nCREATE ROLE proxima_x NOLOGIN;\nGRANT SELECT ON t TO proxima_x;\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id) VALUES (1); -- drop mentioned only in a comment\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id, note) VALUES (2, 'literal mentioning drop and truncate');\nCOMMIT;\n",
        "BEGIN;\nINSERT INTO t (id) VALUES (3) ON CONFLICT (id) DO NOTHING;\nCOMMIT;\n",
        "BEGIN;\nCREATE VIEW safe_v WITH (security_invoker = true) AS SELECT id FROM t;\nCOMMIT;\n",
        "BEGIN;\nALTER TABLE t ADD COLUMN a int, ADD COLUMN b text;\nCOMMIT;\n",
        "BEGIN;\nGRANT SELECT, INSERT ON fact_order_counts TO proxima_source_publisher;\nCOMMIT;\n",
        "BEGIN;\nGRANT SELECT, INSERT, UPDATE ON schema_migrations TO proxima_migration_owner;\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY tenant_isolation ON t FOR SELECT TO proxima_data_health_read USING (tenant_id = current_setting('proxima.tenant_id', true));\nCOMMIT;\n",
        "BEGIN;\nCREATE POLICY tenant_isolation ON t FOR ALL TO proxima_source_publisher USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true));\nCOMMIT;\n",
    ]
    for sql in allowed:
        migrations.assert_additive_only(sql, "999_fixture.sql")


def test_migration_verifier_additive_check_covers_all_existing_migrations() -> None:
    migrations = load_tool("verify_migrations")
    for path in sorted((ROOT / "db" / "migrations").glob("*.sql")):
        migrations.assert_additive_only(path.read_text(encoding="utf-8"), path.name)


def test_wb_async_report_gate_is_fail_closed() -> None:
    gate = load_tool("verify_wb_async_report")
    gate.verify()


def test_wb_async_report_gate_prints_the_run_ledger_line() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_wb_async_report.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "wb_async_report: run ledger\n"


def test_wb_async_report_gate_rejects_tenant_autocreate_and_lost_tests(tmp_path: Path) -> None:
    gate = load_tool("verify_wb_async_report")
    original = (ROOT / "tools" / "wb_async_report.py").read_text(encoding="utf-8")
    regressed = tmp_path / "wb_async_report.py"
    regressed.write_text(
        original + '\n\ndef _legacy(connection, tenant_id):\n    connection.execute("INSERT INTO tenants (tenant_id) VALUES (%s) ON CONFLICT DO NOTHING", (tenant_id,))\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="never insert into tenants"):
        gate.verify(tool_path=regressed)

    without_guc = tmp_path / "without_guc.py"
    without_guc.write_text(original.replace("SELECT set_config(%s, %s, false)", "SELECT 1"), encoding="utf-8")
    with pytest.raises(ValueError, match="set_config"):
        gate.verify(tool_path=without_guc)

    missing_tests = tmp_path / "test_wb_async_report.py"
    missing_tests.write_text("def test_something_else() -> None:\n    pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing test test_second_run_in_a_day_does_not_create_a_report"):
        gate.verify(unit_tests=missing_tests)

    unwired = tmp_path / "Makefile"
    unwired.write_text("verify: install test\n", encoding="utf-8")
    with pytest.raises(ValueError, match="wb-async-report"):
        gate.verify(makefile=unwired)


def test_nm_daily_gate_is_fail_closed() -> None:
    gate = load_tool("verify_nm_daily")
    days, nm_ids, rows, passed = gate.verify(node_test=False)
    assert (days, nm_ids, rows, passed) == (13, 97, 13 * 97, 0)


def test_nm_daily_gate_rejects_webapp_grant_and_missing_cascade(tmp_path: Path) -> None:
    gate = load_tool("verify_nm_daily")
    original = (ROOT / "db" / "migrations" / "018_nm_daily.sql").read_text(encoding="utf-8")

    leaked = tmp_path / "webapp.sql"
    leaked.write_text(original.replace("GRANT SELECT ON fact_nm_daily TO proxima_job_norm;", "GRANT SELECT ON fact_nm_daily TO proxima_job_norm;\nGRANT SELECT ON fact_nm_daily TO proxima_webapp_readonly;"), encoding="utf-8")
    with pytest.raises(AssertionError, match="webapp gets no grant"):
        gate.check_migration(leaked)

    restricted = tmp_path / "restrict.sql"
    restricted.write_text(original.replace("REFERENCES collector_runs(run_id) ON DELETE CASCADE", "REFERENCES collector_runs(run_id) ON DELETE RESTRICT", 1), encoding="utf-8")
    with pytest.raises(AssertionError, match="cascade from collector_runs"):
        gate.check_migration(restricted)


def test_nm_daily_gate_rejects_a_second_run_inputs_writer(tmp_path: Path) -> None:
    gate = load_tool("verify_nm_daily")
    writer = tmp_path / "nm-daily.ts"
    writer.write_text(
        (ROOT / "services" / "collector" / "src" / "facts" / "nm-daily.ts").read_text(encoding="utf-8")
        + "\nconst DRIFT = 'INSERT INTO collector_run_inputs (tenant_id, run_id, input_run_id) VALUES (1, 2, 3)';\nvoid DRIFT;\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="collector_run_inputs is written once"):
        gate.check_writer(writer=writer)


def test_makefile_wires_codegen_diff_immediately_after_codegen() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    verify_line = next(line for line in makefile.splitlines() if line.startswith("verify:"))

    assert "codegen codegen-diff" in verify_line
    assert "codegen-diff: codegen" in makefile
    assert "git diff --exit-code --stat -- services/collector/src/contracts services/webapp/src/lib/contracts" in makefile
    assert "git ls-files --others --exclude-standard -- services/collector/src/contracts services/webapp/src/lib/contracts" in makefile
