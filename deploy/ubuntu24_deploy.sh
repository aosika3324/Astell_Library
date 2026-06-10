#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-astell-library}"
APP_USER="${APP_USER:-astell}"
APP_GROUP="${APP_GROUP:-astell}"
INSTALL_DIR="${INSTALL_DIR:-/opt/astell-library}"
SERVICE_NAME="${SERVICE_NAME:-astell-control-tower}"
ENV_DIR="${ENV_DIR:-/etc/astell-library}"
ENV_FILE="${ENV_FILE:-${ENV_DIR}/astell.env}"

ENABLE_NGINX="${ENABLE_NGINX:-0}"
ENABLE_BASIC_AUTH="${ENABLE_BASIC_AUTH:-0}"
ENABLE_APP_AUTH="${ENABLE_APP_AUTH:-${ENABLE_BASIC_AUTH}}"
ENABLE_UFW="${ENABLE_UFW:-0}"
SERVER_NAME="${SERVER_NAME:-_}"
NGINX_PORT="${NGINX_PORT:-80}"
BASIC_AUTH_USER="${BASIC_AUTH_USER:-astell}"
BASIC_AUTH_PASSWORD="${BASIC_AUTH_PASSWORD:-}"
EMPLOYEE_AUTH_USER="${EMPLOYEE_AUTH_USER:-}"
EMPLOYEE_AUTH_PASSWORD="${EMPLOYEE_AUTH_PASSWORD:-}"
ASTELL_AUTH_USER="${ASTELL_AUTH_USER:-${BASIC_AUTH_USER}}"
ASTELL_AUTH_PASSWORD_SHA256="${ASTELL_AUTH_PASSWORD_SHA256:-}"
ASTELL_AUTH_USERS_SHA256="${ASTELL_AUTH_USERS_SHA256:-}"
ASTELL_ADMIN_USERS="${ASTELL_ADMIN_USERS:-${ASTELL_AUTH_USER}}"
ASTELL_EMPLOYEE_USERS="${ASTELL_EMPLOYEE_USERS:-${EMPLOYEE_AUTH_USER}}"

if [[ "${ENABLE_NGINX}" == "1" && -z "${ASTELL_UI_HOST:-}" ]]; then
  ASTELL_UI_HOST="127.0.0.1"
else
  ASTELL_UI_HOST="${ASTELL_UI_HOST:-0.0.0.0}"
