import sys
import os
import base64
import binascii
import hashlib
import json
import secrets
import sqlite3
import urllib.parse
import webbrowser
import threading
import time
import shutil
import subprocess
from datetime import datetime
from typing import List, Optional
from astell_config import (
    ASTELL_AUTH_ENABLED,
    ASTELL_AUTH_PASSWORD,
    ASTELL_AUTH_PASSWORD_SHA256,
    ASTELL_AUTH_REALM,
    ASTELL_AUTH_USER,
    ASTELL_CORS_ORIGINS,
    ASTELL_CONTROL_DB,
    ASTELL_LIBRARY_ROOT as ASTELL_LIBRARY_ROOT_PATH,
    ASTELL_OPEN_BROWSER,
    ASTELL_UI_HOST,
    ASTELL_UI_PORT,
    LIBRARY_PATH as LIBRARY_PATH_VALUE,
    MEMPALACE_DB as MEMPALACE_DB_PATH,
    MEMPALACE_SRC,
    add_runtime_paths,
)

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 引入数据库辅助
add_runtime_paths()
from mempalace_db.db_helper import (
    add_project, get_active_project, get_all_projects,
    create_pipeline_in_db, get_pipelines, update_subtask_status,
    record_solidification
)
from mempalace_db.sync_state import sync_active_project_to_env
from modsdk_wing import (
    generate_modsdk_template,
    get_modsdk_best_practices,
    review_modsdk_code,
    search_modsdk_official,
)

ASTELL_LIBRARY_ROOT = str(ASTELL_LIBRARY_ROOT_PATH)
LIBRARY_PATH = str(LIBRARY_PATH_VALUE)
MEMPALACE_DB = str(MEMPALACE_DB_PATH)
# 初始化 FastAPI app
app = FastAPI(title="Astell Control Tower API", version="2.0.0")

if ASTELL_AUTH_ENABLED and not (ASTELL_AUTH_PASSWORD or ASTELL_AUTH_PASSWORD_SHA256):
    raise RuntimeError(
        "ASTELL_AUTH_PASSWORD or ASTELL_AUTH_PASSWORD_SHA256 must be set when ASTELL_AUTH_ENABLED=1"
    )


AUTH_EXEMPT_PATHS = {"/healthz"}


def _auth_challenge() -> Response:
    return Response(
        content="Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": f'Basic realm="{ASTELL_AUTH_REALM}"'},
    )


def _basic_auth_valid(header_value: str) -> bool:
    auth_scheme, separator, auth_param = header_value.partition(" ")
    if auth_scheme.lower() != "basic" or not separator:
        return False
    try:
        decoded = base64.b64decode(auth_param.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    if not secrets.compare_digest(username, ASTELL_AUTH_USER):
        return False
    if ASTELL_AUTH_PASSWORD:
        return secrets.compare_digest(password, ASTELL_AUTH_PASSWORD)
    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(password_hash, ASTELL_AUTH_PASSWORD_SHA256)


@app.middleware("http")
async def require_basic_auth(request: Request, call_next):
    if not ASTELL_AUTH_ENABLED or request.url.path in AUTH_EXEMPT_PATHS:
        return await call_next(request)
    if _basic_auth_valid(request.headers.get("Authorization", "")):
        return await call_next(request)
    return _auth_challenge()


def _resolve_under(base_path: str, rel_path: str, *, must_be_file: bool = False) -> str:
    """Resolve a user-supplied relative path and keep it inside base_path."""

    base = os.path.realpath(base_path)
    target = os.path.realpath(os.path.join(base, rel_path))
    base_cmp = os.path.normcase(base)
    target_cmp = os.path.normcase(target)
    if target_cmp != base_cmp and not target_cmp.startswith(base_cmp + os.sep):
        raise HTTPException(status_code=400, detail="路径越界")
    if must_be_file and not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="文件不存在")
    return target

# 挂载静态文件目录
app.mount("/ui", StaticFiles(directory=os.path.join(ASTELL_LIBRARY_ROOT, "ui")), name="ui")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ASTELL_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Models ===
class ProjectCreate(BaseModel):
    path: str
    prefix: Optional[str] = None
    is_mc_project: bool = True


