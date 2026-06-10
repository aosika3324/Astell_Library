import os
import json
from pathlib import Path

try:
    from astell_config import COMM_BUFFER
except ImportError:
    COMM_BUFFER = Path(__file__).resolve().parents[1] / "COMM_BUFFER"

from mempalace_db.db_helper import get_active_project, add_project

def sync_active_project_to_env():
    proj = get_active_project()
    if proj:
        os.environ["ASTELL_ACTIVE_PROJECT"] = proj["path"]
        os.environ["ASTELL_ACTIVE_PREFIX"] = proj["prefix"]
        return proj
    else:
        # Fallback to env or default
        path = os.environ.get("ASTELL_ACTIVE_PROJECT")
        prefix = os.environ.get("ASTELL_ACTIVE_PREFIX")
        if path and prefix:
            add_project(path, prefix, True)
            return {"path": path, "prefix": prefix}
    return None

def sync_pipeline_json_with_db():
    # 读 task_pipeline.json，同步到 SQLite，实现两边互通，以便 fetch_next_task 和 finish_current_task 继续以 mcp 调用形式正常工作
    pipeline_file = str(COMM_BUFFER / "task_pipeline.json")
    if not os.path.exists(pipeline_file):
        return
        
    try:
        with open(pipeline_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 如果 json 里有 tasks，且没有 active_index 以外的 ID，我们做一个轻量映射
        # 这里主要是为了让 mcp_server 里面老的 fetch_next_task / finish_current_task 能跟 SQLite 映射起来
        # 如果是新系统，我们可以完全统一
    except Exception as e:
        print(f"Error syncing pipeline JSON: {e}")
