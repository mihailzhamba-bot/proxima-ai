#!/usr/bin/env bash
# Rehearsal of release 1.14 on the VPS in a disposable compose project (D35, NOT a deploy).
#
# Replays docs/operations/release-m01.md §2-§4 against the project `proxima-rehearsal`
# (infra/compose.yaml + infra/compose.rehearsal.yaml): own postgres on 127.0.0.1:5434, own
# network, own volume, own secrets/raw directories under --root. The production project
# `proxima-ai`, /srv/proxima-ai and /etc/proxima-ai/secrets are never touched.
#
# Usage:
#   rehearsal_run.sh [--dry-run] init     --root <dir> --statistics-token-src <path>
#   rehearsal_run.sh [--dry-run] up       --root <dir>
#   rehearsal_run.sh [--dry-run] backfill --root <dir> [--artifacts-dir <dir>]
#   rehearsal_run.sh [--dry-run] tail     --root <dir> --live
#   rehearsal_run.sh [--dry-run] steps    --root <dir>
#   rehearsal_run.sh [--dry-run] check    --root <dir>
#   rehearsal_run.sh [--dry-run] down     --root <dir>
#   rehearsal_run.sh [--dry-run] all      --root <dir> [--live] [--artifacts-dir <dir>]
#
# `all` = up -> backfill -> tail (only with --live) -> steps -> check; `init` and `down` are
# always separate. `tail --live` is the only step that reaches WB: 2 read calls (orders +
# sales on the statistics token), the D35 exception. --dry-run prints every command and runs
# nothing. Secret values are never printed (file names only). Privileged calls go through
# `sudo -n` when not root; the invoking user needs passwordless sudo (proxima-admin has it).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly SCRIPT_DIR REPO_ROOT

readonly PROJECT="proxima-rehearsal"
readonly OVERRIDE_FILE="infra/compose.rehearsal.yaml"
readonly TENANT="amirova-test"
readonly PG_PORT_DEFAULT="5434"
readonly WEBAPP_PORT_DEFAULT="3434"
readonly POSTGRES_USER_VALUE="proxima"
readonly CONTAINER_USER="1010:1010"
# The webapp image runs as uid 1001 (services/webapp/Dockerfile), not 1010: its URI/password files
# get that owner (D35 addendum, Mike 08.09) - the same rule provision-runtime-roles.sh re-asserts.
readonly WEBAPP_USER="1001:1001"
readonly RUNTIME_ROLES=(proxima_collector proxima_norm proxima_webapp proxima_janitor proxima_sandbox)

# Runbook §3: the 31.08 pair, the only history copy before the WB window (D15).
readonly ARTIFACTS_DIR_DEFAULT="${HOME}/signal-inputs/fixtures/wb-api/statistics"
readonly SALES_FILE="supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json"
readonly ORDERS_FILE="supplier-orders/20260831T155341Z__dateFrom-2023-01-01_flag-0.json"
readonly SALES_SHA="d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96"
readonly ORDERS_SHA="0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40"
readonly RETRIEVED_AT="2026-08-31T15:53:41Z"
# Runbook §3 / AC Story 1.13 (CP-1): overlap tail from 27.08.
readonly DATE_FROM="2026-08-27"

# Runbook §4 references: docs/state/API-FACTS.md, «Эталоны недельных сумм W10/W35» and «Что
# означают эталоны» (rule of Mike, 08.09.2026 ~13:40 UTC). W10 (ISO 2026-03-02..2026-03-08)
# is the 30.08 fixture recomputed with the glossary formulas (kopecks from the 08.09 recompute;
# SPEC/epics keep the rounded «700 860») and is compared as a week sum. W35
# (2026-08-24..2026-08-30) is never compared as a week: days 24-26.08 lie before the live tail
# (DATE_FROM) and must equal the loaded 31.08 pair day by day
# (calendar_day|orders_count|cancelled_count|revenue_rub - jq over the pair, 08.09; the stand's
# fact_cabinet_daily_current gave the same); days DATE_FROM..W35_LAST_DAY are rewritten by the
# tail and must equal the latest observations of the stand itself (stg_wb_orders_latest grouped
# by the Moscow day of payload.date, isCancel not-true / true) - an internal-consistency check
# without an external constant. Any mismatch = gate not passed.
readonly W10_EXPECTED="W10|649|700860.50"
readonly -a W35_DAYS_EXPECTED=(
  "2026-08-24|55|6|62146.87"
  "2026-08-25|40|7|29247.90"
  "2026-08-26|28|4|44956.00"
)
readonly W35_LAST_DAY="2026-08-30"

