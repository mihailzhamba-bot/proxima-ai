#!/usr/bin/env bash
set -euo pipefail

readonly ADMIN_USER="proxima-admin"
readonly MONITOR_USER="proxima-monitor"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../.." && pwd -P)"
readonly REPOSITORY_DIR="/srv/proxima-ai/repo"
repository_ready=false

fail() {
  printf '%s\n' "bootstrap-vps: $*" >&2
  exit 1
}

require_root() {
  [[ "$(id -u)" -eq 0 ]] || fail "run as root via sudo"
}

validate_admin_key() {
  local key_file="$1"
  local key_line
  local key_lines=0

  [[ -r "${key_file}" ]] || fail "PROXIMA_ADMIN_PUBLIC_KEY_FILE is not readable"
  while IFS= read -r key_line || [[ -n "${key_line}" ]]; do
    [[ -z "${key_line}" ]] && continue
    case "${key_line}" in
      ssh-ed25519\ *|sk-ssh-ed25519\ *|ecdsa-sha2-nistp*\ *|ssh-rsa\ *) ;;
      *) fail "admin key must be one supported public SSH key" ;;
    esac
    key_lines=$((key_lines + 1))
  done < "${key_file}"

  [[ "${key_lines}" -eq 1 ]] || fail "admin key file must contain exactly one public SSH key"
}

ensure_user() {
  local user="$1"
  local shell="$2"
  if ! id -u "${user}" >/dev/null 2>&1; then
    useradd --create-home --shell "${shell}" "${user}"
  fi
}

admin_git() {
  id -u "${ADMIN_USER}" >/dev/null 2>&1 || fail "existing repository owner does not exist"
  runuser --user "${ADMIN_USER}" -- git -C "${REPOSITORY_DIR}" "$@"
}

preflight_repository() {
  if [[ -e "${REPOSITORY_DIR}" && ! -d "${REPOSITORY_DIR}" ]]; then
    fail "repository path exists but is not a directory"
  fi
  if [[ -e "${REPOSITORY_DIR}/.git" ]]; then
    admin_git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "existing repository path is not a valid Git checkout"
    admin_git diff --quiet || fail "existing repository checkout has unstaged changes"
    admin_git diff --cached --quiet || fail "existing repository checkout has staged changes"
    repository_ready=true
    return
  fi

  if [[ -e "${REPOSITORY_DIR}" ]] && [[ -n "$(find "${REPOSITORY_DIR}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    fail "repository directory exists but is not an empty bootstrap target"
  fi
}

install_repository() {
  if [[ "${repository_ready}" == true ]]; then
    return
  fi

  git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "bootstrap must run from a Git checkout"
  git -C "${ROOT_DIR}" diff --quiet || fail "bootstrap checkout has unstaged changes"
  git -C "${ROOT_DIR}" diff --cached --quiet || fail "bootstrap checkout has staged changes"

  git clone --no-hardlinks --origin bootstrap-source "${ROOT_DIR}" "${REPOSITORY_DIR}"
  git -C "${REPOSITORY_DIR}" remote remove bootstrap-source
  chown --recursive "${ADMIN_USER}:${ADMIN_USER}" "${REPOSITORY_DIR}"
}

require_root
[[ "${PROXIMA_SECURITY_GROUP_VERIFIED:-}" == "yes" ]] || fail "configure Selectel security group for TCP/22 only, then set PROXIMA_SECURITY_GROUP_VERIFIED=yes"
[[ -n "${PROXIMA_ADMIN_PUBLIC_KEY_FILE:-}" ]] || fail "set PROXIMA_ADMIN_PUBLIC_KEY_FILE to a public-key file"
validate_admin_key "${PROXIMA_ADMIN_PUBLIC_KEY_FILE}"
command -v git >/dev/null 2>&1 || fail "bootstrap checkout requires Git to be installed"
preflight_repository

export DEBIAN_FRONTEND=noninteractive
apt-get update
if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
  compose_package="docker-compose-v2"
elif apt-cache show docker-compose-plugin >/dev/null 2>&1; then
  compose_package="docker-compose-plugin"
else
  fail "no Docker Compose v2 package is available from the configured Ubuntu repositories"
fi
apt-get install --yes ca-certificates curl "${compose_package}" docker.io git openssh-server python3 ufw

ensure_user "${ADMIN_USER}" "/bin/bash"
usermod --append --groups sudo "${ADMIN_USER}"
ensure_user "${MONITOR_USER}" "/usr/sbin/nologin"

install --directory --mode 0700 --owner "${ADMIN_USER}" --group "${ADMIN_USER}" "/home/${ADMIN_USER}/.ssh"
install --mode 0600 --owner "${ADMIN_USER}" --group "${ADMIN_USER}" "${PROXIMA_ADMIN_PUBLIC_KEY_FILE}" "/home/${ADMIN_USER}/.ssh/authorized_keys"

install --directory --mode 0750 --owner "${ADMIN_USER}" --group "${ADMIN_USER}" "${REPOSITORY_DIR}"
install --directory --mode 0750 --owner "${ADMIN_USER}" --group "${ADMIN_USER}" /srv/proxima-ai/data
install --directory --mode 0750 --owner root --group "${MONITOR_USER}" /etc/proxima-ai
install --directory --mode 0750 --owner root --group "${MONITOR_USER}" /etc/proxima-ai/secrets
install --directory --mode 0700 --owner "${MONITOR_USER}" --group "${MONITOR_USER}" /var/lib/proxima-ai-monitor
install --mode 0640 --owner root --group "${MONITOR_USER}" "${ROOT_DIR}/infra/vps-contract.json" /etc/proxima-ai/vps-contract.json

install --mode 0644 "${SCRIPT_DIR}/60-proxima-ai.conf" /etc/ssh/sshd_config.d/60-proxima-ai.conf
/usr/sbin/sshd -t
systemctl reload ssh

ufw allow 22/tcp
ufw default deny incoming
ufw default allow outgoing
ufw --force enable

install_repository

install --directory --mode 0755 /usr/local/lib/proxima-ai
install --mode 0755 "${ROOT_DIR}/infra/monitoring/host_monitor.py" /usr/local/lib/proxima-ai/host_monitor.py
install --mode 0640 --owner root --group "${MONITOR_USER}" "${ROOT_DIR}/infra/monitoring/monitor.env.example" /etc/proxima-ai/monitor.env
install --mode 0644 "${ROOT_DIR}/infra/monitoring/proxima-host-monitor.service" /etc/systemd/system/proxima-host-monitor.service
install --mode 0644 "${ROOT_DIR}/infra/monitoring/proxima-host-monitor.timer" /etc/systemd/system/proxima-host-monitor.timer
systemctl daemon-reload
systemctl enable --now docker
docker compose version >/dev/null

printf '%s\n' "bootstrap-vps: complete. Do not enable proxima-host-monitor.timer before Telegram secret files and a delivery test are ready."
