from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_runtime_roles_exist_with_expected_grant_matrix() -> None:
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        roles = {
            row["rolname"]
            for row in connection.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN ("
                "'proxima_migration_owner', 'proxima_source_publisher',"
                "'proxima_release_publisher', 'proxima_data_health_read')"
            ).fetchall()
        }
        assert roles == {
            "proxima_migration_owner",
            "proxima_source_publisher",
            "proxima_release_publisher",
            "proxima_data_health_read",
        }
        for role in roles - {"proxima_migration_owner", "proxima_data_health_read"}:
            login = connection.execute(
                "SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (role,)
            ).fetchone()["rolcanlogin"]
            assert login is False

        def can(role: str, privilege: str, table: str) -> bool:
            row = connection.execute(
                "SELECT has_table_privilege(%s, %s, %s) AS ok", (role, table, privilege)
            ).fetchone()
            return bool(row["ok"])

        # source publisher: writes facts family, reads evidence, never pointers/schema ledger
        assert can("proxima_source_publisher", "INSERT", "fact_order_counts")
        assert can("proxima_source_publisher", "INSERT", "stg_quarantine_rows")
        assert can("proxima_source_publisher", "SELECT", "stg_wb_nm_report_rows")
        assert not can("proxima_source_publisher", "UPDATE", "domain_release_pointers")
        assert not can("proxima_source_publisher", "SELECT", "schema_migrations")

        # release publisher: owns pointer/release surfaces, never fact inserts
        assert can("proxima_release_publisher", "UPDATE", "domain_release_pointers")
        assert can("proxima_release_publisher", "INSERT", "release_attempts")
        assert not can("proxima_release_publisher", "INSERT", "fact_order_counts")
        assert not can("proxima_release_publisher", "SELECT", "schema_migrations")

        # data health: read-only everywhere it needs, writes nowhere
        assert can("proxima_data_health_read", "SELECT", "fact_order_counts")
        assert can("proxima_data_health_read", "SELECT", "public_order_counts_operational")
        assert not can("proxima_data_health_read", "INSERT", "fact_order_counts")
        assert not can("proxima_data_health_read", "UPDATE", "domain_release_pointers")
        assert not can("proxima_data_health_read", "SELECT", "schema_migrations")

        # migration owner: the only role with schema_migrations access
        assert can("proxima_migration_owner", "UPDATE", "schema_migrations")
        assert not can("proxima_migration_owner", "INSERT", "fact_order_counts")


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_phase3_tables_have_row_level_security_with_tenant_policies() -> None:
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    expected_tables = {
        "fact_attempt_runs",
        "stg_quarantine_rows",
        "fact_order_counts",
        "fact_lineage_records",
        "quality_check_results",
        "release_attempts",
        "release_promoted_facts",
        "domain_release_pointers",
    }
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        secured = {
            row["tablename"]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity"
            ).fetchall()
        }
        assert expected_tables <= secured
        policy_count = connection.execute(
            "SELECT count(*) AS n FROM pg_policies WHERE schemaname = 'public'"
        ).fetchone()["n"]
        assert policy_count == 16
