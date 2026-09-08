#!/usr/bin/env bash
# Runtime LOGIN roles, the proxima_test database and the agent sandbox role
# (AD-11 / AD-12). Runs OUTSIDE the migration ledger, strictly after the
# migrations, under a role allowed to create roles and databases (VPS:
# `docker compose exec -T postgres psql`; local harness: the disposable PG16
# cluster superuser). Idempotent: two consecutive runs both succeed and the
# second one changes nothing.
#
# Usage:
#   provision-runtime-roles.sh --psql <psql> --secrets-dir <dir>
#                             [--host H] [--port P] [--database D]
#                             [--test-database T] [--admin-user U]
#
# Secrets contract (generated on first run, never printed, never in git):
#   <secrets-dir>/{proxima_collector,proxima_norm,proxima_webapp,
#                  proxima_janitor,proxima_sandbox}_password
# URI files (Conventions table of the architecture spine):
#   <secrets-dir>/{proxima_collector,proxima_norm,proxima_webapp,
#                  proxima_janitor,proxima_sandbox}_uri
# Ownership (root only): job secrets 1010:1010 0600 (AD-6/AD-11/AD-15, uid of
# the collector/control-plane images); proxima_webapp_{password,uri} 1001:1001
# 0600 - the uid of services/webapp/Dockerfile (D35 addendum, Mike 08.09.2026).
#
# NOLOGIN group roles come from migration 011 (Story 1.3). Until it exists the
# LOGIN users are created WITHOUT membership and a warning is printed; a later
# re-run of this script grants the missing memberships. That keeps the script
# correct in both ledger states.
#
# Passwords never travel as plaintext SQL: the SCRAM-SHA-256 verifier is
# computed locally (python3 stdlib) and sent instead, so an ALTER ROLE with
# log_statement=all or an erroneous statement cannot leak the secret. The
# plaintext stays only in the 0600 password/URI files services read.
#
# bash-3.2 (macOS /bin/bash) compatible: no extglob, no `|&`, no mapfile,
# no associative arrays; indexed arrays only.
set -euo pipefail

PSQL_PATH=""
SECRETS_DIR=""
HOST="127.0.0.1"
PORT="5432"
DATABASE="proxima"
TEST_DATABASE="proxima_test"
ADMIN_USER="postgres"

usage() {
  sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --psql) PSQL_PATH="${2:?--psql requires a value}" ; shift 2 ;;
    --secrets-dir) SECRETS_DIR="${2:?--secrets-dir requires a value}" ; shift 2 ;;
    --host) HOST="${2:?--host requires a value}" ; shift 2 ;;
    --port) PORT="${2:?--port requires a value}" ; shift 2 ;;
    --database) DATABASE="${2:?--database requires a value}" ; shift 2 ;;
    --test-database) TEST_DATABASE="${2:?--test-database requires a value}" ; shift 2 ;;
    --admin-user) ADMIN_USER="${2:?--admin-user requires a value}" ; shift 2 ;;
    -h | --help) usage ;;
    *) echo "provision-runtime-roles: unknown argument: $1" >&2 ; usage ;;
  esac
done

fail() {
  echo "provision-runtime-roles: $*" >&2
  exit 1
}

[[ -n "${PSQL_PATH}" && -x "${PSQL_PATH}" ]] || fail "--psql must point to an executable psql"
[[ -n "${SECRETS_DIR}" ]] || fail "--secrets-dir is required"
[[ "${DATABASE}" != "${TEST_DATABASE}" ]] || fail "test database must differ from the main database"
for name in "${DATABASE}" "${TEST_DATABASE}"; do
  [[ "${name}" =~ ^[a-z_][a-z0-9_]*$ ]] || fail "database name must be a plain identifier: ${name}"
done
case "${HOST}" in *[[:space:]]* | "") fail "--host is malformed" ;; esac
[[ "${PORT}" =~ ^[0-9]+$ ]] || fail "--port must be numeric"
command -v python3 >/dev/null 2>&1 || fail "python3 is required to build the SCRAM verifier"

mkdir -p "${SECRETS_DIR}"
chmod 0700 "${SECRETS_DIR}"

