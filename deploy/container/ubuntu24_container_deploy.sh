#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_HOST="${PUBLIC_HOST:-${1:-}}"
BASIC_AUTH_USER="${BASIC_AUTH_USER:-${2:-admin}}"
BASIC_AUTH_PASSWORD="${BASIC_AUTH_PASSWORD:-${3:-}}"
ACME_EMAIL="${ACME_EMAIL:-${4:-admin@example.com}}"
FORCE_REGENERATE_ENV="${FORCE_REGENERATE_ENV:-0}"

if [[ -z "${PUBLIC_HOST}" ]]; then
  cat >&2 <<'EOF'
Usage:
  sudo PUBLIC_HOST=astell.example.com BASIC_AUTH_USER=admin BASIC_AUTH_PASSWORD='StrongPassword' ACME_EMAIL=it@example.com ./deploy/container/ubuntu24_container_deploy.sh

Or:
  sudo ./deploy/container/ubuntu24_container_deploy.sh astell.example.com admin 'StrongPassword' it@example.com

Before running, point the domain A record to this server and open ports 80/443.
EOF
  exit 1
fi

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return
  fi

  log "Installing Docker Engine and Compose plugin"
  apt-get update
  apt-get install -y ca-certificates curl gnupg openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

install_docker

log "Preparing Basic Auth configuration"
cd "${SCRIPT_DIR}"
if [[ ! -f .env || "${FORCE_REGENERATE_ENV}" == "1" ]]; then
  PUBLIC_HOST="${PUBLIC_HOST}" \
  BASIC_AUTH_USER="${BASIC_AUTH_USER}" \
  BASIC_AUTH_PASSWORD="${BASIC_AUTH_PASSWORD}" \
  ACME_EMAIL="${ACME_EMAIL}" \
    bash ./init_env.sh
else
  log "Using existing ${SCRIPT_DIR}/.env. Set FORCE_REGENERATE_ENV=1 to recreate credentials."
fi

log "Building and starting containers"
docker compose -f docker-compose.yml up -d --build

log "Deployment complete"
echo "URL: https://${PUBLIC_HOST}/"
echo "Status: docker compose -f ${SCRIPT_DIR}/docker-compose.yml ps"
echo "Logs:   docker compose -f ${SCRIPT_DIR}/docker-compose.yml logs -f"
