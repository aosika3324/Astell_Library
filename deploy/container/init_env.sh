#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PUBLIC_HOST="${1:-${PUBLIC_HOST:-}}"
BASIC_AUTH_USER="${2:-${BASIC_AUTH_USER:-admin}}"
BASIC_AUTH_PASSWORD="${3:-${BASIC_AUTH_PASSWORD:-}}"
ACME_EMAIL="${4:-${ACME_EMAIL:-admin@example.com}}"

if [[ -z "${PUBLIC_HOST}" ]]; then
  cat >&2 <<'EOF'
Usage:
  ./init_env.sh <domain> [username] [password] [acme_email]

Example:
  ./init_env.sh astell.example.com admin 'StrongPasswordHere' it@example.com
EOF
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to generate the Caddy password hash." >&2
  exit 1
fi

if [[ -z "${BASIC_AUTH_PASSWORD}" ]]; then
  BASIC_AUTH_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
  GENERATED_PASSWORD=1
else
  GENERATED_PASSWORD=0
fi

BASIC_AUTH_HASH="$(docker run --rm caddy:2 caddy hash-password --plaintext "${BASIC_AUTH_PASSWORD}")"
ASTELL_AUTH_PASSWORD_SHA256="$(printf '%s' "${BASIC_AUTH_PASSWORD}" | sha256sum | awk '{print $1}')"

cat > .env <<EOF
PUBLIC_HOST=${PUBLIC_HOST}
ACME_EMAIL=${ACME_EMAIL}
BASIC_AUTH_USER=${BASIC_AUTH_USER}
BASIC_AUTH_HASH='${BASIC_AUTH_HASH}'
ASTELL_AUTH_ENABLED=1
ASTELL_AUTH_USER=${BASIC_AUTH_USER}
ASTELL_AUTH_PASSWORD_SHA256=${ASTELL_AUTH_PASSWORD_SHA256}
ASTELL_AUTH_REALM=Astell Library
ASTELL_CORS_ORIGINS=https://${PUBLIC_HOST}
ASTELL_UI_HOST=0.0.0.0
ASTELL_UI_PORT=8080
ASTELL_OPEN_BROWSER=0
EOF

chmod 600 .env
mkdir -p projects

echo "Wrote $(pwd)/.env"
echo "Username: ${BASIC_AUTH_USER}"
if [[ "${GENERATED_PASSWORD}" == "1" ]]; then
  echo "Generated password: ${BASIC_AUTH_PASSWORD}"
  echo "Store this password now; it is not written in plaintext."
fi