DRY_RUN=false
LIVE=false
ROOT=""
TOKEN_SRC=""
ARTIFACTS_DIR="${ARTIFACTS_DIR_DEFAULT}"
SUBCOMMAND=""

# Privilege prefix: empty when already root (bash >= 4.4 expands an empty array cleanly).
SUDO=(sudo -n)
if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
fi

usage() {
  sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' >&2
  exit 64
}

fail() {
  printf '%s\n' "rehearsal_run: $*" >&2
  exit 1
}

note() {
  printf '%s\n' "rehearsal_run: $*"
}

# --- command runner (dry-run aware) ---------------------------------------------------------

shell_quote() {
  local arg="$1"
  if [[ "${arg}" =~ ^[A-Za-z0-9_./:@=+,%-]+$ ]]; then
    printf '%s' "${arg}"
  else
    printf "'%s'" "${arg//\'/\'\\\'\'}"
  fi
}

shell_join() {
  local out="" arg
  for arg in "$@"; do
    out="${out}${out:+ }$(shell_quote "${arg}")"
  done
  printf '%s' "${out}"
}

run() {
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ %s\n' "$(shell_join "$@")"
    return 0
  fi
  "$@"
}

# Privileged variant: `sudo -n` in front unless already root.
run_root() {
  run "${SUDO[@]}" "$@"
}

# Runs a privileged command and mirrors its output into <root>/logs/<name>.log (no secrets in
# any of these outputs: provision prints names only, compose jobs log JSON steps).
run_root_logged() {
  local name="$1"
  shift
  local log="${ROOT}/logs/${name}.log"
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ %s 2>&1 | tee %s\n' "$(shell_join "${SUDO[@]}" "$@")" "$(shell_quote "${log}")"
    return 0
  fi
  mkdir -p "${ROOT}/logs"
  "${SUDO[@]}" "$@" 2>&1 | tee "${log}"
}

compose_base() {
  printf '%s\n' docker compose --env-file "${ROOT}/.env" -p "${PROJECT}" \
    -f infra/compose.yaml -f "${OVERRIDE_FILE}"
}

compose() {
  local -a base
  mapfile -t base < <(compose_base)
  run_root "${base[@]}" "$@"
}

compose_logged() {
  local name="$1"
  shift
  local -a base
  mapfile -t base < <(compose_base)
  run_root_logged "${name}" "${base[@]}" "$@"
}

# Owner psql inside the rehearsal postgres container (runbook form `psqlp`): SQL on stdin,
# user name read inside the container from /run/secrets, socket auth, nothing printed.
# shellcheck disable=SC2016
readonly PSQL_OWNER_SNIPPET='psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 "$@"'

run_sql() {
  local sql="$1"
  shift
  local -a cmd=(docker exec -i "${PROJECT}-postgres-1" sh -c "${PSQL_OWNER_SNIPPET}" sh "$@")
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ printf %%s %s | %s\n' "$(shell_quote "${sql}")" "$(shell_join "${SUDO[@]}" "${cmd[@]}")"
    return 0
  fi
  printf '%s\n' "${sql}" | "${SUDO[@]}" "${cmd[@]}"
}

# Real-mode variant: returns the -tA output for comparisons (one query, printed by the caller).
sql_capture() {
  local sql="$1"
  printf '%s\n' "${sql}" | "${SUDO[@]}" docker exec -i "${PROJECT}-postgres-1" sh -c "${PSQL_OWNER_SNIPPET}" sh -tA
}

readonly SCHEMA_SQL="SELECT count(*) || '|' || max(version) FROM schema_migrations;"

