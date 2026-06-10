import sqlite3
import os
import time
from datetime import datetime

DB_PATH = os.environ.get(
    "ASTELL_CONTROL_DB",
    os.path.join(os.path.dirname(__file__), "astell_control.db"),
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# === Project APIs ===
def add_project(path, prefix, is_mc_project):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO projects (path, prefix, is_mc_project, last_active) VALUES (?, ?, ?, ?)",
            (path, prefix, int(is_mc_project), int(time.time()))
        )
        # 将其他项目的 last_active 置为 0
        cursor.execute("UPDATE projects SET last_active = 0 WHERE path != ?", (path,))
        conn.commit()
    finally:
        conn.close()

def get_active_project():
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM projects WHERE last_active > 0 ORDER BY last_active DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_projects():
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM projects ORDER BY last_active DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# === Pipeline APIs ===
def create_pipeline_in_db(name, tasks):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO pipelines (name, created_at, status) VALUES (?, ?, 'pending')", (name, now_str))
        pipeline_id = cursor.lastrowid
        
        for t in tasks:
            cursor.execute(
                "INSERT INTO subtasks (pipeline_id, content, status) VALUES (?, ?, 'pending')",
                (pipeline_id, t["content"])
            )
        conn.commit()
        return pipeline_id
    finally:
        conn.close()

def get_pipelines():
    conn = get_db_connection()
    cursor = conn.cursor()
    pipelines = cursor.execute("SELECT * FROM pipelines ORDER BY id DESC").fetchall()
    result = []
    for p in pipelines:
        p_dict = dict(p)
        subtasks = cursor.execute("SELECT * FROM subtasks WHERE pipeline_id = ?", (p_dict["id"],)).fetchall()
        p_dict["tasks"] = [dict(s) for s in subtasks]
        result.append(p_dict)
    conn.close()
    return result

def update_subtask_status(subtask_id, status, summary=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if summary:
            cursor.execute(
                "UPDATE subtasks SET status = ?, summary = ?, completed_at = ? WHERE id = ?",
                (status, summary, now_str, subtask_id)
            )
        else:
            cursor.execute(
                "UPDATE subtasks SET status = ? WHERE id = ?",
                (status, subtask_id)
            )
        
        # Check if all subtasks in the pipeline are done
        subtask = cursor.execute("SELECT pipeline_id FROM subtasks WHERE id = ?", (subtask_id,)).fetchone()
        if subtask:
            pid = subtask["pipeline_id"]
            total = cursor.execute("SELECT COUNT(*) as cnt FROM subtasks WHERE pipeline_id = ?", (pid,)).fetchone()["cnt"]
            done = cursor.execute("SELECT COUNT(*) as cnt FROM subtasks WHERE pipeline_id = ? AND status = 'done'", (pid,)).fetchone()["cnt"]
            p_status = "running"
            if done == total:
                p_status = "completed"
            elif done > 0:
                p_status = "running"
            cursor.execute("UPDATE pipelines SET status = ? WHERE id = ?", (p_status, pid))
            
        conn.commit()
    finally:
        conn.close()

# === Solidification Records ===
def record_solidification(project_path, prefix, wing_name, files_count, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO solidification_history (project_path, prefix, wing_name, solidified_at, files_count, details) VALUES (?, ?, ?, ?, ?, ?)",
            (project_path, prefix, wing_name, now_str, files_count, details)
        )
        conn.commit()
    finally:
        conn.close()