fi
ASTELL_UI_PORT="${ASTELL_UI_PORT:-8080}"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${INSTALL_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

ensure_auth_secret() {
  if [[ "${ENABLE_APP_AUTH}" != "1" ]]; then
    return
  fi
  if [[ -n "${ASTELL_AUTH_PASSWORD_SHA256}" ]]; then
    ASTELL_AUTH_USERS_SHA256="${ASTELL_AUTH_USERS_SHA256:-${ASTELL_AUTH_USER}:${ASTELL_AUTH_PASSWORD_SHA256}:admin}"
  else
    if [[ -z "${BASIC_AUTH_PASSWORD}" ]]; then
      BASIC_AUTH_PASSWORD="$(openssl rand -base64 18)"
      log "Generated BASIC_AUTH_PASSWORD for ${BASIC_AUTH_USER}: ${BASIC_AUTH_PASSWORD}"
    fi
    ASTELL_AUTH_PASSWORD_SHA256="$(printf '%s' "${BASIC_AUTH_PASSWORD}" | sha256sum | awk '{print $1}')"
    ASTELL_AUTH_USERS_SHA256="${ASTELL_AUTH_USERS_SHA256:-${ASTELL_AUTH_USER}:${ASTELL_AUTH_PASSWORD_SHA256}:admin}"
  fi

  if [[ -n "${EMPLOYEE_AUTH_USER}" ]]; then
    if [[ -z "${EMPLOYEE_AUTH_PASSWORD}" ]]; then
      EMPLOYEE_AUTH_PASSWORD="$(openssl rand -base64 18)"
      log "Generated EMPLOYEE_AUTH_PASSWORD for ${EMPLOYEE_AUTH_USER}: ${EMPLOYEE_AUTH_PASSWORD}"
    fi
    local employee_password_sha256
    employee_password_sha256="$(printf '%s' "${EMPLOYEE_AUTH_PASSWORD}" | sha256sum | awk '{print $1}')"
    if [[ "${ASTELL_AUTH_USERS_SHA256}" != *"${EMPLOYEE_AUTH_USER}:"* ]]; then
      ASTELL_AUTH_USERS_SHA256="${ASTELL_AUTH_USERS_SHA256},${EMPLOYEE_AUTH_USER}:${employee_password_sha256}:employee"
    fi
  fi
}

write_env_file() {
  install -d -m 0755 "${ENV_DIR}"
  cat > "${ENV_FILE}" <<EOF
ASTELL_LIBRARY_ROOT=${INSTALL_DIR}
MEMPALACE_SRC=${INSTALL_DIR}/mempalace-develop
MEMPALACE_DB=${INSTALL_DIR}/mempalace_db
ASTELL_KNOWLEDGE_LIBRARY=${INSTALL_DIR}/Library
ASTELL_COMM_BUFFER=${INSTALL_DIR}/COMM_BUFFER
ASTELL_CONTROL_DB=${INSTALL_DIR}/mempalace_db/astell_control.db
ASTELL_UI_HOST=${ASTELL_UI_HOST}
ASTELL_UI_PORT=${ASTELL_UI_PORT}
ASTELL_OPEN_BROWSER=0
ASTELL_AUTH_ENABLED=${ENABLE_APP_AUTH}
ASTELL_AUTH_USER=${ASTELL_AUTH_USER}
ASTELL_AUTH_PASSWORD_SHA256=${ASTELL_AUTH_PASSWORD_SHA256}
ASTELL_AUTH_USERS_SHA256=${ASTELL_AUTH_USERS_SHA256}
ASTELL_AUTH_REALM=Astell Library
ASTELL_ADMIN_USERS=${ASTELL_ADMIN_USERS}
ASTELL_EMPLOYEE_USERS=${ASTELL_EMPLOYEE_USERS}
PYTHONUNBUFFERED=1
EOF
  chmod 0644 "${ENV_FILE}"
}

write_systemd_unit() {
  cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Astell Control Tower
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_BIN} ${INSTALL_DIR}/mcp_ui_server.py
Restart=always
RestartSec=5
UMask=0027
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
}

write_mcp_wrapper() {
  cat > /usr/local/bin/astell-mcp-server <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
set -a
source "${ENV_FILE}"
set +a
cd "${INSTALL_DIR}"
exec "${PYTHON_BIN}" "${INSTALL_DIR}/mcp_server.py"
EOF
  chmod 0755 /usr/local/bin/astell-mcp-server
}

write_nginx_site() {
  local site="/etc/nginx/sites-available/${APP_NAME}.conf"
  local auth_lines=""
  if [[ "${ENABLE_BASIC_AUTH}" == "1" ]]; then
    ensure_auth_secret
    htpasswd -bc "/etc/nginx/${APP_NAME}.htpasswd" "${BASIC_AUTH_USER}" "${BASIC_AUTH_PASSWORD}"
    if [[ -n "${EMPLOYEE_AUTH_USER}" ]]; then
      htpasswd -b "/etc/nginx/${APP_NAME}.htpasswd" "${EMPLOYEE_AUTH_USER}" "${EMPLOYEE_AUTH_PASSWORD}"
    fi
    auth_lines=$'        auth_basic "Astell Library";\n        auth_basic_user_file /etc/nginx/'"${APP_NAME}"$'.htpasswd;'
  fi

  cat > "${site}" <<EOF
server {
    listen ${NGINX_PORT};
    server_name ${SERVER_NAME};

    client_max_body_size 100m;

    location / {
${auth_lines}
        proxy_pass http://127.0.0.1:${ASTELL_UI_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Authorization \$http_authorization;
    }
}
EOF
  ln -sfn "${site}" "/etc/nginx/sites-enabled/${APP_NAME}.conf"
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
}