# Writes a secret file from stdin as <owner> 0600 (default 1010:1010, the job container user).
# The value never appears on a command line.
write_secret() {
  local path="$1" owner="${2:-${CONTAINER_USER}}"
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ write-secret %s owner %s  # value generated in memory, never printed\n' \
      "$(shell_quote "${path}")" "${owner}"
    return 0
  fi
  # shellcheck disable=SC2016
  "${SUDO[@]}" sh -c 'umask 077 && cat > "$1" && chown "$2" "$1" && chmod 0600 "$1"' sh "${path}" "${owner}"
}

# --- argument parsing -----------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ; shift ;;
    --live) LIVE=true ; shift ;;
    --root) ROOT="${2:?--root requires a value}" ; shift 2 ;;
    --statistics-token-src) TOKEN_SRC="${2:?--statistics-token-src requires a value}" ; shift 2 ;;
    --artifacts-dir) ARTIFACTS_DIR="${2:?--artifacts-dir requires a value}" ; shift 2 ;;
    -h | --help) usage ;;
    --*) fail "unknown option: $1" ;;
    *)
      [[ -z "${SUBCOMMAND}" ]] || fail "unexpected argument: $1"
      SUBCOMMAND="$1"
      shift
      ;;
  esac
done

[[ -n "${SUBCOMMAND}" ]] || usage
[[ -n "${ROOT}" ]] || fail "--root <dir> is required"
[[ "${ROOT}" == /* ]] || fail "--root must be an absolute path"
ROOT="${ROOT%/}"
case "${ROOT}" in
  /srv/proxima-ai* | /etc/proxima-ai* | / | /srv | /etc)
    fail "--root must not point at the production tree: ${ROOT}" ;;
esac
case "${ROOT}/" in
  "${REPO_ROOT}"/*) fail "--root must stay outside the git checkout (CAS root rule): ${ROOT}" ;;
esac
[[ -f "${REPO_ROOT}/${OVERRIDE_FILE}" ]] || fail "override file is missing: ${REPO_ROOT}/${OVERRIDE_FILE}"

cd "${REPO_ROOT}"

require_initialized() {
  [[ "${DRY_RUN}" == true ]] && return 0
  [[ -f "${ROOT}/.env" ]] || fail "${ROOT}/.env is missing - run 'init' first"
  [[ -x "${ROOT}/bin/psql-owner" ]] || fail "${ROOT}/bin/psql-owner is missing - run 'init' first"
}

git_sha() {
  git -C "${REPO_ROOT}" rev-parse HEAD
}

expected_schema() {
  local count last
  count="$(find "${REPO_ROOT}/db/migrations" -maxdepth 1 -name '[0-9][0-9][0-9]_*.sql' | wc -l | tr -d ' ')"
  last="$(find "${REPO_ROOT}/db/migrations" -maxdepth 1 -name '[0-9][0-9][0-9]_*.sql' -printf '%f\n' | sort | tail -n 1 | cut -c1-3 | sed 's/^0*//')"
  [[ "${count}" == "${last}" ]] || fail "db/migrations is not contiguous: ${count} files, last number ${last}"
  printf '%s|%s' "${count}" "${last}"
}

# --- init -----------------------------------------------------------------------------------

do_init() {
  [[ -n "${TOKEN_SRC}" ]] || fail "init requires --statistics-token-src <path>"
  if [[ "${DRY_RUN}" != true ]]; then
    [[ ! -e "${ROOT}/.env" ]] || fail "${ROOT}/.env already exists - 'down' and remove ${ROOT} before a new init"
    "${SUDO[@]}" test -f "${TOKEN_SRC}" || fail "statistics token source is not a file: ${TOKEN_SRC}"
    command -v openssl >/dev/null 2>&1 || fail "openssl is required to generate passwords"
  fi

  note "init: rehearsal root ${ROOT} (secrets, raw, bin, logs, .env)"
  run mkdir -p "${ROOT}" "${ROOT}/bin" "${ROOT}/logs"
  run_root install -d -m 0700 -o 1010 -g 1010 "${ROOT}/secrets" "${ROOT}/raw"

  # Owner credentials for the rehearsal postgres (POSTGRES_USER_FILE / POSTGRES_PASSWORD_FILE).
  if [[ "${DRY_RUN}" == true ]]; then
    write_secret "${ROOT}/secrets/postgres_user"
    write_secret "${ROOT}/secrets/postgres_password"
  else
    printf '%s\n' "${POSTGRES_USER_VALUE}" | write_secret "${ROOT}/secrets/postgres_user"
    openssl rand -hex 24 | write_secret "${ROOT}/secrets/postgres_password"
  fi

  # Runtime roles: the same files infra/bootstrap/provision-runtime-roles.sh reads and writes
  # (<role>_password -> <role>_uri, host `postgres`, port 5432). Pre-creating them keeps the
  # provision run idempotent on these values and gives compose its secret files before `up`.
  # Owner: 1010:1010 for the job roles, 1001:1001 for proxima_webapp (webapp image uid).
  local role database password owner
  for role in "${RUNTIME_ROLES[@]}"; do
    database="proxima"
    owner="${CONTAINER_USER}"
    [[ "${role}" == "proxima_sandbox" ]] && database="proxima_test"
    [[ "${role}" == "proxima_webapp" ]] && owner="${WEBAPP_USER}"
    if [[ "${DRY_RUN}" == true ]]; then
      write_secret "${ROOT}/secrets/${role}_password" "${owner}"
      write_secret "${ROOT}/secrets/${role}_uri" "${owner}"
    else
      password="$(openssl rand -hex 20)"
      printf '%s\n' "${password}" | write_secret "${ROOT}/secrets/${role}_password" "${owner}"
      printf 'postgresql://%s:%s@postgres:5432/%s\n' "${role}" "${password}" "${database}" \
        | write_secret "${ROOT}/secrets/${role}_uri" "${owner}"
      password=""
    fi
  done

  # Statistics token: copied as root, never read into the shell. Analytics token: EMPTY
  # placeholder - compose needs the file to exist, the rehearsal does not run the funnel.
  run_root install -m 0600 -o 1010 -g 1010 "${TOKEN_SRC}" "${ROOT}/secrets/${TENANT}_wb_statistics_token"
  run_root install -m 0600 -o 1010 -g 1010 /dev/null "${ROOT}/secrets/${TENANT}_wb_analytics_token"

  # Owner psql wrapper for provision-runtime-roles.sh --psql (runbook §1.4 form, container of
  # this project instead of proxima-ai-postgres-1).
  local wrapper="${ROOT}/bin/psql-owner"
  local wrapper_body
  wrapper_body="$(cat <<EOF
#!/usr/bin/env bash
# Rehearsal (D35): owner psql inside ${PROJECT}-postgres-1 for provision-runtime-roles.sh (--psql).
# The password is read from /run/secrets inside the container and never leaves it.
set -euo pipefail
exec docker exec -i ${PROJECT}-postgres-1 sh -c \\
  'PGPASSWORD="\$(cat /run/secrets/postgres_password)" exec psql "\$@"' sh "\$@"
EOF
)"
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ write-file %s (mode 0755):\n' "$(shell_quote "${wrapper}")"
    printf '%s\n' "${wrapper_body}" | sed 's/^/    /'
  else
    printf '%s\n' "${wrapper_body}" > "${wrapper}"
    chmod 0755 "${wrapper}"
  fi

  local env_file="${ROOT}/.env"
  local env_body
  env_body="$(cat <<EOF
# Rehearsal of release 1.14 (D35) - disposable compose project next to the production one.
# Paths only, no secret values. Used as: docker compose --env-file ${env_file} ...
COMPOSE_PROJECT_NAME=${PROJECT}
COMPOSE_FILE=infra/compose.yaml:${OVERRIDE_FILE}
PROXIMA_SECRETS_DIR=${ROOT}/secrets
PROXIMA_RAW_DIR=${ROOT}/raw
PROXIMA_REHEARSAL_PG_PORT=${PG_PORT_DEFAULT}
# Webapp preview (infra/webapp.staging.compose.yaml as a third -f): postgres mode on 127.0.0.1:${WEBAPP_PORT_DEFAULT}.
WEBAPP_DATA_MODE=postgres
WEBAPP_TENANT_ID=${TENANT}
PROXIMA_WEBAPP_PORT=${WEBAPP_PORT_DEFAULT}
EOF
)"
  if [[ "${DRY_RUN}" == true ]]; then
    printf '+ write-file %s (mode 0600):\n' "$(shell_quote "${env_file}")"
    printf '%s\n' "${env_body}" | sed 's/^/    /'
  else
    (umask 077 && printf '%s\n' "${env_body}" > "${env_file}")
  fi

  run_root ls -la "${ROOT}/secrets"
  note "init: done; next - 'up --root ${ROOT}'"
}