class ModsdkSearchRequest(BaseModel):
    query: str
    scope: str = "docs"
    limit: int = 5


class ModsdkTemplateRequest(BaseModel):
    kind: str
    identifier: str
    namespace: str = "astell"
    display_name: Optional[str] = None


class ModsdkReviewRequest(BaseModel):
    code: str
    filename: str = "snippet.py"


class ModsdkPracticesRequest(BaseModel):
    topic: str = "general"

# 同步初始环境
sync_active_project_to_env()

# --- Static views ---
@app.get("/", response_class=HTMLResponse)
def get_index():
    html_path = os.path.join(ASTELL_LIBRARY_ROOT, "ui", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/index.html", response_class=HTMLResponse)
def get_index_alias():
    return get_index()

# --- API Endpoints ---

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    sqlite_ok = False
    try:
        with sqlite3.connect(str(ASTELL_CONTROL_DB)) as conn:
            conn.execute("SELECT 1")
        sqlite_ok = True
    except sqlite3.Error:
        sqlite_ok = False

    checks = {
        "library": os.path.isdir(LIBRARY_PATH),
        "mempalace_db": os.path.isdir(MEMPALACE_DB),
        "control_db": sqlite_ok,
    }
    ready = all(checks.values())
    body = {"status": "ready" if ready else "not_ready", "checks": checks}
    if not ready:
        return JSONResponse(content=body, status_code=503)
    return body


@app.get("/api/status")
def get_status():
    active_project = get_active_project()
    return {
        "active_project": active_project["path"] if active_project else "None",
        "active_prefix": active_project["prefix"] if active_project else "None",
        "library_wings": [d for d in os.listdir(LIBRARY_PATH) if d.startswith("wing_")] if os.path.exists(LIBRARY_PATH) else [],
        "all_projects": get_all_projects()
    }

@app.post("/api/project/switch")
def switch_project(proj: ProjectCreate):
    path = proj.path
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"路径不存在: {path}")
        
    is_mc = proj.is_mc_project
    # 如果没传前缀，自动获取目录名
    prefix = proj.prefix or os.path.basename(path).replace(" ", "_")
    
    # 存入 SQLite 数据库
    add_project(path, prefix, is_mc)
    sync_active_project_to_env()
    
    # 创建四件套文件（如果有的话）
    status_msg = []
    file_types = {
        "dev": "开发日志",
        "info": "信息记录.md",
        "problem": "问题记录",
        "search": "搜索日志.md"
    }
    for key, val in file_types.items():
        filename = f"{prefix}_{val}"
        full_path = os.path.join(path, filename)
        
        if key in ["dev", "problem"]:
            if not os.path.exists(full_path):
                os.makedirs(full_path, exist_ok=True)
                status_msg.append(f"已创建文件夹 {filename}")
            else:
                status_msg.append(f"已对接文件夹 {filename}")
        else:
            if not os.path.exists(full_path):
                with open(full_path, "w", encoding="utf-8") as f:
                    if key == "info":
                        f.write("# 📇 信息记录\n\n| 资源ID | 描述 | 路径 | 记录时间 |\n| --- | --- | --- | --- |\n")
                    elif key == "search":
                        f.write("# 🔍 搜索日志\n\n")
                status_msg.append(f"已创建文件 {filename}")
            else:
                status_msg.append(f"已对接文件 {filename}")
            
    return {"success": True, "project": {"path": path, "prefix": prefix, "is_mc": is_mc}, "details": status_msg}