main() {
  log "Installing OS packages"
  apt-get update
  apt-get install -y \
    build-essential \
    curl \
    git \
    openssl \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    rsync \
    sqlite3

  if [[ "${ENABLE_NGINX}" == "1" ]]; then
    apt-get install -y nginx apache2-utils
  fi

  need_cmd python3
  need_cmd rsync
  need_cmd systemctl

  log "Creating service user ${APP_USER}"
  if ! getent group "${APP_GROUP}" >/dev/null; then
    groupadd --system "${APP_GROUP}"
  fi
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --gid "${APP_GROUP}" --home-dir "${INSTALL_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
  fi

  log "Copying application to ${INSTALL_DIR}"
  install -d -m 0755 "${INSTALL_DIR}"
  if systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1; then
    systemctl stop "${SERVICE_NAME}" || true
  fi
  rsync -a \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    "${SOURCE_DIR}/" "${INSTALL_DIR}/"

  log "Creating Python virtual environment"
  python3 -m venv "${VENV_DIR}"
  "${PYTHON_BIN}" -m pip install --upgrade pip setuptools wheel

  log "Installing Python dependencies"
  "${PYTHON_BIN}" -m pip install -r "${INSTALL_DIR}/requirements.txt"
  "${PYTHON_BIN}" -m pip install -e "${INSTALL_DIR}/mempalace-develop"

  ensure_auth_secret

  log "Writing runtime environment"
  write_env_file
  chown root:root "${ENV_FILE}"

  log "Preparing persistent directories and SQLite"
  install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0750 \
    "${INSTALL_DIR}/Library" \
    "${INSTALL_DIR}/mempalace_db" \
    "${INSTALL_DIR}/COMM_BUFFER"
  set -a
  source "${ENV_FILE}"
  set +a
  "${PYTHON_BIN}" "${INSTALL_DIR}/mempalace_db/init_sqlite.py"

  log "Fixing ownership"
  chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"

  log "Installing systemd service"
  write_systemd_unit
  write_mcp_wrapper
  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}"
  systemctl restart "${SERVICE_NAME}"

  if [[ "${ENABLE_NGINX}" == "1" ]]; then
    log "Configuring Nginx reverse proxy"
    write_nginx_site
  fi

  if [[ "${ENABLE_UFW}" == "1" ]] && command -v ufw >/dev/null 2>&1; then
    log "Opening firewall port"
    if [[ "${ENABLE_NGINX}" == "1" ]]; then
      ufw allow "${NGINX_PORT}/tcp"
    else
      ufw allow "${ASTELL_UI_PORT}/tcp"
    fi
  fi

  log "Checking service health"
  local health_host="${ASTELL_UI_HOST}"
  if [[ "${health_host}" == "0.0.0.0" || "${health_host}" == "::" || "${health_host}" == "localhost" ]]; then
    health_host="127.0.0.1"
  fi
  local health_url="http://${health_host}:${ASTELL_UI_PORT}/healthz"
  for _ in $(seq 1 30); do
    if curl -fsS "${health_url}" >/dev/null; then
      break
    fi
    sleep 2
  done
  curl -fsS "${health_url}" >/dev/null

  local server_ip
  server_ip="$(hostname -I | awk '{print $1}')"
  log "Deployment complete"
  if [[ "${ENABLE_NGINX}" == "1" ]]; then
    echo "UI URL: http://${server_ip}:${NGINX_PORT}/"
  else
    echo "UI URL: http://${server_ip}:${ASTELL_UI_PORT}/"
  fi
  echo "Service: systemctl status ${SERVICE_NAME}"
  echo "Logs:    journalctl -u ${SERVICE_NAME} -f"
  echo "MCP command: /usr/local/bin/astell-mcp-server"
}

main "$@"