# --- up: images, postgres, migrations, roles (runbook §2, §1.4) -----------------------------

do_up() {
  require_initialized
  local schema
  schema="$(expected_schema)"

  note "up: building job images and starting postgres for project ${PROJECT}"
  compose --profile jobs build
  compose up -d --wait --wait-timeout 180 postgres
  # shellcheck disable=SC2016
  run_root sh -c 'docker ps --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" | grep proxima'

  # Fresh volume: infra/compose.yaml mounts db/migrations into /docker-entrypoint-initdb.d, so
  # postgres applied every migration at first init. The runbook §2 command still runs to
  # rehearse the container path (owner secrets, jobs.env allowlist, ledger checksums); here it
  # is expected to answer `migrations: already current`, on 15.09 a list 007..0NN.
  note "up: apply-migrations via control-plane-admin (expected here: 'migrations: already current')"
  compose_logged apply-migrations --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env
  note "up: schema_migrations expected ${schema} (count|max from db/migrations)"
  if [[ "${DRY_RUN}" == true ]]; then
    run_sql "${SCHEMA_SQL}" -tA
  else
    local actual
    actual="$(sql_capture "${SCHEMA_SQL}")"
    printf 'schema_migrations: %s\n' "${actual}"
    [[ "${actual}" == "${schema}" ]] || fail "schema_migrations is ${actual}, expected ${schema}"
    [[ "$("${SUDO[@]}" cat "${ROOT}/secrets/postgres_user")" == "${POSTGRES_USER_VALUE}" ]] \
      || fail "postgres_user differs from the init value (file name only: ${ROOT}/secrets/postgres_user)"
  fi

  # Runbook §1.4 / §2: two provision runs, the second proves idempotence. Migrations 011+ are
  # already in, so neither run may warn about missing ledger group roles.
  local pass
  for pass in 1 2; do
    note "up: provision-runtime-roles (run ${pass} of 2)"
    run_root_logged "provision-${pass}" bash infra/bootstrap/provision-runtime-roles.sh \
      --psql "${ROOT}/bin/psql-owner" --secrets-dir "${ROOT}/secrets" \
      --host postgres --port 5432 --database proxima \
      --admin-user "${POSTGRES_USER_VALUE}"
    if [[ "${DRY_RUN}" != true ]]; then
      grep -q 'provision-runtime-roles: ok (6 login roles' "${ROOT}/logs/provision-${pass}.log" \
        || fail "provision run ${pass} did not report ok"
      ! grep -q 'WARNING' "${ROOT}/logs/provision-${pass}.log" \
        || fail "provision run ${pass} printed a WARNING (see ${ROOT}/logs/provision-${pass}.log)"
    fi
  done
  note "up: done"
}