@app.get("/api/workspace/modules")
def get_workspace_modules():
    """获取工作区的所有模块化记录及其信任状态"""
    project = get_active_project()
    if not project:
        return {"modules": []}
    
    path = project["path"]
    prefix = project["prefix"]
    
    dev_dir = os.path.join(path, f"{prefix}_开发日志")
    prob_dir = os.path.join(path, f"{prefix}_问题记录")
    
    modules = {}

    # 扫描开发日志
    if os.path.exists(dev_dir):
        for f in os.listdir(dev_dir):
            if f.endswith(".md"):
                m_name = f[:-3]
                modules[m_name] = {
                    "name": m_name,
                    "has_dev": True,
                    "has_prob": False,
                    "prob_resolved": True,
                    "is_untrustworthy": False,
                    "dev_path": os.path.join(f"{prefix}_开发日志", f)
                }

    # 扫描问题记录并进行交叉审计
    if os.path.exists(prob_dir):
        for f in os.listdir(prob_dir):
            if f.endswith(".md"):
                m_name = f[:-3]
                if m_name not in modules:
                    modules[m_name] = {
                        "name": m_name,
                        "has_dev": False,
                        "is_untrustworthy": False,
                        "dev_path": None
                    }
                
                modules[m_name]["has_prob"] = True
                modules[m_name]["prob_path"] = os.path.join(f"{prefix}_问题记录", f)
                
                # 读取内容检查状态
                with open(os.path.join(prob_dir, f), "r", encoding="utf-8") as file:
                    content = file.read()
                    # 如果包含 "尝试中" 或 "未解决"，则视为未闭环
                    if "状态: 尝试中" in content or "未解决" in content:
                        modules[m_name]["prob_resolved"] = False
                    else:
                        modules[m_name]["prob_resolved"] = True
                    
                    if "不可信" in content or "<!-- UNTRUSTWORTHY -->" in content:
                        modules[m_name]["is_untrustworthy"] = True

    # 检查开发日志自身的不可信标记
    for m in modules.values():
        if m.get("has_dev") and not m.get("is_untrustworthy"):
            full_dev_path = os.path.join(path, m["dev_path"])
            with open(full_dev_path, "r", encoding="utf-8") as file:
                if "不可信" in file.read() or "<!-- UNTRUSTWORTHY -->" in file.read():
                    m["is_untrustworthy"] = True

    return {"modules": list(modules.values())}

@app.get("/api/workspace/read")
def read_workspace_file(rel_path: str):
    project = get_active_project()
    if not project: raise HTTPException(status_code=400, detail="无活跃项目")
    
    full_path = _resolve_under(project["path"], rel_path, must_be_file=True)
    
    with open(full_path, "r", encoding="utf-8") as f:
        return {"content": f.read()}

class TagRequest(BaseModel):
    rel_path: str
    tag: str # "untrustworthy"

@app.post("/api/workspace/tag")
def tag_file(req: TagRequest):
    project = get_active_project()
    if not project: raise HTTPException(status_code=400, detail="无活跃项目")
    
    full_path = _resolve_under(project["path"], req.rel_path, must_be_file=True)
        
    if req.tag == "untrustworthy":
        with open(full_path, "a", encoding="utf-8") as f:
            f.write("\n\n> ⚠️ <!-- UNTRUSTWORTHY --> **此记录已被人工标记为不可信，严禁固化。**")
            
    return {"success": True}


