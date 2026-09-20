#!/usr/bin/env bash
# Rebuild proxima_test from proxima and grant the OpenHands sandbox access to
# the copy only (AD-12). Authentication is supplied by the normal libpq
# environment (PGPASSFILE/PGPASSWORD); this script never reads or prints it.
#
# Production usage:
#   PROXIMA_TENANT_ID=<tenant> make test-db-refresh
# Optional connection overrides use the standard PGHOST, PGPORT and PGUSER
# variables. Binary paths and database names are overridable for the local
# disposable PostgreSQL harness.
set -euo pipefail

PSQL_PATH="${PROXIMA_PSQL_PATH:-$(command -v psql 2>/dev/null || true)}"
PG_DUMP_PATH="${PROXIMA_PG_DUMP_PATH:-$(command -v pg_dump 2>/dev/null || true)}"
MAIN_DATABASE="${PROXIMA_MAIN_DATABASE:-proxima}"
TEST_DATABASE="${PROXIMA_TEST_DATABASE:-proxima_test}"
SANDBOX_ROLE="proxima_sandbox"
TENANT_ID="${PROXIMA_TENANT_ID:-}"

fail() {
  echo "test-db-refresh: $*" >&2
  exit 1
}

[[ -n "${PSQL_PATH}" && -x "${PSQL_PATH}" ]] || fail "psql is required (or set PROXIMA_PSQL_PATH)"
[[ -n "${PG_DUMP_PATH}" && -x "${PG_DUMP_PATH}" ]] || fail "pg_dump is required (or set PROXIMA_PG_DUMP_PATH)"
[[ "${MAIN_DATABASE}" =~ ^[a-z_][a-z0-9_]*$ ]] || fail "main database name must be a plain identifier"
[[ "${TEST_DATABASE}" =~ ^[a-z_][a-z0-9_]*$ ]] || fail "test database name must be a plain identifier"
[[ "${MAIN_DATABASE}" != "${TEST_DATABASE}" ]] || fail "test database must differ from the main database"
[[ "${TENANT_ID}" =~ ^[a-z0-9][a-z0-9_-]{2,63}$ ]] || fail "PROXIMA_TENANT_ID is required and malformed"

PSQL_ARGS=(--no-psqlrc --quiet --set ON_ERROR_STOP=1)

echo "test-db-refresh: terminating sessions on ${TEST_DATABASE}"
"${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${MAIN_DATABASE}" --command \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TEST_DATABASE}' AND pid <> pg_backend_pid();" >/dev/null

echo "test-db-refresh: recreating ${TEST_DATABASE}"
"${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${MAIN_DATABASE}" --command \
  "DROP DATABASE ${TEST_DATABASE} WITH (FORCE);"
"${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${MAIN_DATABASE}" --command \
  "CREATE DATABASE ${TEST_DATABASE};"

echo "test-db-refresh: copying ${MAIN_DATABASE} to ${TEST_DATABASE}"
"${PG_DUMP_PATH}" --no-owner --no-privileges --dbname "${MAIN_DATABASE}" | \
  "${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${TEST_DATABASE}" >/dev/null

echo "test-db-refresh: granting sandbox access to the copy"
"${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${TEST_DATABASE}" <<SQL
REVOKE CONNECT ON DATABASE ${TEST_DATABASE} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${TEST_DATABASE} TO ${SANDBOX_ROLE};
GRANT ALL ON SCHEMA public TO ${SANDBOX_ROLE};
GRANT ALL ON ALL TABLES IN SCHEMA public TO ${SANDBOX_ROLE};
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO ${SANDBOX_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${SANDBOX_ROLE};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${SANDBOX_ROLE};
ALTER ROLE ${SANDBOX_ROLE} IN DATABASE ${TEST_DATABASE} SET proxima.tenant_id = '${TENANT_ID}';
SQL

echo "test-db-refresh: PASS (${TEST_DATABASE} refreshed; sandbox granted only on copy)"
