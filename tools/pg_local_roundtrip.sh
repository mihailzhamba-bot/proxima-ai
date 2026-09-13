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
if [[ -z "${PGBIN}" && -n "${PROXIMA_PG16_BIN:-}" && -x "${PROXIMA_PG16_BIN}/initdb" ]] \
   && "${PROXIMA_PG16_BIN}/initdb" --version 2>/dev/null | grep -qE 'PostgreSQL[)] 16\.'; then
  # Opt-in escape hatch for environments whose PostgreSQL 16 tools live
  # outside the searched paths (e.g. container toolchains on PATH shims).
  PGBIN="${PROXIMA_PG16_BIN}"
fi
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

# Story 1.8: put one production-shaped fact in the main database, rebuild the
# test copy twice, then prove that the sandbox can read and write the copy but
# cannot connect to the main database. The marker table is deliberately
# created in the disposable source database so pg_dump must carry it across.
REFRESH_TENANT="refresh-harness"
REFRESH_RUN="00000000-0000-4000-8000-000000000018"
"${PGBIN}/psql" -h 127.0.0.1 -p "${PORT}" -U proxima_roundtrip -d proxima -v ON_ERROR_STOP=1 <<SQL >/dev/null
INSERT INTO tenants (tenant_id) VALUES ('${REFRESH_TENANT}') ON CONFLICT DO NOTHING;
INSERT INTO collector_runs (run_id, tenant_id, kind, status, finished_at)
VALUES ('${REFRESH_RUN}', '${REFRESH_TENANT}', 'collect', 'SUCCEEDED', CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;
INSERT INTO fact_cabinet_daily
  (tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count,
   returns_count, revenue_rub, forpay_rub, evidence_sha256)
VALUES
  ('${REFRESH_TENANT}', CURRENT_DATE - 1, '${REFRESH_RUN}', 1, 0, 1, 0, 1.00, 1.00,
   ARRAY['0000000000000000000000000000000000000000000000000000000000000018'::char(64)])
ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS sandbox_refresh_probe (value text NOT NULL);
SQL

REFRESH_ENV=(PGHOST=127.0.0.1 PGPORT="${PORT}" PGUSER=proxima_roundtrip
             PROXIMA_PSQL_PATH="${PGBIN}/psql" PROXIMA_PG_DUMP_PATH="${PGBIN}/pg_dump"
             PROXIMA_TENANT_ID="${REFRESH_TENANT}")
echo "pg-roundtrip: test-db-refresh (run 1 of 2)"
env "${REFRESH_ENV[@]}" bash "${REPO_ROOT}/tools/test_db_refresh.sh"
echo "pg-roundtrip: test-db-refresh (run 2 of 2)"
env "${REFRESH_ENV[@]}" bash "${REPO_ROOT}/tools/test_db_refresh.sh"

FACT_COUNT="$("${PGBIN}/psql" "${DSN_SANDBOX}" -v ON_ERROR_STOP=1 -tAc 'SELECT count(*) FROM fact_cabinet_daily_current')"
[[ "${FACT_COUNT}" -gt 0 ]] || { echo "pg-roundtrip: FAIL (sandbox sees no copied facts)" >&2; exit 1; }
"${PGBIN}/psql" "${DSN_SANDBOX}" -v ON_ERROR_STOP=1 -c "INSERT INTO sandbox_refresh_probe(value) VALUES ('copy-only')" >/dev/null
SANDBOX_MAIN_DSN="$(printf '%s' "${DSN_SANDBOX}" | sed 's|/proxima_test$|/proxima|')"
if "${PGBIN}/psql" "${SANDBOX_MAIN_DSN}" -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null 2>&1; then
  echo "pg-roundtrip: FAIL (sandbox connected to main database)" >&2
  exit 1
fi
echo "test-db-refresh: sandbox sees copy"

# Only *.db.test.ts run here; the plain `make test` glob excludes them.
DB_LOG="${WORK}/collector-db-tests.log"
# tools/delete_run.py needs psycopg, and delete-run.db.test.ts shells out to it.
# That test matches the generic tests/*.db.test.ts glob as well as its own step,
# so the interpreter is resolved once here and exported for both - a bare python3
# has no psycopg and the test would fail in the glob while passing in its step.
PROJECT_PY="$(cd "${REPO_ROOT}" && uv run --python 3.14 --project services/control-plane --extra test python -c 'import sys; print(sys.executable)')"
export PROXIMA_TEST_PYTHON="${PROJECT_PY}"
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
  echo "pg-roundtrip: FAIL (norm db-tests reported ${NORM_PASSED:-0} passed, expected at least 5)" >&2
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

# Story 1.7: delete_run closure over collector_run_inputs plus the AD-11/AD-12
# RLS matrix, both through the real janitor LOGIN role. The db-test shells out
# to tools/delete_run.py via the project interpreter (psycopg lives there).
echo "pg-roundtrip: delete-run db-tests (closure, rls matrix; PROXIMA_TEST_DSN_JANITOR)"
DELETE_LOG="${WORK}/delete-run-db-tests.log"
if ! (cd "${REPO_ROOT}" && \
      npm --workspace @proxima/collector exec -- tsx --test --test-concurrency=1 tests/delete-run.db.test.ts) >"${DELETE_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (delete-run db-tests)" >&2
  cat "${DELETE_LOG}" >&2
  exit 1
fi
if grep -q "^# fail [1-9]" "${DELETE_LOG}" || grep -q "^not ok" "${DELETE_LOG}"; then
  echo "pg-roundtrip: FAIL (delete-run db-tests reported failures)" >&2
  cat "${DELETE_LOG}" >&2
  exit 1
fi
# node:test always prints a "# skipped N" summary line, so the guard has to look
# at the count: matching the word alone fires on "# skipped 0" and fails every run.
if grep -qE "^# skipped [1-9]" "${DELETE_LOG}"; then
  echo "pg-roundtrip: FAIL (delete-run db-tests skipped while a DSN was available)" >&2
  cat "${DELETE_LOG}" >&2
  exit 1
fi
DELETE_PASSED="$(sed -n 's/^# pass \([0-9][0-9]*\)$/\1/p' "${DELETE_LOG}" | awk '{s+=$1} END {printf "%d", s}')"
if [[ "${DELETE_PASSED}" -lt 5 ]]; then
  echo "pg-roundtrip: FAIL (delete-run db-tests reported ${DELETE_PASSED:-0} passed, expected at least 4)" >&2
  cat "${DELETE_LOG}" >&2
  exit 1
fi
echo "delete_run: closure (${DELETE_PASSED} tests incl. rls: matrix)"

# Story 3.1: the funnel_v3 job end to end on the fixture - 21 observations,
# replay 0, changed payload versions, run_day not versioned, a failed batch
# keeping the received ones, RLS matrix - through the collector/norm/webapp
# LOGIN roles. The glob above already ran the file; this step refuses a silent skip.
echo "pg-roundtrip: funnel db-tests (PROXIMA_TEST_DSN_COLLECTOR, PROXIMA_TEST_DSN_NORM, PROXIMA_TEST_DSN_WEBAPP)"
FUNNEL_LOG="${WORK}/funnel-db-tests.log"
if ! (cd "${REPO_ROOT}" && \
      npm --workspace @proxima/collector exec -- tsx --test --test-concurrency=1 tests/funnel-v3.db.test.ts) >"${FUNNEL_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (funnel db-tests)" >&2
  cat "${FUNNEL_LOG}" >&2
  exit 1
fi
if grep -q "^# fail [1-9]" "${FUNNEL_LOG}" || grep -q "^not ok" "${FUNNEL_LOG}"; then
  echo "pg-roundtrip: FAIL (funnel db-tests reported failures)" >&2
  cat "${FUNNEL_LOG}" >&2
  exit 1
fi
if grep -qE "^# skipped [1-9]" "${FUNNEL_LOG}"; then
  echo "pg-roundtrip: FAIL (funnel db-tests skipped while the DSNs were available)" >&2
  cat "${FUNNEL_LOG}" >&2
  exit 1
fi
FUNNEL_PASSED="$(sed -n 's/^# pass \([0-9][0-9]*\)$/\1/p' "${FUNNEL_LOG}" | awk '{s+=$1} END {printf "%d", s}')"
if [[ "${FUNNEL_PASSED}" -lt 2 ]]; then
  echo "pg-roundtrip: FAIL (funnel db-tests reported ${FUNNEL_PASSED:-0} passed, expected at least 2)" >&2
  cat "${FUNNEL_LOG}" >&2
  exit 1
fi
echo "funnel_v3: db ${FUNNEL_PASSED} tests (21 obs, replay 0, versions, coverage, rls)"

# Story 4.0 (AD-19): the collect run on the fixtures versions fact_nm_daily and
# dim_nm_subject - one row per (day, nmId) with a category, per-nm sums equal
# to the cabinet day, replay, transitive delete_run, RLS matrix - through the
# collector/norm/webapp/janitor LOGIN roles. The glob above already ran the
# file; this step refuses a silent skip.
echo "pg-roundtrip: nm-daily db-tests (PROXIMA_TEST_DSN_COLLECTOR, _NORM, _WEBAPP, _JANITOR)"
NM_DAILY_LOG="${WORK}/nm-daily-db-tests.log"
if ! (cd "${REPO_ROOT}" && \
      npm --workspace @proxima/collector exec -- tsx --test --test-concurrency=1 tests/nm-daily.db.test.ts) >"${NM_DAILY_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (nm-daily db-tests)" >&2
  cat "${NM_DAILY_LOG}" >&2
  exit 1
fi
if grep -q "^# fail [1-9]" "${NM_DAILY_LOG}" || grep -q "^not ok" "${NM_DAILY_LOG}"; then
  echo "pg-roundtrip: FAIL (nm-daily db-tests reported failures)" >&2
  cat "${NM_DAILY_LOG}" >&2
  exit 1
fi
if grep -qE "^# skipped [1-9]" "${NM_DAILY_LOG}"; then
  echo "pg-roundtrip: FAIL (nm-daily db-tests skipped while the DSNs were available)" >&2
  cat "${NM_DAILY_LOG}" >&2
  exit 1
fi
NM_DAILY_PASSED="$(sed -n 's/^# pass \([0-9][0-9]*\)$/\1/p' "${NM_DAILY_LOG}" | awk '{s+=$1} END {printf "%d", s}')"
if [[ "${NM_DAILY_PASSED}" -lt 3 ]]; then
  echo "pg-roundtrip: FAIL (nm-daily db-tests reported ${NM_DAILY_PASSED:-0} passed, expected at least 3)" >&2
  cat "${NM_DAILY_LOG}" >&2
  exit 1
fi
echo "order-counts: db ${NM_DAILY_PASSED} tests (rows per day x nmId, sums vs cabinet, replay, delete_run, rls)"

# Story 4.1 (AD-19): the detector as a step of the brief run - ranked, schema-valid
# signals on fact_nm_daily/dim_nm_subject through the norm LOGIN role, none when
# the brief is not ok, the read runs in run_inputs, deterministic snapshot. Python,
# self-skips without the DSNs; a silent skip must not pass for green here.
DETECTOR_LOG="${WORK}/detector-db-tests.log"
echo "pg-roundtrip: detector db-tests (PROXIMA_TEST_DSN_NORM)"
if ! (cd "${REPO_ROOT}" && uv run --python 3.14 --project services/control-plane --extra test \
      pytest services/control-plane/tests/detector/test_detector_db.py -q) >"${DETECTOR_LOG}" 2>&1; then
  echo "pg-roundtrip: FAIL (detector db-tests)" >&2
  cat "${DETECTOR_LOG}" >&2
  exit 1
fi
if grep -q "skipped" "${DETECTOR_LOG}"; then
  echo "pg-roundtrip: FAIL (detector db-tests skipped while a DSN was available)" >&2
  cat "${DETECTOR_LOG}" >&2
  exit 1
fi
DETECTOR_PASSED="$(sed -n 's/^\([0-9][0-9]*\) passed.*$/\1/p' "${DETECTOR_LOG}" | tail -1)"
if [[ "${DETECTOR_PASSED:-0}" -lt 5 ]]; then
  echo "pg-roundtrip: FAIL (detector db-tests reported ${DETECTOR_PASSED:-0} passed, expected at least 5)" >&2
  cat "${DETECTOR_LOG}" >&2
  exit 1
fi
echo "detector: db signals on nm facts, none when brief not ok (${DETECTOR_PASSED} tests)"

# LOOP: run real DB tests in the webapp too; this must not silently skip.
LOOP_LOG="${WORK}/loop-db-tests.log"
if ! (cd "${REPO_ROOT}" && npm --workspace @proxima/webapp exec -- vitest run src/tests/loop.db.test.ts) >"${LOOP_LOG}" 2>&1; then
  python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text())' "${LOOP_LOG}"
  exit 1
fi
if grep -q 'skipped' "${LOOP_LOG}"; then
  printf '%s\n' 'pg-roundtrip: FAIL (LOOP tests skipped)'
  exit 1
fi
printf '%s\n' 'loop: transactions, membership, retries, RLS, cancellation, observation'

echo "pg-roundtrip: PASS"