@app.post("/api/modsdk/search")
def api_modsdk_search(req: ModsdkSearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    return search_modsdk_official(req.query, scope=req.scope, limit=req.limit)


@app.post("/api/modsdk/template")
def api_modsdk_template(req: ModsdkTemplateRequest):
    if not req.identifier.strip():
        raise HTTPException(status_code=400, detail="identifier 不能为空")
    try:
        return generate_modsdk_template(
            kind=req.kind,
            identifier=req.identifier,
            namespace=req.namespace,
            display_name=req.display_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/modsdk/review")
def api_modsdk_review(req: ModsdkReviewRequest):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="代码不能为空")
    result = review_modsdk_code(req.code)
    result["filename"] = req.filename
    return result


@app.post("/api/modsdk/practices")
def api_modsdk_practices(req: ModsdkPracticesRequest):
    return get_modsdk_best_practices(req.topic)

@app.get("/api/pending")
def get_pending():
    """保留旧接口适配，但逻辑改为从模块中提取可固化项"""
    modules_res = get_workspace_modules()
    pending_items = []
    
    for m in modules_res["modules"]:
        # 交叉审计逻辑：有开发日志且没有报错（或报错已解决），且未被标记为不可信
        if m.get("has_dev") and m.get("prob_resolved", True) and not m.get("is_untrustworthy"):
            pending_items.append({
                "type": "module",
                "title": f"模块固化: {m['name']}",
                "content": f"该模块开发记录完整，且经交叉审计无挂起报错。\n关联文件: {m['dev_path']}",
                "module_name": m['name'],
                "rel_path": m['dev_path']
            })
            
    return {"pending": pending_items}

# --- 物理固化 API ---
class SolidifyRequest(BaseModel):
    rel_path: str # e.g. "MyMod_开发日志/夜视曲奇.md"
    module_name: str

@app.post("/api/solidify/execute")
def execute_solidify(req: SolidifyRequest):
    project = get_active_project()
    if not project:
        raise HTTPException(status_code=400, detail="未设置活跃项目")
        
    path = project["path"]
    prefix = project["prefix"]
    
    # 物理路径
    src_full_path = _resolve_under(path, req.rel_path, must_be_file=True)

    # 固化至统一的项目记忆分区，以项目名作为 Room
    wing_name = "wing_Project_Memory"
    room_name = f"room_{prefix}"
    target_wing_path = os.path.join(LIBRARY_PATH, wing_name)
    target_room_path = os.path.join(target_wing_path, room_name)
    target_drawer_path = os.path.join(target_room_path, "drawer")

    # 创建目标结构并写入 mempalace.yaml
    os.makedirs(target_drawer_path, exist_ok=True)
    config_path = os.path.join(target_room_path, "mempalace.yaml")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"wing: {wing_name}\nrooms:\n  - name: {room_name}\n    description: \"Memory for {prefix}\"")
    
    copied_count = 0
    copied_details = []

    # 备份当前原子文件
    timestamp = datetime.now().strftime("%Y%m%d")
    dest_filename = f"{req.module_name}_{timestamp}.md"
    dest_path = os.path.join(target_drawer_path, dest_filename)
    
    try:
        shutil.copy2(src_full_path, dest_path)
        copied_count += 1
        copied_details.append(f"已备份模块: {req.module_name} -> {dest_filename}")
        
        # 如果有同名的已解决报错，也一并固化
        prob_rel_path = os.path.join(f"{prefix}_问题记录", f"{req.module_name}.md")
        prob_full_path = _resolve_under(path, prob_rel_path)
        if os.path.exists(prob_full_path):
            prob_dest_filename = f"{req.module_name}_problem_{timestamp}.md"
            shutil.copy2(prob_full_path, os.path.join(target_drawer_path, prob_dest_filename))
            copied_count += 1
            copied_details.append(f"同步备份报错记录: {prob_dest_filename}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"物理备份失败: {str(e)}")

    # 触发 MemPalace 索引
    vector_status = "Skipped"
    try:
        add_runtime_paths()
        from mempalace.miner import mine
        # mine 现在只支持 project_dir 和 wing_override
        # 我们传入 room 目录，并在其中放置了 mempalace.yaml
        mine(
            project_dir=target_room_path,
            palace_path=MEMPALACE_DB,
            wing_override=wing_name
        )
        vector_status = "Success"
        
        # 在原子原文件中留下固化标记
        for orig_file_path in [src_full_path, prob_full_path if 'prob_full_path' in locals() and os.path.exists(prob_full_path) else None]:
            if orig_file_path and os.path.exists(orig_file_path):
                with open(orig_file_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n--- 🛡️ 已于 {datetime.now().strftime('%Y-%m-%d %H:%M')} 物理固化至记忆宫殿 ---")
                    
    except Exception as e:
        vector_status = f"Failed: {str(e)}"

    # 记录到 SQLite 历史表
    record_solidification(
        project_path=path,
        prefix=prefix,
        wing_name=wing_name,
        files_count=copied_count,
        details=json.dumps(copied_details)
    )

    return {
        "success": True,
        "copied_count": copied_count,
        "vector_status": vector_status,
        "details": copied_details
    }

# --- 知识库树读取 API ---
def _get_vectorized_files():
    """从 ChromaDB 中获取所有已索引的文件路径列表"""
    try:
        add_runtime_paths()
        from mempalace.palace import get_collection
        col = get_collection(MEMPALACE_DB, create=False)
        # 获取所有元数据中的 source_file
        results = col.get(include=["metadatas"])
        indexed_files = set()
        for meta in results.get("metadatas", []):
            if "source_file" in meta:
                # 统一路径格式
                indexed_files.add(os.path.normpath(meta["source_file"]))
        return indexed_files
    except Exception:
        return set()

def _get_library_tree(root_path, indexed_files):
    tree = []
    try:
        for item in os.listdir(root_path):
            if item.startswith('.'):
                continue
            full_path = os.path.join(root_path, item)
            is_dir = os.path.isdir(full_path)
            rel_path = os.path.relpath(full_path, LIBRARY_PATH)
            
            node = {
                "name": item,
                "path": rel_path.replace("\\", "/"),
                "is_dir": is_dir
            }
            
            if is_dir:
                node["children"] = _get_library_tree(full_path, indexed_files)
                # 文件夹向量化状态：只有当它包含文件且所有文件都已向量化，且所有子文件夹也已向量化时，才为 True
                all_children = node["children"]
                if all_children:
                    # 如果所有子项（文件或文件夹）的 is_vectorized 都为 True，则该文件夹为 True
                    node["is_vectorized"] = all(c.get("is_vectorized", False) for c in all_children)
                else:
                    node["is_vectorized"] = False
            else:
                # 检查是否已向量化
                node["is_vectorized"] = os.path.normpath(full_path) in indexed_files
            
            tree.append(node)
    except Exception as e:
        print(f"Error reading library directory: {e}")
    return sorted(tree, key=lambda x: (not x["is_dir"], x["name"].lower()))

@app.get("/api/library/tree")
def get_library_tree():
    indexed_files = _get_vectorized_files()
    tree = _get_library_tree(LIBRARY_PATH, indexed_files)
    return {"tree": tree}

class MineRequest(BaseModel):
    wing_path: str

@app.post("/api/library/mine")
def mine_wing(req: MineRequest):
    """手动对特定目录触发 mempalace 打包（向量化）"""
    full_path = _resolve_under(LIBRARY_PATH, req.wing_path)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=400, detail="路径不存在")
    
    # 推断 wing
    parts = req.wing_path.replace("\\", "/").split("/")
    wing_name = parts[0] if len(parts) > 0 else "wing_Unknown"

    try:
        add_runtime_paths()
        from mempalace.miner import mine
        mine(
            project_dir=full_path,
            palace_path=MEMPALACE_DB,
            wing_override=wing_name
        )
        return {"success": True, "message": f"目录 {req.wing_path} 已成功向量化"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library/read")
def read_library_file(path: str):
    full_path = _resolve_under(LIBRARY_PATH, path, must_be_file=True)
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except Exception as e:
        return {"content": f"读取文件失败: {str(e)}"}

# --- Server Start Logic ---
def open_browser(url):
    time.sleep(1.5)
    webbrowser.open(url)

def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def find_available_port(start_port: int) -> int:
    port = start_port
    while is_port_in_use(port):
        print(f"Port {port} is in use, trying next port...")
        port += 1
    return port

if __name__ == "__main__":
    import uvicorn
    default_port = ASTELL_UI_PORT
    
    # 如果通过命令行参数传入了端口，则以命令行参数为准；否则自动寻找空闲端口
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            port = find_available_port(default_port)
    else:
        port = find_available_port(default_port)
            
    display_host = "localhost" if ASTELL_UI_HOST in {"0.0.0.0", "::"} else ASTELL_UI_HOST
    url = f"http://{display_host}:{port}"
    print(f"[Astell Control Tower 2.0] Backend Running at: {url}")
    if ASTELL_OPEN_BROWSER:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    # 启动 Uvicorn 服务
    uvicorn.run(app, host=ASTELL_UI_HOST, port=port, log_level="warning")
