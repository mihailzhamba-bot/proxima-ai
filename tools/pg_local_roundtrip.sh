#!/usr/bin/env bash
# Disposable local PostgreSQL migration + runtime-roles roundtrip
# (Story 1.2, AD-11/AD-12). No Docker, no VPS: initdb a throwaway PostgreSQL 16
# cluster in the OS temp dir, apply every verified migration through the
# canonical apply path, prove idempotent re-apply, run the real-PostgreSQL
# pytest subset, assert ledger completeness, provision the production LOGIN
# roles twice (idempotence proof) and run the collector *.db.test.ts subset
# under those roles, then destroy the cluster. Exits 0 with SKIP when no initdb.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PROXIMA_PG_ROUNDTRIP_PORT:-55432}"

PGBIN=""
# Explicit PG16 locations first: a PATH initdb of another major version must
# not cause a skip when a real PG16 candidate exists later in the list.
for candidate in /opt/homebrew/opt/postgresql@16/bin /usr/lib/postgresql/16/bin /usr/local/opt/postgresql@16/bin "$(dirname "$(command -v initdb 2>/dev/null || true)")"; do
  if [[ -x "${candidate}/initdb" ]] && "${candidate}/initdb" --version 2>/dev/null | grep -qE 'PostgreSQL[)] 16\.'; then PGBIN="${candidate}"; break; fi
done
if [[ -z "${PGBIN}" ]]; then
  echo "pg-roundtrip: SKIP (no local initdb found; disposable PostgreSQL 16 unavailable)"
  exit 0
fi
if ! "${PGBIN}/initdb" --version | grep -qE 'PostgreSQL[)] 16\.'; then
  echo "pg-roundtrip: SKIP (local PostgreSQL is not major version 16)"
  exit 0
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/proxima-pg-roundtrip.XXXXXX")"

# Ephemeral port: start from the default and probe until one is free.
PORT="${PROXIMA_PG_ROUNDTRIP_PORT:-55432}"
for _ in $(seq 1 20); do
  if ! "${PGBIN}/pg_isready" -h 127.0.0.1 -p "${PORT}" -t 1 >/dev/null 2>&1; then
    break
  fi
  PORT=$((PORT + 1))
done
cleanup() {
  "${PGBIN}/pg_ctl" -D "${WORK}/pgdata" -m immediate -w stop >/dev/null 2>&1 || true
  rm -rf "${WORK}"
}
trap cleanup EXIT

echo "pg-roundtrip: initdb disposable cluster (${PGBIN})"
"${PGBIN}/initdb" -D "${WORK}/pgdata" -U proxima_roundtrip --auth=trust --encoding=UTF8 >/dev/null
if ! "${PGBIN}/pg_ctl" -D "${WORK}/pgdata" -o "-p ${PORT} -k ${WORK} -c listen_addresses=127.0.0.1" -l "${WORK}/postgres.log" -w start >/dev/null; then
  echo "pg-roundtrip: server start failed; postgres log:" >&2
  cat "${WORK}/postgres.log" >&2 || true
  exit 1
fi
"${PGBIN}/createdb" -h 127.0.0.1 -p "${PORT}" -U proxima_roundtrip proxima

printf 'proxima_roundtrip\n' > "${WORK}/postgres_user"
printf 'disposable-roundtrip-only\n' > "${WORK}/postgres_password"
chmod 0600 "${WORK}/postgres_user" "${WORK}/postgres_password"
cat > "${WORK}/roundtrip.env" <<EOF
POSTGRES_USER_FILE=${WORK}/postgres_user
POSTGRES_PASSWORD_FILE=${WORK}/postgres_password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=${PORT}
POSTGRES_DB=proxima
EOF

echo "pg-roundtrip: real-PostgreSQL pytest subset (applies all migrations on the fresh cluster)"
export PROXIMA_TEST_POSTGRES_DSN="postgresql://proxima_roundtrip@127.0.0.1:${PORT}/proxima"
(cd "${REPO_ROOT}" && uv run --python 3.14 --project services/control-plane --extra test pytest tools/tests/test_wb_async_report_postgres.py tools/tests/test_runtime_roles_schema.py -q)

echo "pg-roundtrip: canonical apply path proves idempotence"
SECOND="$(cd "${REPO_ROOT}" && uv run --python 3.14 --project services/control-plane --extra test python tools/apply_migrations.py --env-file "${WORK}/roundtrip.env")"
if [[ "${SECOND}" != "migrations: already current" ]]; then
  echo "pg-roundtrip: FAIL (re-apply not idempotent: ${SECOND})" >&2
  exit 1
fi

EXPECTED="$(ls "${REPO_ROOT}/db/migrations"/*.sql | wc -l | tr -d ' ')"
RECORDED="$("${PGBIN}/psql" -h 127.0.0.1 -p "${PORT}" -U proxima_roundtrip -d proxima -tAc "SELECT count(*) FROM schema_migrations")"
if [[ "${RECORDED}" != "${EXPECTED}" ]]; then
  echo "pg-roundtrip: FAIL (ledger ${RECORDED} != files ${EXPECTED})" >&2
  exit 1
fi
echo "pg-roundtrip: ledger complete (${RECORDED}/${EXPECTED})"

# AD-11/AD-12: provision the production LOGIN roles (plus the proxima_test
# database and the sandbox role) against the disposable cluster, then prove
# the script is idempotent by running it a second time. Secrets live only in
# the throwaway work dir; passwords are generated on the fly.
SECRETS_DIR="${WORK}/secrets"
PROVISION_ARGS=(--psql "${PGBIN}/psql" --secrets-dir "${SECRETS_DIR}"
                --host 127.0.0.1 --port "${PORT}" --database proxima
                --admin-user proxima_roundtrip)
