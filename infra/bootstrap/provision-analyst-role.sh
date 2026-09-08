#!/usr/bin/env bash
set -euo pipefail

readonly SECRETS_DIR="/etc/proxima-ai/secrets"
readonly PASSWORD_FILE="${SECRETS_DIR}/proxima_analyst_password"
readonly URI_FILE="${SECRETS_DIR}/proxima_analyst_uri"
readonly CONTAINER="proxima-ai-postgres-1"
readonly ADMIN_ROLE="proxima"
readonly ANALYST_ROLE="proxima_analyst"
readonly DATABASE="proxima"
readonly URI_HOST="127.0.0.1"
readonly URI_PORT="5433"

fail() {
  printf '%s\n' "provision-analyst-role: $*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root via sudo"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed"
docker inspect "${CONTAINER}" >/dev/null 2>&1 || fail "PostgreSQL container is missing"

if [[ ! -d "${SECRETS_DIR}" ]]; then
  install --directory --mode 0750 --owner root --group root "${SECRETS_DIR}"
fi
if [[ ! -s "${PASSWORD_FILE}" ]]; then
  python3 - <<'PY' | install --mode 0600 --owner root --group root /dev/stdin /etc/proxima-ai/secrets/proxima_analyst_password
import secrets

print(secrets.token_urlsafe(48))
PY
fi
chown root:root "${PASSWORD_FILE}"
chmod 0600 "${PASSWORD_FILE}"

python3 - "${PASSWORD_FILE}" <<'PY' | docker exec --interactive "${CONTAINER}" \
  psql --username "${ADMIN_ROLE}" --dbname "${DATABASE}" --no-psqlrc --quiet --set ON_ERROR_STOP=1
from pathlib import Path
import sys


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


password = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
if not password:
    raise SystemExit("analyst password file is empty")

print(
    f"""
SET password_encryption = 'scram-sha-256';
DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'proxima_analyst') THEN
    CREATE ROLE proxima_analyst;
  END IF;
END
$role$;

ALTER ROLE proxima_analyst
  LOGIN
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT
  NOREPLICATION
  NOBYPASSRLS
  PASSWORD {sql_literal(password)};
ALTER ROLE proxima_analyst SET default_transaction_read_only = on;
ALTER ROLE proxima_analyst SET statement_timeout = '30s';
ALTER ROLE proxima_analyst SET lock_timeout = '5s';
ALTER ROLE proxima_analyst SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE proxima_analyst SET search_path = public, pg_catalog;

DO $memberships$
DECLARE group_role name;
BEGIN
  FOR group_role IN
    SELECT parent.rolname
      FROM pg_auth_members membership
      JOIN pg_roles parent ON parent.oid = membership.roleid
      JOIN pg_roles member ON member.oid = membership.member
     WHERE member.rolname = 'proxima_analyst'
  LOOP
    EXECUTE format('REVOKE %I FROM proxima_analyst', group_role);
  END LOOP;
END
$memberships$;

REVOKE ALL PRIVILEGES ON DATABASE proxima FROM proxima_analyst;
GRANT CONNECT ON DATABASE proxima TO proxima_analyst;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM proxima_analyst;
GRANT USAGE ON SCHEMA public TO proxima_analyst;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM proxima_analyst;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM proxima_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO proxima_analyst;
ALTER DEFAULT PRIVILEGES FOR ROLE proxima IN SCHEMA public
  GRANT SELECT ON TABLES TO proxima_analyst;
"""
)
PY

python3 - "${PASSWORD_FILE}" "${ANALYST_ROLE}" "${URI_HOST}" "${URI_PORT}" "${DATABASE}" <<'PY' \
  | install --mode 0600 --owner root --group root /dev/stdin /etc/proxima-ai/secrets/proxima_analyst_uri
from pathlib import Path
import sys
from urllib.parse import quote

password_file, role, host, port, database = sys.argv[1:]
password = Path(password_file).read_text(encoding="utf-8").strip()
print(f"postgresql://{role}:{quote(password, safe='')}@{host}:{port}/{database}")
PY
chown root:root "${URI_FILE}"
chmod 0600 "${URI_FILE}"

printf '%s\n' "provision-analyst-role: password file: ${PASSWORD_FILE}"
printf '%s\n' "provision-analyst-role: URI file: ${URI_FILE}"
