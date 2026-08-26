from __future__ import annotations

import os
import uuid

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
        for role in roles:
            row = connection.execute(
                "SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (role,)
            ).fetchone()
            assert row["rolcanlogin"] is False

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
        "wb_analytics_report_tasks",
        "raw_wb_analytics_responses",
        "stg_wb_nm_report_rows",
    }
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        secured = {
            row["tablename"]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity"
            ).fetchall()
        }
        assert secured == expected_tables
        policy_count = connection.execute(
            "SELECT count(*) AS n FROM pg_policies WHERE schemaname = 'public'"
        ).fetchone()["n"]
        assert policy_count == 23
        non_invoker_views = [
            row["relname"]
            for row in connection.execute(
                "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' AND c.relkind = 'v'"
                " AND NOT ('security_invoker=true' = ANY (c.reloptions))"
            ).fetchall()
        ]
        assert non_invoker_views == [], f"views without security_invoker=true: {non_invoker_views}"


@pytest.mark.skipif(not os.environ.get("PROXIMA_TEST_POSTGRES_DSN"), reason="dedicated PostgreSQL DSN not configured")
def test_row_level_security_enforces_tenant_scope_for_runtime_roles() -> None:
    """Live RLS proof: seed two tenants with facts/releases as the owner,
    then query under runtime roles. Cross-tenant reads must return nothing;
    the security_invoker view must surface only the setting's tenant."""
    dsn = os.environ["PROXIMA_TEST_POSTGRES_DSN"]
    tenants = [f"rls_a_{uuid.uuid4().hex[:8]}", f"rls_b_{uuid.uuid4().hex[:8]}"]
    attempt_ids = {tenants[0]: uuid.uuid4(), tenants[1]: uuid.uuid4()}
    release_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        for tenant in tenants:
            connection.execute("INSERT INTO tenants (tenant_id) VALUES (%s)", (tenant,))
            connection.execute(
                "INSERT INTO fact_attempt_runs (attempt_id, tenant_id, source_family, source_ref, status, finished_at)"
                " VALUES (%s, %s, 'wb_analytics_task', %s, 'SUCCEEDED', CURRENT_TIMESTAMP)",
                (attempt_ids[tenant], tenant, f"task-{tenant}"),
            )
            connection.execute(
                "INSERT INTO fact_order_counts (attempt_id, tenant_id, nm_id, calendar_day, order_count)"
                " VALUES (%s, %s, 101, '2026-08-24', 5)",
                (attempt_ids[tenant], tenant),
            )
            connection.execute(
                "INSERT INTO fact_lineage_records (attempt_id, tenant_id, evidence_sha256, evidence_locator,"
                " parser_version, acquired_via, acquired_at)"
                " VALUES (%s, %s, %s, 'locator', 'v1', 'wb_analytics_task', CURRENT_TIMESTAMP)",
                (attempt_ids[tenant], tenant, "0" * 64),
            )
            connection.execute(
                "INSERT INTO quality_check_results (attempt_id, tenant_id, check_name, status, detail)"
                " VALUES (%s, %s, 'grain_uniqueness', 'PASS', '{}')",
                (attempt_ids[tenant], tenant),
            )
        connection.execute(
            "INSERT INTO release_attempts (release_id, tenant_id, domain, status, finished_at)"
            " VALUES (%s, %s, 'operational', 'SUCCEEDED', CURRENT_TIMESTAMP)",
            (release_id, tenants[0]),
        )
        connection.execute(
            "INSERT INTO release_promoted_facts (release_id, fact_attempt_id, tenant_id)"
            " VALUES (%s, %s, %s)",
            (release_id, attempt_ids[tenants[0]], tenants[0]),
        )
        connection.execute(
            "INSERT INTO domain_release_pointers (tenant_id, domain, current_release_id)"
            " VALUES (%s, 'operational', %s)",
            (tenants[0], release_id),
        )

        # data health role, scoped to tenant A: sees only A's facts and the public view rows of A
        connection.execute("SET ROLE proxima_data_health_read")
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (tenants[0],))
        visible = connection.execute("SELECT count(*) AS n FROM fact_order_counts").fetchone()["n"]
        assert visible == 1
        public_rows = connection.execute(
            "SELECT count(*) AS n FROM public_order_counts_operational"
        ).fetchone()["n"]
        assert public_rows == 1
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (tenants[1],))
        assert connection.execute("SELECT count(*) AS n FROM fact_order_counts").fetchone()["n"] == 1
        assert (
            connection.execute("SELECT count(*) AS n FROM public_order_counts_operational").fetchone()["n"]
            == 0
        ), "tenant B must not see tenant A's released facts through the view"
        connection.execute("RESET ROLE")
        connection.execute("SELECT set_config('proxima.tenant_id', '', false)")

        # cross-tenant FK hard-stop: promoting tenant B's attempt under tenant A's release must fail
        bad_release = uuid.uuid4()
        connection.execute(
            "INSERT INTO release_attempts (release_id, tenant_id, domain, status, finished_at)"
            " VALUES (%s, %s, 'operational', 'SUCCEEDED', CURRENT_TIMESTAMP)",
            (bad_release, tenants[0]),
        )
        try:
            connection.execute(
                "INSERT INTO release_promoted_facts (release_id, fact_attempt_id, tenant_id)"
                " VALUES (%s, %s, %s)",
                (bad_release, attempt_ids[tenants[1]], tenants[0]),
            )
            raised = False
        except psycopg.errors.ForeignKeyViolation:
            raised = True
        assert raised, "tenant mismatch across release/promotion must be rejected by the composite FK"

        # the mirrored path: a tenant-B row (fresh attempt) referencing tenant-A's release must fail
        fresh_attempt_b = uuid.uuid4()
        connection.execute(
            "INSERT INTO fact_attempt_runs (attempt_id, tenant_id, source_family, source_ref, status, finished_at)"
            " VALUES (%s, %s, 'wb_analytics_task', %s, 'SUCCEEDED', CURRENT_TIMESTAMP)",
            (fresh_attempt_b, tenants[1], f"task2-{tenants[1]}"),
        )
        try:
            connection.execute(
                "INSERT INTO release_promoted_facts (release_id, fact_attempt_id, tenant_id)"
                " VALUES (%s, %s, %s)",
                (release_id, fresh_attempt_b, tenants[1]),
            )
            raised_row = False
        except psycopg.errors.ForeignKeyViolation:
            raised_row = True
        assert raised_row, "tenant-B promotion row must not reference tenant-A's release"

        # fact row of tenant B referencing tenant A's attempt must fail (composite FK)
        try:
            connection.execute(
                "INSERT INTO fact_order_counts (attempt_id, tenant_id, nm_id, calendar_day, order_count)"
                " VALUES (%s, %s, 102, '2026-08-24', 1)",
                (attempt_ids[tenants[0]], tenants[1]),
            )
            raised_fact = False
        except psycopg.errors.ForeignKeyViolation:
            raised_fact = True
        assert raised_fact, "cross-tenant fact-to-attempt edge must be rejected"