echo "pg-roundtrip: provision runtime roles (run 1 of 2)"
bash "${REPO_ROOT}/infra/bootstrap/provision-runtime-roles.sh" "${PROVISION_ARGS[@]}"
echo "pg-roundtrip: provision runtime roles (run 2 of 2)"
bash "${REPO_ROOT}/infra/bootstrap/provision-runtime-roles.sh" "${PROVISION_ARGS[@]}"
echo "pg-roundtrip: provision: idempotent (2 runs)"

role_dsn() {
  sed -e 's/[[:space:]]*$//' "${SECRETS_DIR}/$1_uri"
}
DSN_COLLECTOR="$(role_dsn proxima_collector)"
DSN_NORM="$(role_dsn proxima_norm)"
DSN_WEBAPP="$(role_dsn proxima_webapp)"
DSN_JANITOR="$(role_dsn proxima_janitor)"
DSN_SANDBOX="$(role_dsn proxima_sandbox)"
export PROXIMA_TEST_DSN_COLLECTOR="${DSN_COLLECTOR}"
export PROXIMA_TEST_DSN_NORM="${DSN_NORM}"
export PROXIMA_TEST_DSN_WEBAPP="${DSN_WEBAPP}"
export PROXIMA_TEST_DSN_JANITOR="${DSN_JANITOR}"
export PROXIMA_TEST_DSN_SANDBOX="${DSN_SANDBOX}"

# Only *.db.test.ts run here; the plain `make test` glob excludes them.
DB_LOG="${WORK}/collector-db-tests.log"
echo "pg-roundtrip: collector db-tests (*.db.test.ts, PROXIMA_TEST_DSN_<ROLE>)"
if ! (cd "${REPO_ROOT}" && npm --workspace @proxima/collector run test:db) >"${DB_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (collector db-tests)" >&2
  cat "${DB_LOG}" >&2
  exit 1
fi
PASSED="$(sed -n 's/^# pass \([0-9][0-9]*\)$/\1/p' "${DB_LOG}" | awk '{s+=$1} END {printf "%d", s}')"
if [[ "${PASSED}" -eq 0 ]]; then
  echo "pg-roundtrip: FAIL (collector db-tests reported 0 passed tests)" >&2
  cat "${DB_LOG}" >&2
  exit 1
fi
echo "pg-roundtrip: collector db-tests: ${PASSED} passed"

# Norm db-tests are Python and self-skip without PROXIMA_TEST_DSN_NORM, so the
# plain `make test` never runs them; here the DSN exists, and a silent skip must
# not pass for green - that is exactly how pg-roundtrip itself can lie.
NORM_LOG="${WORK}/norm-db-tests.log"
echo "pg-roundtrip: norm db-tests (PROXIMA_TEST_DSN_NORM)"
if ! (cd "${REPO_ROOT}" && uv run --python 3.14 --project services/control-plane --extra test \
      pytest services/control-plane/tests/norm/test_norm_db.py -q) >"${NORM_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (norm db-tests)" >&2
  cat "${NORM_LOG}" >&2
  exit 1
fi
if grep -q "skipped" "${NORM_LOG}"; then
  echo "pg-roundtrip: FAIL (norm db-tests skipped while a DSN was available)" >&2
  cat "${NORM_LOG}" >&2
  exit 1
fi
NORM_PASSED="$(sed -n 's/^\([0-9][0-9]*\) passed.*$/\1/p' "${NORM_LOG}" | tail -1)"
if [[ "${NORM_PASSED:-0}" -lt 4 ]]; then
  echo "pg-roundtrip: FAIL (norm db-tests reported ${NORM_PASSED:-0} passed, expected at least 4)" >&2
  cat "${NORM_LOG}" >&2
  exit 1
fi
echo "norm: median window, insufficient 9/14"

# Brief db-tests (Story 2.4) share the norm DSN and add the webapp DSN for the
# RLS matrix; the same no-silent-skip rule applies.
BRIEF_LOG="${WORK}/brief-db-tests.log"
echo "pg-roundtrip: brief db-tests (PROXIMA_TEST_DSN_NORM, PROXIMA_TEST_DSN_WEBAPP)"
if ! (cd "${REPO_ROOT}" && uv run --python 3.14 --project services/control-plane --extra test \
      pytest services/control-plane/tests/brief/test_brief_db.py -q) >"${BRIEF_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (brief db-tests)" >&2
  cat "${BRIEF_LOG}" >&2
  exit 1
fi
if grep -q "skipped" "${BRIEF_LOG}"; then
  echo "pg-roundtrip: FAIL (brief db-tests skipped while a DSN was available)" >&2
  cat "${BRIEF_LOG}" >&2
  exit 1
fi
BRIEF_PASSED="$(sed -n 's/^\([0-9][0-9]*\) passed.*$/\1/p' "${BRIEF_LOG}" | tail -1)"
if [[ "${BRIEF_PASSED:-0}" -lt 7 ]]; then
  echo "pg-roundtrip: FAIL (brief db-tests reported ${BRIEF_PASSED:-0} passed, expected at least 7)" >&2
  cat "${BRIEF_LOG}" >&2
  exit 1
fi
echo "brief: ok, insufficient, blocked, brief_current, webapp RLS"

echo "pg-roundtrip: PASS"
