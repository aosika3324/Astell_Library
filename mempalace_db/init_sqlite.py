import sqlite3
import os

DB_PATH = os.environ.get(
    "ASTELL_CONTROL_DB",
    os.path.join(os.path.dirname(__file__), "astell_control.db"),
)

def init_db():
    print(f"Initializing SQLite database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 活跃项目及配置表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE,
        prefix TEXT,
        is_mc_project INTEGER,
        last_active INTEGER DEFAULT 0
    )
    """)
    
    # 2. 任务流水线及子任务表
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
    
    # 3. 运行实例及日志关联表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_executions (
        id TEXT PRIMARY KEY, -- task_id like research_xxxx or task_xxxx
        title TEXT,
        prompt TEXT,
        status TEXT DEFAULT 'pending',
        log_path TEXT,
        created_at TEXT,
        completed_at TEXT
    )
    """)
    
    # 4. 固化历史记录表
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
    
    conn.commit()
    conn.close()
    print("Database tables initialized successfully.")

if __name__ == "__main__":
    init_db()
