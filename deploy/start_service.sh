#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PUBLIC_HOST="${PUBLIC_HOST:-${1:-localhost}}"
BASIC_AUTH_USER="${BASIC_AUTH_USER:-${2:-astell}}"
BASIC_AUTH_PASSWORD="${BASIC_AUTH_PASSWORD:-${3:-}}"
ACME_EMAIL="${ACME_EMAIL:-${4:-admin@example.com}}"
ASTELL_PUBLISHED_PORT="${ASTELL_PUBLISHED_PORT:-8080}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
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

if [[ "${PUBLIC_HOST}" == "localhost" || "${PUBLIC_HOST}" == "127.0.0.1" ]]; then
  ASTELL_CORS_ORIGINS="http://localhost:${ASTELL_PUBLISHED_PORT},http://127.0.0.1:${ASTELL_PUBLISHED_PORT}"
else
  ASTELL_CORS_ORIGINS="https://${PUBLIC_HOST}"
fi

cat > .env <<EOF
PUBLIC_HOST=${PUBLIC_HOST}
ACME_EMAIL=${ACME_EMAIL}
BASIC_AUTH_USER=${BASIC_AUTH_USER}
BASIC_AUTH_HASH=${BASIC_AUTH_HASH}
ASTELL_AUTH_ENABLED=1
ASTELL_AUTH_USER=${BASIC_AUTH_USER}
ASTELL_AUTH_PASSWORD_SHA256=${ASTELL_AUTH_PASSWORD_SHA256}
ASTELL_AUTH_REALM=Astell Library
ASTELL_CORS_ORIGINS=${ASTELL_CORS_ORIGINS}
ASTELL_UI_HOST=0.0.0.0
ASTELL_UI_PORT=8080
ASTELL_OPEN_BROWSER=0
ASTELL_PUBLISHED_PORT=${ASTELL_PUBLISHED_PORT}
EOF

chmod 600 .env
mkdir -p deploy/container/projects

docker compose up -d --build

echo "Astell service is starting."
echo "URL: http://localhost:${ASTELL_PUBLISHED_PORT}/"
echo "Username: ${BASIC_AUTH_USER}"
if [[ "${GENERATED_PASSWORD}" == "1" ]]; then
  echo "Generated password: ${BASIC_AUTH_PASSWORD}"
  echo "Store this password now; it is not written in plaintext."
fi
