"""Offline contract for collector secrets and raw artifact mounts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra" / "compose.yaml"
RUNNERS = tuple(ROOT / "tools" / name for name in ("morning_run.sh", "funnel_v3_run.sh", "funnel_csv_run.sh"))


def service(name: str) -> str:
    compose = COMPOSE.read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n|^networks:)", compose)
    assert match is not None
    return match.group("body")


def secret_names(body: str) -> set[str]:
    match = re.search(r"(?ms)^    secrets:\n(?P<body>.*?)(?=^    [a-zA-Z])", body)
    assert match is not None
    return set(re.findall(r"^      - ([a-zA-Z0-9_-]+)$", match.group("body"), re.MULTILINE))


def assert_provenance_environment(body: str) -> None:
    assert body.count("PROXIMA_GIT_SHA: ${PROXIMA_GIT_SHA:-}") == 1
    assert body.count("PROXIMA_IMAGE_ID: ${PROXIMA_IMAGE_ID:-}") == 1


def test_ledger_services_declare_host_provenance_with_empty_defaults() -> None:
    assert_provenance_environment(service("collector"))
    assert_provenance_environment(service("control-plane"))
    assert_provenance_environment(service("control-plane-admin"))


def test_collector_receives_only_runtime_secrets_and_raw_mount() -> None:
    collector = service("collector")
    assert secret_names(collector) == {
        "proxima_collector_uri",
        "pilot-tenant_wb_statistics_token",
        "pilot-tenant_wb_analytics_token",
    }
    assert "postgres_" not in collector
    assert "_owner_uri" not in collector
    assert "${PROXIMA_RAW_DIR:?set PROXIMA_RAW_DIR}:/srv/proxima-ai/raw" in collector
    assert "PROXIMA_RAW_DIR: /srv/proxima-ai/raw" in collector


def test_admin_gets_only_the_extra_files_needed_by_csv_download() -> None:
    admin = service("control-plane-admin")
    assert secret_names(admin) == {"postgres_user", "postgres_password", "pilot-tenant_wb_analytics_token"}
    assert "pilot-tenant_wb_statistics_token" not in admin
    assert "${PROXIMA_RAW_DIR:?set PROXIMA_RAW_DIR}:/srv/proxima-ai/raw" in admin


def test_runners_use_container_paths_and_host_checks_use_secrets_dir() -> None:
    contents = "\n".join(path.read_text(encoding="utf-8") for path in RUNNERS)
    assert "/run/secrets/${tenant}_wb_statistics_token" in contents
    assert "/run/secrets/${tenant}_wb_analytics_token" in contents
    assert "${secrets_dir}/${tenant}_wb_statistics_token" in contents
    assert "${secrets_dir}/${tenant}_wb_analytics_token" in contents
    assert '--volume "$analytics_token:' not in contents
    assert '--volume "$spool_dir:' not in contents


def test_example_and_runbook_match_the_compose_contract() -> None:
    example = (ROOT / "infra" / "local.env.example").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "operations" / "release-m01.md").read_text(encoding="utf-8")
    assert "PROXIMA_SECRETS_DIR=/etc/proxima-ai/secrets" in example
    assert "PROXIMA_RAW_DIR=/srv/proxima-ai/raw" in example
    assert "WB_STATISTICS_TOKEN_FILE=/run/secrets/pilot-tenant_wb_statistics_token" in example
    assert "WB_ANALYTICS_TOKEN_FILE=/run/secrets/pilot-tenant_wb_analytics_token" in example
    assert "-v /srv/proxima-ai/raw:/srv/proxima-ai/raw" not in runbook
    assert "-v /etc/proxima-ai/secrets/pilot-tenant_wb_statistics_token" not in runbook
    assert "Пока ноль" not in runbook
