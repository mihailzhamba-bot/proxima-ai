#!/usr/bin/env bash
set -euo pipefail

readonly NODE_MAJOR="22"
readonly REPOSITORY_DIR="/srv/proxima-ai/repo"
readonly SIGNAL_CONFIG_DIR="/etc/proxima-ai/business-signal"
readonly SECRETS_DIR="/etc/proxima-ai/secrets"
readonly SIGNAL_RAW_DIR="/srv/proxima-ai/data/business-signal"

fail() {
  printf '%s\n' "prepare-business-signal-runtime: $*" >&2
  exit 1
}

[[ "$(id -u)" -eq 0 ]] || fail "run as root via sudo"
[[ -d "${REPOSITORY_DIR}/.git" ]] || fail "bootstrap repository is missing"
id -u proxima-admin >/dev/null 2>&1 || fail "proxima-admin user is missing"
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v gpg >/dev/null 2>&1 || {
  apt-get update
  apt-get install --yes gnupg
}

if ! command -v node >/dev/null 2>&1 || [[ "$(node --version)" != v${NODE_MAJOR}.* ]]; then
  install --directory --mode 0755 /etc/apt/keyrings
  curl --fail --silent --show-error --location https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor --yes --output /etc/apt/keyrings/nodesource.gpg
  chmod 0644 /etc/apt/keyrings/nodesource.gpg
  printf '%s\n' "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update
  apt-get install --yes nodejs
fi
[[ "$(node --version)" == v${NODE_MAJOR}.* ]] || fail "Node ${NODE_MAJOR}.x is required"

install --directory --mode 0700 --owner proxima-admin --group proxima-admin "${SIGNAL_CONFIG_DIR}"
install --directory --mode 0700 --owner proxima-admin --group proxima-admin "${SIGNAL_RAW_DIR}"
install --directory --mode 0750 --owner root --group proxima-monitor "${SECRETS_DIR}"

for secret in postgres_user postgres_password; do
  [[ -r "${SECRETS_DIR}/${secret}" ]] || fail "${SECRETS_DIR}/${secret} is missing"
done
python3 - "${SECRETS_DIR}/postgres_user" "${SECRETS_DIR}/postgres_password" <<'PY' | install --mode 0600 --owner proxima-admin --group proxima-admin /dev/stdin "${SECRETS_DIR}/postgres_url"
import pathlib
import sys
import urllib.parse

user = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
password = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").strip()
print(f"postgresql://{urllib.parse.quote(user, safe='')}:{urllib.parse.quote(password, safe='')}@127.0.0.1:5432/proxima")
PY

runuser --user proxima-admin -- env PUPPETEER_SKIP_DOWNLOAD=true npm --prefix "${REPOSITORY_DIR}" ci
runuser --user proxima-admin -- npm --prefix "${REPOSITORY_DIR}" run build

printf '%s\n' "prepare-business-signal-runtime: Node ${NODE_MAJOR}, private directories and collector build are ready. Add private source files before dry run."
