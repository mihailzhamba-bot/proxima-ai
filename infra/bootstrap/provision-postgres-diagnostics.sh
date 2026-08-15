#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY_DIR="/srv/proxima-ai/repo"
readonly SECRETS_DIR="/etc/proxima-ai/secrets"
readonly PASSWORD_FILE="${SECRETS_DIR}/postgres_diagnostics_password"
readonly CONTAINER="proxima-ai-postgres-1"
readonly ADMIN_ROLE="proxima"
readonly DIAGNOSTIC_ROLE="proxima_diagnostics"
readonly WRAPPER_SOURCE="${REPOSITORY_DIR}/infra/bootstrap/proxima-psql-readonly"
readonly WRAPPER_TARGET="/usr/local/sbin/proxima-psql-readonly"

fail() {
  printf '%s\n' "provision-postgres-diagnostics: $*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root via sudo"
[[ -d "${REPOSITORY_DIR}/.git" ]] || fail "bootstrap repository is missing"
[[ -f "${WRAPPER_SOURCE}" ]] || fail "read-only psql wrapper is missing"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed"
docker inspect "${CONTAINER}" >/dev/null 2>&1 || fail "PostgreSQL container is missing"

install --directory --mode 0750 --owner root --group proxima-monitor "${SECRETS_DIR}"
if [[ ! -e "${PASSWORD_FILE}" ]]; then
  python3 - <<'PY' | install --mode 0600 --owner root --group root /dev/stdin /etc/proxima-ai/secrets/postgres_diagnostics_password
import secrets

print(secrets.token_urlsafe(48))
PY
fi
chown root:root "${PASSWORD_FILE}"
chmod 0600 "${PASSWORD_FILE}"

python3 - "${PASSWORD_FILE}" <<'PY' | docker exec --interactive "${CONTAINER}" \
  psql --username "${ADMIN_ROLE}" --dbname proxima --no-psqlrc --quiet --set ON_ERROR_STOP=1
from pathlib import Path
import sys


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


password = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
if not password:
    raise SystemExit("diagnostic password file is empty")

print(
    f"""
SET password_encryption = 'scram-sha-256';
DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'proxima_diagnostics') THEN
    CREATE ROLE proxima_diagnostics;
  END IF;
END
$role$;

ALTER ROLE proxima_diagnostics
  LOGIN
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT
  NOREPLICATION
  NOBYPASSRLS
  PASSWORD {sql_literal(password)};
ALTER ROLE proxima_diagnostics SET default_transaction_read_only = on;
ALTER ROLE proxima_diagnostics SET statement_timeout = '30s';
ALTER ROLE proxima_diagnostics SET lock_timeout = '5s';
ALTER ROLE proxima_diagnostics SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE proxima_diagnostics SET search_path = public, pg_catalog;

REVOKE ALL PRIVILEGES ON DATABASE proxima FROM proxima_diagnostics;
GRANT CONNECT ON DATABASE proxima TO proxima_diagnostics;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM proxima_diagnostics;
GRANT USAGE ON SCHEMA public TO proxima_diagnostics;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM proxima_diagnostics;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM proxima_diagnostics;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO proxima_diagnostics;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO proxima_diagnostics;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE proxima IN SCHEMA public
  GRANT SELECT ON TABLES TO proxima_diagnostics;
ALTER DEFAULT PRIVILEGES FOR ROLE proxima IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO proxima_diagnostics;
ALTER DEFAULT PRIVILEGES FOR ROLE proxima IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
"""
)
PY

install --mode 0755 --owner root --group root "${WRAPPER_SOURCE}" "${WRAPPER_TARGET}"
printf '%s\n' "SELECT current_user, current_database(), current_setting('default_transaction_read_only');" \
  | "${WRAPPER_TARGET}" >/dev/null

printf '%s\n' "provision-postgres-diagnostics: role and wrapper ready; secret value was not printed"