# --- backfill: CAS import + backfill from the 31.08 pair (runbook §3) -----------------------

do_backfill() {
  require_initialized
  local sales="${ARTIFACTS_DIR}/${SALES_FILE}"
  local orders="${ARTIFACTS_DIR}/${ORDERS_FILE}"

  note "backfill: verifying the 31.08 pair under ${ARTIFACTS_DIR}"
  run sha256sum "${sales}" "${orders}"
  if [[ "${DRY_RUN}" != true ]]; then
    [[ "$(sha256sum "${sales}" | cut -d' ' -f1)" == "${SALES_SHA}" ]] || fail "sales artifact sha256 mismatch: ${sales}"
    [[ "$(sha256sum "${orders}" | cut -d' ' -f1)" == "${ORDERS_SHA}" ]] || fail "orders artifact sha256 mismatch: ${orders}"
  fi

  # tools/cas_import.ts is not in the collector image; it runs on the host with tsx (runbook §3).
  if [[ "${DRY_RUN}" == true || ! -x "${REPO_ROOT}/node_modules/.bin/tsx" ]]; then
    note "backfill: node_modules/.bin/tsx missing -> npm ci (network), skipped when already present"
    run env PUPPETEER_SKIP_DOWNLOAD=1 npm ci --workspace @proxima/collector --include-workspace-root
  fi

  local artifact
  for artifact in "${sales}" "${orders}"; do
    run_root_logged "cas-import-$(basename "$(dirname "${artifact}")")" \
      env "PROXIMA_RAW_DIR=${ROOT}/raw" node_modules/.bin/tsx tools/cas_import.ts "${artifact}" \
      --retrieved-at "${RETRIEVED_AT}" --source official_wb_statistics
  done
  if [[ "${DRY_RUN}" != true ]]; then
    grep -q "\"content_sha256\": *\"${SALES_SHA}\"" "${ROOT}/logs/cas-import-supplier-sales.log" \
      || fail "cas_import did not return the expected sales sha256"
    grep -q "\"content_sha256\": *\"${ORDERS_SHA}\"" "${ROOT}/logs/cas-import-supplier-orders.log" \
      || fail "cas_import did not return the expected orders sha256"
  fi
  run_root chown -R "${CONTAINER_USER}" "${ROOT}/raw"
  run_root find "${ROOT}/raw" -maxdepth 2 -printf '%M %u:%g %p\n'

  # Fresh database: the tenant row exists in production (runbook §3) but not in the migrations.
  run_sql "INSERT INTO tenants (tenant_id) VALUES ('${TENANT}') ON CONFLICT (tenant_id) DO NOTHING;" -tA

  note "backfill: collector backfill from artifact:${SALES_SHA:0:8}…,${ORDERS_SHA:0:8}… (expect 'backfill committed', run_day 2026-08-31)"
  compose_logged backfill --profile jobs run --rm -e "PROXIMA_GIT_SHA=$(git_sha)" \
    collector npm run backfill -- --tenant "${TENANT}" --source "artifact:${SALES_SHA},${ORDERS_SHA}"
  note "backfill: done"
}

