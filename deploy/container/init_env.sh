#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PUBLIC_HOST="${1:-${PUBLIC_HOST:-}}"
BASIC_AUTH_USER="${2:-${BASIC_AUTH_USER:-admin}}"
BASIC_AUTH_PASSWORD="${3:-${BASIC_AUTH_PASSWORD:-}}"
ACME_EMAIL="${4:-${ACME_EMAIL:-admin@example.com}}"
EMPLOYEE_AUTH_USER="${5:-${EMPLOYEE_AUTH_USER:-}}"
EMPLOYEE_AUTH_PASSWORD="${6:-${EMPLOYEE_AUTH_PASSWORD:-}}"

if [[ -z "${PUBLIC_HOST}" ]]; then
  cat >&2 <<'EOF'
Usage:
  ./init_env.sh <domain> [admin_user] [admin_password] [acme_email] [employee_user] [employee_password]

Example:
  ./init_env.sh astell.example.com admin 'StrongPasswordHere' it@example.com
  ./init_env.sh astell.example.com admin 'AdminPassword' it@example.com employee 'EmployeePassword'
EOF
  exit 1
fi

if [[ -z "${BASIC_AUTH_PASSWORD}" ]]; then
  BASIC_AUTH_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
  GENERATED_PASSWORD=1
else
  GENERATED_PASSWORD=0
fi

ASTELL_AUTH_PASSWORD_SHA256="$(printf '%s' "${BASIC_AUTH_PASSWORD}" | sha256sum | awk '{print $1}')"
ASTELL_AUTH_USERS_SHA256="${BASIC_AUTH_USER}:${ASTELL_AUTH_PASSWORD_SHA256}:admin"
ASTELL_EMPLOYEE_USERS=""
EMPLOYEE_GENERATED_PASSWORD=0

if [[ -n "${EMPLOYEE_AUTH_USER}" ]]; then
  if [[ -z "${EMPLOYEE_AUTH_PASSWORD}" ]]; then
    EMPLOYEE_AUTH_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
    EMPLOYEE_GENERATED_PASSWORD=1
  fi
  EMPLOYEE_AUTH_PASSWORD_SHA256="$(printf '%s' "${EMPLOYEE_AUTH_PASSWORD}" | sha256sum | awk '{print $1}')"
  ASTELL_AUTH_USERS_SHA256="${ASTELL_AUTH_USERS_SHA256},${EMPLOYEE_AUTH_USER}:${EMPLOYEE_AUTH_PASSWORD_SHA256}:employee"
  ASTELL_EMPLOYEE_USERS="${EMPLOYEE_AUTH_USER}"
fi

cat > .env <<EOF
PUBLIC_HOST=${PUBLIC_HOST}
ACME_EMAIL=${ACME_EMAIL}
BASIC_AUTH_USER=${BASIC_AUTH_USER}
BASIC_AUTH_HASH='unused-app-auth-handled-by-astell'
ASTELL_AUTH_ENABLED=1
ASTELL_AUTH_USER=${BASIC_AUTH_USER}
ASTELL_AUTH_PASSWORD_SHA256=${ASTELL_AUTH_PASSWORD_SHA256}
ASTELL_AUTH_USERS_SHA256=${ASTELL_AUTH_USERS_SHA256}
ASTELL_AUTH_REALM=Astell Library
ASTELL_ADMIN_USERS=${BASIC_AUTH_USER}
ASTELL_EMPLOYEE_USERS=${ASTELL_EMPLOYEE_USERS}
ASTELL_CORS_ORIGINS=https://${PUBLIC_HOST}
ASTELL_UI_HOST=0.0.0.0
ASTELL_UI_PORT=8080
ASTELL_OPEN_BROWSER=0
EOF

chmod 600 .env
mkdir -p projects

echo "Wrote $(pwd)/.env"
echo "Admin username: ${BASIC_AUTH_USER}"
if [[ "${GENERATED_PASSWORD}" == "1" ]]; then
  echo "Generated admin password: ${BASIC_AUTH_PASSWORD}"
  echo "Store this password now; it is not written in plaintext."
fi
if [[ -n "${EMPLOYEE_AUTH_USER}" ]]; then
  echo "Employee username: ${EMPLOYEE_AUTH_USER}"
  if [[ "${EMPLOYEE_GENERATED_PASSWORD}" == "1" ]]; then
    echo "Generated employee password: ${EMPLOYEE_AUTH_PASSWORD}"
    echo "Store this employee password now; it is not written in plaintext."
  fi
fi
