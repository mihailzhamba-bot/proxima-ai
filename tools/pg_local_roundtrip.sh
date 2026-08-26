#!/usr/bin/env bash
# Disposable local PostgreSQL migration roundtrip (Phase 3 plan 03-01, Task 3).
# No Docker, no VPS: initdb a throwaway PostgreSQL 16 cluster in the OS temp
# dir, apply every verified migration through the canonical apply path, prove
# idempotent re-apply, run the real-PostgreSQL pytest subset, assert ledger
# completeness, then destroy the cluster. Exits 0 with SKIP when no initdb.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PROXIMA_PG_ROUNDTRIP_PORT:-55432}"

PGBIN=""
for candidate in "$(dirname "$(command -v initdb 2>/dev/null || true)")" /opt/homebrew/opt/postgresql@16/bin /usr/lib/postgresql/16/bin /usr/local/opt/postgresql@16/bin; do
  if [[ -x "${candidate}/initdb" ]]; then PGBIN="${candidate}"; break; fi
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

echo "pg-roundtrip: PASS"