# --- tail: live overlap collect, 2 WB read calls (runbook §3, D35 exception) ----------------

do_tail() {
  require_initialized
  [[ "${LIVE}" == true ]] || fail "tail performs 2 live WB read calls (orders + sales on the statistics token, D35 exception) - pass --live explicitly"
  note "tail: LIVE WB API - 2 read calls (supplier/orders, supplier/sales) with the ${TENANT} statistics token, date-from ${DATE_FROM}; PROXIMA_REHEARSAL_LIVE=1 for this run only"
  local -a base
  mapfile -t base < <(compose_base)
  run_root_logged collect env PROXIMA_REHEARSAL_LIVE=1 "${base[@]}" --profile jobs run --rm \
    -e "PROXIMA_GIT_SHA=$(git_sha)" \
    collector npm run collect -- --tenant "${TENANT}" --date-from "${DATE_FROM}" \
    --statistics-token-file "/run/secrets/${TENANT}_wb_statistics_token"
  note "tail: done (expect 'date_from': '${DATE_FROM}', 'source': 'flag', then kind collect, status SUCCEEDED)"
}

# --- steps: norm -> brief (tools/morning_run.sh modules) ------------------------------------

do_steps() {
  require_initialized
  local module
  for module in proxima_control_plane.norm proxima_control_plane.brief; do
    note "steps: ${module} run --tenant ${TENANT}"
    compose_logged "${module##*.}" --profile jobs run --rm -e "PROXIMA_GIT_SHA=$(git_sha)" \
      control-plane python -m "${module}" run --tenant "${TENANT}"
  done
  note "steps: done"
}

