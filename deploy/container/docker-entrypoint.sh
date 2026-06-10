#!/usr/bin/env bash
set -Eeuo pipefail

seed_dir() {
  local src="$1"
  local dest="$2"

  mkdir -p "${dest}"
  if [[ -d "${src}" ]] && [[ -z "$(find "${dest}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    cp -a "${src}/." "${dest}/"
  fi
}

seed_dir "/app/Library" "${ASTELL_KNOWLEDGE_LIBRARY:-/data/Library}"
seed_dir "/app/mempalace_db" "${MEMPALACE_DB:-/data/mempalace_db}"
seed_dir "/app/COMM_BUFFER" "${ASTELL_COMM_BUFFER:-/data/COMM_BUFFER}"

python /app/mempalace_db/init_sqlite.py

exec "$@"
