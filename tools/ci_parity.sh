#!/usr/bin/env bash
# Local replacement for the database-backed and systemd CI checks while
# GitHub Actions is unavailable (D37). Docker is required except for --systemd.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT="proxima-ciparity"
OVERRIDE_FILE="infra/compose.ci-parity.yaml"
PORT="5436"
ONLY=""
DRY_RUN=false
KEEP=false
WORK=""
STAND_USED=false
ROOT_PREPARED=false
SUDO=()
CHECK_NAMES=(db-tests apply-migrations systemd-verify)
CHECK_RESULTS=(NOT-RUN NOT-RUN NOT-RUN)

fail() { echo "ci-parity: FAIL ($*)" >&2; exit 2; }
usage() {
  echo "Usage: tools/ci_parity.sh [--dry-run] [--keep] [--only db|migrations|systemd] [--port N]"
}
shell_join() {
  local out="" item quoted
  for item in "$@"; do
    printf -v quoted '%q' "${item}"
    out="${out}${out:+ }${quoted}"
  done
  printf '%s' "${out}"
}
run() {
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ %s\n' "$(shell_join "$@")"
  else
    "$@"
  fi
}
compose() {
  run "${SUDO[@]}" env "PROXIMA_SECRETS_DIR=${WORK}/secrets" \
    "PROXIMA_RAW_DIR=${WORK}/raw" "PROXIMA_CI_PARITY_PORT=${PORT}" \
    docker compose -p "${PROJECT}" -f infra/compose.yaml -f "${OVERRIDE_FILE}" "$@"
}
selected() { [[ -z "${ONLY}" || "${ONLY}" == "$1" ]]; }
set_result() { CHECK_RESULTS[$1]="$2"; }

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ "${KEEP}" == true ]]; then
    echo "ci-parity: cleanup SKIP (--keep; root ${WORK})"
  else
    if [[ -n "${WORK}" ]]; then
      if [[ "${STAND_USED}" == true ]]; then
        if [[ "${DRY_RUN}" == true ]]; then
          compose down -v --remove-orphans || true
        else
          compose down -v --remove-orphans >/dev/null 2>&1 || true
        fi
      fi
      if [[ "${DRY_RUN}" == true ]]; then
        run rm -rf "${WORK}"
      else
        "${SUDO[@]}" rm -rf "${WORK}"
      fi
    fi
  fi
  exit "${status}"
}
trap cleanup EXIT INT TERM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --keep) KEEP=true; shift ;;
    --only) [[ $# -ge 2 ]] || fail "--only requires a value"; ONLY="$2"; shift 2 ;;
    --port) [[ $# -ge 2 ]] || fail "--port requires a value"; PORT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done
case "${ONLY}" in ""|db|migrations|systemd) ;; *) fail "--only must be db, migrations, or systemd" ;; esac
[[ "${PORT}" =~ ^[0-9]+$ ]] && [[ "${PORT}" -ge 1 && "${PORT}" -le 65535 ]] || fail "--port must be 1..65535"

if [[ "${DRY_RUN}" == true ]]; then
  WORK="/tmp/proxima-ci-parity.DRYRUN"
else
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/proxima-ci-parity.XXXXXX")"
  [[ "$(id -u)" -eq 0 ]] || SUDO=(sudo -n)
fi
cd "${REPO_ROOT}"

write_secret() {
  local path="$1" owner="$2" value="$3"
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ write-secret %s owner %s  # value hidden\n' "${path}" "${owner}"
  else
    printf '%s\n' "${value}" | "${SUDO[@]}" sh -c 'umask 077; cat > "$1"; chown "$2" "$1"; chmod 0600 "$1"' sh "${path}" "${owner}"
  fi
}
prepare_root() {
  local role owner password
  STAND_USED=true
  ROOT_PREPARED=true
  run "${SUDO[@]}" install -d -m 0700 -o 1010 -g 1010 "${WORK}/secrets" "${WORK}/raw"
  write_secret "${WORK}/secrets/postgres_user" 1010:1010 proxima_ciparity
  if [[ "${DRY_RUN}" == true ]]; then password=hidden; else password="$(openssl rand -hex 24)"; fi
  write_secret "${WORK}/secrets/postgres_password" 1010:1010 "${password}"
  for role in proxima_collector proxima_norm proxima_webapp proxima_janitor proxima_sandbox; do
    owner=1010:1010; [[ "${role}" == proxima_webapp ]] && owner=1001:1001
    if [[ "${DRY_RUN}" == true ]]; then password=hidden; else password="$(openssl rand -hex 20)"; fi
    write_secret "${WORK}/secrets/${role}_password" "${owner}" "${password}"
  done
  write_secret "${WORK}/secrets/amirova-test_wb_statistics_token" 1010:1010 placeholder
  write_secret "${WORK}/secrets/amirova-test_wb_analytics_token" 1010:1010 placeholder
}

psql_owner() {
  compose exec -T postgres sh -c 'exec psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 "$@"' sh "$@"
}
provision_roles() {
  local wrapper="${WORK}/psql-owner"
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ write-file %s  # isolated docker exec psql wrapper\n' "${wrapper}"
    printf '+ bash infra/bootstrap/provision-runtime-roles.sh --psql %s --secrets-dir %s --host postgres --port 5432 --database proxima --admin-user proxima_ciparity\n' "${wrapper}" "${WORK}/secrets"
    printf '+ bash infra/bootstrap/provision-runtime-roles.sh --psql %s --secrets-dir %s --host postgres --port 5432 --database proxima --admin-user proxima_ciparity\n' "${wrapper}" "${WORK}/secrets"
    return
  fi
  printf '#!/usr/bin/env bash\nset -euo pipefail\nexec docker exec -i %s-postgres-1 sh -c '\''PGPASSWORD="$(cat /run/secrets/postgres_password)" exec psql "$@"'\'' sh "$@"\n' "${PROJECT}" >"${wrapper}"
  chmod 0755 "${wrapper}"
  "${SUDO[@]}" bash infra/bootstrap/provision-runtime-roles.sh --psql "${wrapper}" --secrets-dir "${WORK}/secrets" --host postgres --port 5432 --database proxima --admin-user proxima_ciparity
  "${SUDO[@]}" bash infra/bootstrap/provision-runtime-roles.sh --psql "${wrapper}" --secrets-dir "${WORK}/secrets" --host postgres --port 5432 --database proxima --admin-user proxima_ciparity
}
export_dsns() {
  local role uri
  for role in collector norm webapp janitor sandbox; do
    if [[ "${DRY_RUN}" == true ]]; then
      uri="postgresql://proxima_${role}:REDACTED@127.0.0.1:${PORT}/proxima"
      [[ "${role}" == sandbox ]] && uri="${uri%/proxima}/proxima_test"
    else
      uri="$("${SUDO[@]}" sed 's/@postgres:5432\//@127.0.0.1:'"${PORT}"'\//' "${WORK}/secrets/proxima_${role}_uri")"
    fi
    case "${role}" in
      collector) export PROXIMA_TEST_DSN_COLLECTOR="${uri}" ;;
      norm) export PROXIMA_TEST_DSN_NORM="${uri}" ;;
      webapp) export PROXIMA_TEST_DSN_WEBAPP="${uri}" ;;
      janitor) export PROXIMA_TEST_DSN_JANITOR="${uri}" ;;
      sandbox) export PROXIMA_TEST_DSN_SANDBOX="${uri}" ;;
    esac
  done
  export PROXIMA_TEST_POSTGRES_DSN="postgresql://proxima_ciparity:REDACTED@127.0.0.1:${PORT}/proxima"
  if [[ "${DRY_RUN}" != true ]]; then
    PROXIMA_TEST_POSTGRES_DSN="postgresql://proxima_ciparity:$("${SUDO[@]}" tr -d '\n' < "${WORK}/secrets/postgres_password")@127.0.0.1:${PORT}/proxima"
    export PROXIMA_TEST_POSTGRES_DSN
  fi
  printf '+ export PROXIMA_TEST_DSN_COLLECTOR PROXIMA_TEST_DSN_NORM PROXIMA_TEST_DSN_WEBAPP PROXIMA_TEST_DSN_JANITOR PROXIMA_TEST_DSN_SANDBOX PROXIMA_TEST_POSTGRES_DSN  # values hidden\n'
}

