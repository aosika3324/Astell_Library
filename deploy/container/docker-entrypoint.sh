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

if [[ "$(id -u)" == "0" ]]; then
  chown -R astell:astell \
    "${ASTELL_KNOWLEDGE_LIBRARY:-/data/Library}" \
    "${MEMPALACE_DB:-/data/mempalace_db}" \
    "${ASTELL_COMM_BUFFER:-/data/COMM_BUFFER}" \
    /projects
  exec gosu astell "$0" "$@"
fi

python - <<'PY'
import os
import sqlite3

db_path = os.environ.get("ASTELL_CONTROL_DB", "/data/mempalace_db/astell_control.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)

with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        prefix TEXT,
        is_mc_project INTEGER,
        last_active INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipelines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        created_at TEXT,
        status TEXT DEFAULT 'pending'
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subtasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_id INTEGER,
        content TEXT,
        status TEXT DEFAULT 'pending',
        summary TEXT,
        completed_at TEXT,
        FOREIGN KEY (pipeline_id) REFERENCES pipelines(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_executions (
        id TEXT PRIMARY KEY,
        title TEXT,
        prompt TEXT,
        status TEXT DEFAULT 'pending',
        log_path TEXT,
        created_at TEXT,
        completed_at TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS solidification_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_path TEXT,
        prefix TEXT,
        wing_name TEXT,
        solidified_at TEXT,
        files_count INTEGER,
        details TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'employee')),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_login_at TEXT
    )
    """)
    conn.commit()
print(f"Initialized SQLite database at: {db_path}")
PY

exec "$@"