# Passwords stay URL-safe by construction so the URI files never need
# percent-encoding; a hand-written secret from the VPS secrets dir is still
# accepted (only SQL-escaped, never echoed).
generate_password() {
  LC_ALL=C head -c 4096 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9_-' | LC_ALL=C head -c 40
}

read_or_create_password() {
  local role="$1"
  local file="${SECRETS_DIR}/${role}_password"
  if [[ ! -s "${file}" ]]; then
    printf '%s\n' "$(generate_password)" > "${file}"
  fi
  chmod 0600 "${file}"
  local value
  value="$(tr -d '\r\n' < "${file}")"
  [[ -n "${value}" ]] || fail "password file is empty: ${file}"
  printf '%s' "${value}"
}

sql_literal() {
  printf '%s' "$1" | sed "s/'/''/g"
}

# Builds the PostgreSQL SCRAM-SHA-256 secret for a password using only the
# python3 standard library (same construction as scram_build_secret()).
# Verified against PG16: the third field is the STORED key (SHA-256 of the
# client key), and PG16 stores a well-formed verifier verbatim instead of
# re-hashing the input.
scram_verifier() {
  # Pass the plaintext through stdin, not an environment variable or argv:
  # another local process must not be able to discover it via ps(1).
  printf '%s' "$1" | python3 -c '
import base64
import hashlib
import hmac
import os
import sys

password = sys.stdin.buffer.read()
salt = os.urandom(16)
iterations = 4096
salted = hashlib.pbkdf2_hmac("sha256", password, salt, iterations, 32)
client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
stored_key = hashlib.sha256(client_key).digest()
server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
b64 = lambda raw: base64.b64encode(raw).decode("ascii")
print(f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}")
'
}

uri_encode_component() {
  printf '%s' "$1" | sed -e 's/%/%25/g' -e 's/:/%3A/g' -e 's/@/%40/g' -e 's|/|%2F|g'
}

COLLECTOR_PASSWORD="$(read_or_create_password proxima_collector)"
NORM_PASSWORD="$(read_or_create_password proxima_norm)"
WEBAPP_PASSWORD="$(read_or_create_password proxima_webapp)"
JANITOR_PASSWORD="$(read_or_create_password proxima_janitor)"
SANDBOX_PASSWORD="$(read_or_create_password proxima_sandbox)"

COLLECTOR_VERIFIER="$(scram_verifier "${COLLECTOR_PASSWORD}")"
NORM_VERIFIER="$(scram_verifier "${NORM_PASSWORD}")"
WEBAPP_VERIFIER="$(scram_verifier "${WEBAPP_PASSWORD}")"
JANITOR_VERIFIER="$(scram_verifier "${JANITOR_PASSWORD}")"
SANDBOX_VERIFIER="$(scram_verifier "${SANDBOX_PASSWORD}")"
# Pattern kept in a variable: bash 3.2 treats a quoted `[[ =~ ]]` right-hand
# side as a literal string, the variable form behaves the same everywhere.
SCRAM_RE='^SCRAM-SHA-256\$4096:[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+$'
for verifier in "${COLLECTOR_VERIFIER}" "${NORM_VERIFIER}" "${WEBAPP_VERIFIER}" \
                "${JANITOR_VERIFIER}" "${SANDBOX_VERIFIER}"; do
  [[ "${verifier}" =~ ${SCRAM_RE} ]] || fail "generated SCRAM verifier is malformed"
done

PSQL_ARGS=(--no-psqlrc --quiet --set ON_ERROR_STOP=1
           --host "${HOST}" --port "${PORT}" --username "${ADMIN_USER}")

run_sql() {
  local database="$1"
  shift
  printf '%s\n' "$*" | "${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${database}"
}

write_uri() {
  local role="$1" database="$2" password="$3"
  local file="${SECRETS_DIR}/${role}_uri"
  printf 'postgresql://%s:%s@%s:%s/%s\n' \
    "${role}" "$(uri_encode_component "${password}")" "${HOST}" "${PORT}" "${database}" > "${file}"
  chmod 0600 "${file}"
}