# --- check: runbook §4 numbers and ledger state ---------------------------------------------

readonly W10_SQL="SELECT set_config('proxima.tenant_id','${TENANT}',false);
SELECT 'W10', sum(orders_count), sum(revenue_rub) FROM fact_cabinet_daily_current
  WHERE tenant_id='${TENANT}' AND calendar_day BETWEEN '2026-03-02' AND '2026-03-08';"

# Days before the live tail: one row per day, compared with W35_DAYS_EXPECTED (the 31.08 pair).
readonly W35_PAIR_SQL="SELECT set_config('proxima.tenant_id','${TENANT}',false);
SELECT calendar_day, orders_count, cancelled_count, revenue_rub FROM fact_cabinet_daily_current
  WHERE tenant_id='${TENANT}' AND calendar_day BETWEEN '2026-08-24' AND '2026-08-26' ORDER BY calendar_day;"

# Days rewritten by the tail: facts against the latest observations. Moscow day = the first 10
# characters of the zoneless WB date (services/collector/src/wb/msk-day.ts, AD-7);
# orders_count counts rows with isCancel != true, cancelled_count rows with isCancel = true
# (services/collector/src/facts/cabinet-daily.ts). 'missing' marks a side without a row.
readonly W35_TAIL_SQL="SELECT set_config('proxima.tenant_id','${TENANT}',false);
WITH days AS (
  SELECT generate_series(DATE '${DATE_FROM}', DATE '${W35_LAST_DAY}', INTERVAL '1 day')::date AS calendar_day),
obs AS (
  SELECT substr(payload->>'date', 1, 10)::date AS calendar_day,
         count(*) FILTER (WHERE (payload->>'isCancel')::boolean IS NOT TRUE) AS orders_count,
         count(*) FILTER (WHERE (payload->>'isCancel')::boolean IS TRUE) AS cancelled_count
    FROM stg_wb_orders_latest
   WHERE tenant_id='${TENANT}' AND substr(payload->>'date', 1, 10) BETWEEN '${DATE_FROM}' AND '${W35_LAST_DAY}'
   GROUP BY 1)
SELECT d.calendar_day,
       coalesce(f.orders_count::text, 'missing'), coalesce(f.cancelled_count::text, 'missing'),
       coalesce(o.orders_count::text, 'missing'), coalesce(o.cancelled_count::text, 'missing')
  FROM days d
  LEFT JOIN fact_cabinet_daily_current f ON f.tenant_id='${TENANT}' AND f.calendar_day = d.calendar_day
  LEFT JOIN obs o ON o.calendar_day = d.calendar_day
 ORDER BY d.calendar_day;"

readonly STATE_SQL="SET proxima.tenant_id = '${TENANT}';
SELECT count(*) AS migrations, max(version) AS max_version FROM schema_migrations;
SELECT kind, status, started_at, finished_at FROM collector_runs
  WHERE tenant_id='${TENANT}' ORDER BY started_at;
SELECT last_full_day, collected_at, stale FROM data_status_current WHERE tenant_id='${TENANT}';
SELECT count(*) AS norm_rows, max(evaluation_day) AS last_evaluation_day, count(*) FILTER (WHERE status='ok') AS ok_rows
  FROM norm_daily_current WHERE tenant_id='${TENANT}';
SELECT brief_day, status, run_id FROM brief_current WHERE tenant_id='${TENANT}';"

# One verdict line of the §4 table; returns 1 on mismatch. An empty or 'missing' actual is a
# FAIL even when both sides read the same (no row on either side is not agreement).
check_row() {
  local scope="$1" actual="$2" expected="$3" source="$4"
  local verdict=PASS
  [[ -n "${actual}" && "${actual}" == "${expected}" && "${actual}" != *missing* ]] || verdict=FAIL
  printf '%-12s %-24s %-24s %s\n' "${scope}" "${actual:-<none>}" "${expected}" "${verdict} (${source})"
  [[ "${verdict}" == PASS ]]
}