db_tests() {
  local ledger
  prepare_root
  compose up -d --wait postgres
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ schema-check SELECT count(*) || '\''|'\'' || max(version) FROM schema_migrations  # expect 18|18\n'
  else
    ledger="$(psql_owner -tAc "SELECT count(*) || '|' || max(version) FROM schema_migrations")"
    [[ "${ledger}" == "18|18" ]] || { echo "ci-parity: ledger FAIL (${ledger}, expected 18|18)" >&2; return 1; }
  fi
  provision_roles
  export_dsns
  run uv run --python 3.14 --project services/control-plane --extra test pytest tools/tests/test_wb_async_report_postgres.py tools/tests/test_runtime_roles_schema.py -q
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ export PROXIMA_TEST_PYTHON="$(uv run --python 3.14 --project services/control-plane --extra test python -c '\''import sys; print(sys.executable)'\'')"\n'
  else
    export PROXIMA_TEST_PYTHON
    PROXIMA_TEST_PYTHON="$(uv run --python 3.14 --project services/control-plane --extra test python -c 'import sys; print(sys.executable)')"
  fi
  run npm --workspace @proxima/collector run test:db
  run uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests/norm/test_norm_db.py services/control-plane/tests/brief/test_brief_db.py -q
  run npm --workspace @proxima/collector exec -- tsx --test --test-concurrency=1 tests/delete-run.db.test.ts
  run npm --workspace @proxima/collector exec -- tsx --test --test-concurrency=1 tests/funnel-v3.db.test.ts
  run npm --workspace @proxima/collector exec -- tsx --test --test-concurrency=1 tests/nm-daily.db.test.ts
  run uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests/detector/test_detector_db.py -q
}

migrations_check() {
  [[ "${ROOT_PREPARED}" == true ]] || prepare_root
  compose up -d --wait postgres
  compose --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env
}
systemd_check() {
  if [[ "${DRY_RUN}" == true ]]; then
    run systemd-analyze verify infra/systemd/\*.service infra/systemd/\*.timer
  elif ! command -v systemd-analyze >/dev/null 2>&1; then
    return 3
  else
    systemd-analyze verify infra/systemd/*.service infra/systemd/*.timer
  fi
}

if selected db; then if db_tests; then set_result 0 PASS; else set_result 0 FAIL; fi; fi
if selected migrations; then if migrations_check; then set_result 1 PASS; else set_result 1 FAIL; fi; fi
if selected systemd; then
  if systemd_check; then set_result 2 PASS
  elif [[ $? -eq 3 ]]; then set_result 2 "SKIP (no systemd-analyze)"
  else set_result 2 FAIL; fi
fi

overall=0
for index in 0 1 2; do
  [[ "${CHECK_RESULTS[$index]}" == NOT-RUN ]] && continue
  echo "ci-parity: ${CHECK_NAMES[$index]} ${CHECK_RESULTS[$index]}"
  [[ "${CHECK_RESULTS[$index]}" == FAIL ]] && overall=1
done
echo "ci-parity: exit-code ${overall}"
exit "${overall}"