# --- ledger group roles -----------------------------------------------------
# Membership needs migration 011 (Story 1.3). One query, then shell matching.
EXISTING_GROUPS="$("${PSQL_PATH}" "${PSQL_ARGS[@]}" --dbname "${DATABASE}" \
  --tuples-only --no-align --record-separator ' ' \
  --command "SELECT rolname FROM pg_roles WHERE rolname IN (
               'proxima_job_collector','proxima_job_norm','proxima_webapp_readonly',
               'proxima_run_janitor','proxima_source_publisher')")"

group_exists() {
  case " ${EXISTING_GROUPS} " in
    *" $1 "* ) return 0 ;;
    * ) return 1 ;;
  esac
}

MEMBERSHIP_SQL=""
MISSING_REPORT=""

add_membership() {
  local user="$1" group="$2"
  if group_exists "${group}"; then
    MEMBERSHIP_SQL="${MEMBERSHIP_SQL}
GRANT ${group} TO ${user};"
  else
    MISSING_REPORT="${MISSING_REPORT}
  ${user} not granted ${group}"
  fi
}

# --- main database ----------------------------------------------------------
# Verifiers, not plaintext: `ALTER ROLE ... PASSWORD 'SCRAM-SHA-256$...'` is
# stored verbatim by PG16, so the wire and the server log never see the
# password itself.
MAIN_SQL="SET password_encryption = 'scram-sha-256';

SELECT format('CREATE ROLE %I', 'proxima_collector')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'proxima_collector') \gexec
ALTER ROLE proxima_collector LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT PASSWORD '$(sql_literal "${COLLECTOR_VERIFIER}")';

SELECT format('CREATE ROLE %I', 'proxima_norm')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'proxima_norm') \gexec
ALTER ROLE proxima_norm LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT PASSWORD '$(sql_literal "${NORM_VERIFIER}")';

SELECT format('CREATE ROLE %I', 'proxima_webapp')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'proxima_webapp') \gexec
ALTER ROLE proxima_webapp LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT PASSWORD '$(sql_literal "${WEBAPP_VERIFIER}")';

SELECT format('CREATE ROLE %I', 'proxima_janitor')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'proxima_janitor') \gexec
ALTER ROLE proxima_janitor LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT PASSWORD '$(sql_literal "${JANITOR_VERIFIER}")';

SELECT format('CREATE ROLE %I', 'proxima_sandbox')
  WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'proxima_sandbox') \gexec
ALTER ROLE proxima_sandbox LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS INHERIT PASSWORD '$(sql_literal "${SANDBOX_VERIFIER}")';

-- AD-12: only explicit grantees reach the main database. PUBLIC loses CONNECT
-- everywhere it is not required, and proxima_sandbox is deliberately not
-- granted CONNECT anywhere except the test copy.
REVOKE CONNECT ON DATABASE ${DATABASE} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${DATABASE} TO proxima_collector, proxima_norm, proxima_webapp, proxima_janitor;
REVOKE CONNECT ON DATABASE postgres, template0, template1 FROM PUBLIC;
REVOKE CONNECT ON DATABASE postgres, template0, template1 FROM proxima_sandbox;
GRANT USAGE ON SCHEMA public TO proxima_collector, proxima_norm, proxima_webapp, proxima_janitor;