# The days DATE_FROM..W35_LAST_DAY, one per line (bash side of the generate_series above, so a
# query that returns nothing fails every day instead of passing an empty table).
tail_days() {
  local day="${DATE_FROM}"
  while [[ "${day}" < "${W35_LAST_DAY}" || "${day}" == "${W35_LAST_DAY}" ]]; do
    printf '%s\n' "${day}"
    day="$(date -u -d "${day} + 1 day" +%F)"
  done
}

do_check() {
  require_initialized
  note "check: ledger, data status, norm, brief for ${TENANT}"
  run_sql "${STATE_SQL}" -q
  note "check: runbook §4 - W10 exact (${W10_EXPECTED#W10|}); days 2026-08-24..2026-08-26 = the 31.08 pair; days ${DATE_FROM}..${W35_LAST_DAY} = stg_wb_orders_latest (docs/state/API-FACTS.md, «Что означают эталоны»)"
  if [[ "${DRY_RUN}" == true ]]; then
    run_sql "${W10_SQL}" -tA
    run_sql "${W35_PAIR_SQL}" -tA
    run_sql "${W35_TAIL_SQL}" -tA
    return 0
  fi

  local status=0
  printf '%-12s %-24s %-24s %s\n' scope actual expected verdict

  local w10
  w10="$(sql_capture "${W10_SQL}" | grep '^W10|' || true)"
  check_row W10 "${w10#W10|}" "${W10_EXPECTED#W10|}" "API-FACTS, fixture recompute" || status=1

  local pair_rows expected day actual
  pair_rows="$(sql_capture "${W35_PAIR_SQL}" | grep '^2026-' || true)"
  for expected in "${W35_DAYS_EXPECTED[@]}"; do
    day="${expected%%|*}"
    actual="$(printf '%s\n' "${pair_rows}" | grep "^${day}|" || true)"
    check_row "${day}" "${actual#"${day}|"}" "${expected#*|}" "31.08 pair: orders|cancelled|revenue" || status=1
  done

  local tail_rows row fact_side obs_side
  tail_rows="$(sql_capture "${W35_TAIL_SQL}" | grep '^2026-' || true)"
  while IFS= read -r day; do
    row="$(printf '%s\n' "${tail_rows}" | grep "^${day}|" || true)"
    row="${row#"${day}|"}"
    fact_side="$(printf '%s' "${row}" | cut -d'|' -f1,2)"
    obs_side="$(printf '%s' "${row}" | cut -d'|' -f3,4)"
    check_row "${day}" "${fact_side}" "${obs_side:-<none>}" "fact vs stg_wb_orders_latest: orders|cancelled" || status=1
  done < <(tail_days)

  [[ "${status}" -eq 0 ]] || fail "check: runbook §4 numbers differ (gate not passed)"
  note "check: done"
}

# --- down -----------------------------------------------------------------------------------

do_down() {
  note "down: removing project ${PROJECT} with its volume (production project proxima-ai is not touched)"
  compose --profile jobs down -v --remove-orphans
  # shellcheck disable=SC2016
  run_root sh -c 'docker ps --format "{{.Names}}" | grep proxima'
  note "down: done. The root directory is left in place on purpose - remove it yourself when finished:"
  note "  ${SUDO[*]}${SUDO[*]:+ }rm -rf ${ROOT}"
  note "  images: ${SUDO[*]}${SUDO[*]:+ }docker image ls '${PROJECT}-*'"
}

# --- dispatch -------------------------------------------------------------------------------

case "${SUBCOMMAND}" in
  init) do_init ;;
  up) do_up ;;
  backfill) do_backfill ;;
  tail) do_tail ;;
  steps) do_steps ;;
  check) do_check ;;
  down) do_down ;;
  all)
    do_up
    do_backfill
    if [[ "${LIVE}" == true ]]; then
      do_tail
    else
      note "all: tail skipped (no --live) - the live overlap collect is opt-in, 2 WB read calls (D35)"
    fi
    do_steps
    do_check
    ;;
  *) fail "unknown subcommand: ${SUBCOMMAND}" ;;
esac
