#!/usr/bin/env bash
set -euo pipefail

readonly REPOSITORY_DIR="/srv/proxima-ai/repo"
readonly SECRETS_DIR="/etc/proxima-ai/secrets"
readonly PROBE_VENV="/srv/proxima-ai/wb-probe-venv"
readonly ENV_FILE="${REPOSITORY_DIR}/.env"

fail() {
  printf '%s\n' "prepare-day1-runtime: $*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root via sudo"
[[ -d "${REPOSITORY_DIR}/.git" ]] || fail "bootstrap repository is missing"
getent group proxima-monitor >/dev/null 2>&1 || fail "proxima-monitor group is missing"
command -v docker >/dev/null 2>&1 || fail "Docker is not installed"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not installed"
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed"

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("prepare-day1-runtime: Python 3.11+ is required")
PY

usermod --append --groups proxima-monitor proxima-admin
install --directory --mode 0750 --owner root --group proxima-monitor "${SECRETS_DIR}"
install --directory --mode 0750 --owner proxima-admin --group proxima-admin /srv/proxima-ai/data/day1-wb-api
install --directory --mode 0700 --owner proxima-admin --group proxima-admin /srv/proxima-ai/data/wb-analytics-spool

if [[ ! -e "${SECRETS_DIR}/postgres_user" ]]; then
  printf '%s\n' "proxima" | install --mode 0600 /dev/stdin "${SECRETS_DIR}/postgres_user"
fi
if [[ ! -e "${SECRETS_DIR}/postgres_password" ]]; then
  python3 - <<'PY' | install --mode 0600 /dev/stdin /etc/proxima-ai/secrets/postgres_password
import secrets
print(secrets.token_urlsafe(48))
PY
fi
chown root:proxima-monitor "${SECRETS_DIR}/postgres_user" "${SECRETS_DIR}/postgres_password"
chmod 0640 "${SECRETS_DIR}/postgres_user" "${SECRETS_DIR}/postgres_password"

install --mode 0600 /dev/null "${ENV_FILE}"
printf '%s\n' \
  "WB_STATISTICS_TOKEN_FILE=${SECRETS_DIR}/wb_statistics_token" \
  "PROXIMA_RAW_DIR=/srv/proxima-ai/data/day1-wb-api" \
  "WB_ANALYTICS_TOKEN_FILE=${SECRETS_DIR}/wb_analytics_token" \
  "PROXIMA_SPOOL_DIR=/srv/proxima-ai/data/wb-analytics-spool" \
  "POSTGRES_USER_FILE=${SECRETS_DIR}/postgres_user" \
  "POSTGRES_PASSWORD_FILE=${SECRETS_DIR}/postgres_password" \
  "POSTGRES_HOST=127.0.0.1" \
  "POSTGRES_PORT=5432" \
  "POSTGRES_DB=proxima" \
  > "${ENV_FILE}"
chown proxima-admin:proxima-admin "${ENV_FILE}"

if [[ ! -x "${PROBE_VENV}/bin/python" ]]; then
  python3 -m venv "${PROBE_VENV}"
fi
"${PROBE_VENV}/bin/python" -m pip install --disable-pip-version-check --requirement "${REPOSITORY_DIR}/tools/wb_api_probe_requirements.txt"

PROXIMA_SECRETS_DIR="${SECRETS_DIR}" docker compose \
  --file "${REPOSITORY_DIR}/infra/compose.yaml" \
  up --detach postgres

for _ in $(seq 1 30); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' proxima-ai-postgres-1 2>/dev/null || true)"
  if [[ "${status}" == "healthy" ]]; then
    runuser --user proxima-admin -- "${PROBE_VENV}/bin/python" "${REPOSITORY_DIR}/tools/apply_migrations.py" --env-file "${ENV_FILE}"
    printf '%s\n' "prepare-day1-runtime: PostgreSQL healthy and migrations current; WB tokens remain required"
    exit 0
  fi
  [[ "${status}" != "unhealthy" ]] || fail "PostgreSQL healthcheck failed"
  sleep 2
done

fail "PostgreSQL did not become healthy within 60 seconds"