-- AD-11: the janitor only ever deletes runs, so its DELETE grant targets
-- exactly the tables that carry a run_id. Today that set is empty (migration
-- 011 lands in Story 1.3); a re-run of this script after 011 picks the new
-- tables up automatically. A blanket grant over the whole schema is
-- forbidden: it would hand DELETE on schema_migrations and tenants to the
-- janitor and let it drop the migration ledger.
SELECT format('GRANT DELETE ON TABLE %I.%I TO proxima_janitor', n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'r' AND n.nspname = 'public'
    AND EXISTS (SELECT 1 FROM pg_attribute a
                WHERE a.attrelid = c.oid AND a.attname = 'run_id' AND NOT a.attisdropped)
  ORDER BY c.relname \gexec"

add_membership proxima_collector proxima_job_collector
add_membership proxima_collector proxima_source_publisher
add_membership proxima_norm proxima_job_norm
add_membership proxima_webapp proxima_webapp_readonly
add_membership proxima_janitor proxima_run_janitor

echo "provision-runtime-roles: login roles and grants on ${HOST}:${PORT}/${DATABASE}"
run_sql "${DATABASE}" "${MAIN_SQL}${MEMBERSHIP_SQL}"

echo "provision-runtime-roles: ensuring database ${TEST_DATABASE}"
run_sql "${DATABASE}" "SELECT format('CREATE DATABASE %I', '${TEST_DATABASE}')
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${TEST_DATABASE}') \gexec"

TEST_SQL="REVOKE CONNECT ON DATABASE ${TEST_DATABASE} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${TEST_DATABASE} TO proxima_sandbox, proxima_collector, proxima_norm, proxima_webapp, proxima_janitor;
GRANT ALL ON SCHEMA public TO proxima_sandbox;
GRANT ALL ON ALL TABLES IN SCHEMA public TO proxima_sandbox;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO proxima_sandbox;"

run_sql "${TEST_DATABASE}" "${TEST_SQL}"

write_uri proxima_collector "${DATABASE}" "${COLLECTOR_PASSWORD}"
write_uri proxima_norm "${DATABASE}" "${NORM_PASSWORD}"
write_uri proxima_webapp "${DATABASE}" "${WEBAPP_PASSWORD}"
write_uri proxima_janitor "${DATABASE}" "${JANITOR_PASSWORD}"
write_uri proxima_sandbox "${TEST_DATABASE}" "${SANDBOX_PASSWORD}"

# AD-11: the secrets dir is owned by 1010:1010 (the job container user) on the
# VPS. Only root can chown, so a non-root caller (the local harness) keeps the
# files owned by the invoking user and must arrange ownership out of band.
#
# Exception (D35 addendum, Mike 08.09.2026, found on the rehearsal stand): the
# webapp image runs as uid/gid 1001, not 1010 (services/webapp/Dockerfile:
# `useradd --system --uid 1001 ... webapp`, kept on purpose - the public
# process gets its own uid). A 1010:1010 0600 file is unreadable for it and
# WEBAPP_DATA_MODE=postgres fails with "файл WEBAPP_DATA_DATABASE_URI_FILE не
# читается", so proxima_webapp_password / proxima_webapp_uri are owned by
# 1001:1001. Every job secret (collector, norm, janitor, sandbox) stays
# 1010:1010. Ownership is re-asserted on every run: a re-run repairs a wrong
# owner instead of keeping it.
SECRETS_OWNER="1010:1010"
WEBAPP_SECRETS_OWNER="1001:1001"
if [[ "$(id -u)" -eq 0 ]]; then
  chown "${SECRETS_OWNER}" "${SECRETS_DIR}"
  chown "${SECRETS_OWNER}" "${SECRETS_DIR}"/proxima_collector_* \
    "${SECRETS_DIR}"/proxima_norm_* \
    "${SECRETS_DIR}"/proxima_janitor_* "${SECRETS_DIR}"/proxima_sandbox_*
  chown "${WEBAPP_SECRETS_OWNER}" "${SECRETS_DIR}"/proxima_webapp_password \
    "${SECRETS_DIR}"/proxima_webapp_uri
  echo "provision-runtime-roles: secrets owned by ${SECRETS_OWNER}; proxima_webapp_password, proxima_webapp_uri owned by ${WEBAPP_SECRETS_OWNER} (webapp image uid)"
else
  echo "provision-runtime-roles: WARNING not running as root, secret files left owned by $(id -un); run as root (or chown ${SECRETS_OWNER}, proxima_webapp_* ${WEBAPP_SECRETS_OWNER}) on the VPS" >&2
fi

if [[ -n "${MISSING_REPORT}" ]]; then
  echo "provision-runtime-roles: WARNING ledger group roles missing, memberships deferred (re-run after migration 011):${MISSING_REPORT}" >&2
else
  echo "provision-runtime-roles: memberships granted for every ledger group role"
fi
echo "provision-runtime-roles: ok (5 login roles, database ${TEST_DATABASE}, URI files under ${SECRETS_DIR}; no secret value printed)"
