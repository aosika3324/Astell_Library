import sys
import os
import base64
import binascii
import hashlib
import hmac
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
    ASTELL_AUTH_BOOTSTRAP_MODE,
    ASTELL_AUTH_USERS_SHA256,
    ASTELL_ADMIN_USERS,
    ASTELL_CORS_ORIGINS,
    ASTELL_CONTROL_DB,
    ASTELL_EMPLOYEE_USERS,
    ASTELL_JWT_EXPIRE_MINUTES,
    ASTELL_JWT_SECRET,
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
import mcp_server as astell_tools

ASTELL_LIBRARY_ROOT = str(ASTELL_LIBRARY_ROOT_PATH)
LIBRARY_PATH = str(LIBRARY_PATH_VALUE)
MEMPALACE_DB = str(MEMPALACE_DB_PATH)
# 初始化 FastAPI app
app = FastAPI(title="Astell Control Tower API", version="2.0.0")


AUTH_EXEMPT_PATHS = {"/", "/index.html", "/healthz", "/readyz", "/api/auth/login"}
AUTH_EXEMPT_PREFIXES = ("/ui/",)
ADMIN_REQUIRED_ENDPOINTS = {
    ("GET", "/api/users"),
    ("GET", "/api/pending"),
    ("GET", "/api/astell/audit-report"),
    ("POST", "/api/project/switch"),
    ("POST", "/api/project/prefix"),
    ("POST", "/api/users"),
    ("POST", "/api/workspace/tag"),
    ("POST", "/api/solidify/execute"),
    ("POST", "/api/solidify/reject"),
    ("POST", "/api/library/mine"),
}

AUTH_USER_HASHES: dict[str, str] = {}
AUTH_USER_PASSWORDS: dict[str, str] = {}
AUTH_USER_ROLES: dict[str, str] = {}
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = max(1, ASTELL_JWT_EXPIRE_MINUTES) * 60
PASSWORD_ITERATIONS = 120_000


def _role_from_sets(username: str | None) -> str:
    if username and username in ASTELL_ADMIN_USERS:
        return "admin"
    if username and username in ASTELL_EMPLOYEE_USERS:
        return "employee"
    return "admin" if not ASTELL_AUTH_ENABLED else "employee"


def _register_auth_user(
    username: str | None,
    *,
    password: str | None = None,
    password_sha256: str | None = None,
    role: str | None = None,
) -> None:
    if not username:
        return
    if password:
        AUTH_USER_PASSWORDS[username] = password
    if password_sha256:
        AUTH_USER_HASHES[username] = password_sha256.lower()
    resolved_role = role if role in {"admin", "employee"} else _role_from_sets(username)
    AUTH_USER_ROLES[username] = resolved_role


_register_auth_user(
    ASTELL_AUTH_USER,
    password=ASTELL_AUTH_PASSWORD,
    password_sha256=ASTELL_AUTH_PASSWORD_SHA256,
)

for raw_auth_user in ASTELL_AUTH_USERS_SHA256:
    parts = raw_auth_user.split(":")
    if len(parts) < 2:
        continue
    username = parts[0].strip()
    password_sha256 = parts[1].strip().lower()
    role = parts[2].strip().lower() if len(parts) > 2 else None
    _register_auth_user(username, password_sha256=password_sha256, role=role)


def _auth_db_conn():
    conn = sqlite3.connect(str(ASTELL_CONTROL_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_user_store() -> None:
    os.makedirs(os.path.dirname(str(ASTELL_CONTROL_DB)), exist_ok=True)
    with _auth_db_conn() as conn:
        conn.execute(
            """
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
            """
        )
        conn.commit()


def _hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest_b64}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("sha256$"):
        expected = stored_hash.split("$", 1)[1]
        actual = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(actual, expected)

    parts = stored_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    _, iterations, salt, expected_b64 = parts
    try:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
    except ValueError:
        return False
    actual_b64 = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return secrets.compare_digest(actual_b64, expected_b64)


def _upsert_user(username: str, password_hash: str | None, role: str, is_active: bool = True) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if role not in {"admin", "employee"}:
        raise ValueError("role must be admin or employee")

    with _auth_db_conn() as conn:
        existing = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        effective_hash = password_hash or (existing["password_hash"] if existing else None)
        if not effective_hash:
            raise ValueError("password is required for new users")
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = excluded.role,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (username, effective_hash, role, int(is_active), now, now),
        )
        conn.commit()


def _seed_user(username: str, password_hash: str, role: str) -> None:
    if ASTELL_AUTH_BOOTSTRAP_MODE == "sync":
        _upsert_user(username, password_hash, role, True)
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _auth_db_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (username, password_hash, role, now, now),
        )
        conn.commit()


def _bootstrap_auth_users() -> None:
    _ensure_user_store()

    for username, password in AUTH_USER_PASSWORDS.items():
        _seed_user(username, _hash_password(password), _role_for_user(username))

    for username, password_sha256 in AUTH_USER_HASHES.items():
        _seed_user(username, f"sha256${password_sha256}", _role_for_user(username))

    if ASTELL_AUTH_ENABLED:
        with _auth_db_conn() as conn:
            user_count = conn.execute("SELECT COUNT(*) AS count FROM users WHERE is_active = 1").fetchone()["count"]
        if user_count == 0:
            raise RuntimeError(
                "No active users configured. Set ASTELL_AUTH_PASSWORD_SHA256 or ASTELL_AUTH_USERS_SHA256."
            )


def _get_user(username: str):
    with _auth_db_conn() as conn:
        return conn.execute(
            "SELECT username, password_hash, role, is_active FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def _list_users() -> list[dict]:
    with _auth_db_conn() as conn:
        rows = conn.execute(
            "SELECT username, role, is_active, created_at, updated_at, last_login_at FROM users ORDER BY role, username"
        ).fetchall()
    return [dict(row) for row in rows]


def _authenticate_credentials(username: str, password: str) -> dict | None:
    user = _get_user(username)
    if not user or not user["is_active"]:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _auth_db_conn() as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE username = ?", (now, username))
        conn.commit()
    return {"username": user["username"], "role": user["role"]}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _create_jwt(username: str, role: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + JWT_TTL_SECONDS
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": exp,
        "nonce": secrets.token_urlsafe(12),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(ASTELL_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}", exp


def _verify_jwt(token: str) -> dict | None:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(ASTELL_JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not secrets.compare_digest(actual, expected):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, binascii.Error, UnicodeDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    username = payload.get("sub")
    role = payload.get("role")
    if not username or role not in {"admin", "employee"}:
        return None

    user = _get_user(username)
    if not user or not user["is_active"] or user["role"] != role:
        return None
    return {"username": username, "role": role}


def _authenticated_session(header_value: str) -> dict | None:
    auth_scheme, separator, token = header_value.partition(" ")
    if auth_scheme.lower() != "bearer" or not separator:
        return None
    return _verify_jwt(token.strip())


def _role_for_user(username: str | None) -> str:
    if username and username in AUTH_USER_ROLES:
        return AUTH_USER_ROLES[username]
    return _role_from_sets(username)


def _is_auth_exempt(path: str) -> bool:
    return path in AUTH_EXEMPT_PATHS or any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


_bootstrap_auth_users()


@app.middleware("http")
async def require_auth(request: Request, call_next):
    if not ASTELL_AUTH_ENABLED:
        request.state.username = "local"
        request.state.role = "admin"
        return await call_next(request)

    if _is_auth_exempt(request.url.path):
        return await call_next(request)

    session = _authenticated_session(request.headers.get("Authorization", ""))
    if not session:
        return JSONResponse(
            content={"detail": "Authentication required"},
            status_code=401,
        )

    request.state.username = session["username"]
    request.state.role = session["role"]
    role = session["role"]
    if (request.method.upper(), request.url.path) in ADMIN_REQUIRED_ENDPOINTS and role != "admin":
        return JSONResponse(
            content={"detail": "Admin role required"},
            status_code=403,
        )
    return await call_next(request)


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
class LoginRequest(BaseModel):
    username: str
    password: str


class UserUpsertRequest(BaseModel):
    username: str
    password: Optional[str] = None
    role: str = "employee"
    is_active: bool = True


class ProjectCreate(BaseModel):
    path: str
    prefix: Optional[str] = None
    is_mc_project: bool = True


class ProjectPrefixUpdate(BaseModel):
    new_prefix: str


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


class AstellTraceRequest(BaseModel):
    type: str
    content: str
    title: str = "新记录"


class AstellResourceRequest(BaseModel):
    resource_id: str
    description: str
    file_path: str = "N/A"


class AstellRetrieveRequest(BaseModel):
    query: str
    current_project: Optional[str] = None
    strict_mode: bool = False


class AstellResearchRequest(BaseModel):
    query: str


def _call_astell_tool(tool_fn, *args, **kwargs):
    astell_tools.manager.sync_with_db()
    return tool_fn(*args, **kwargs)

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


@app.post("/api/auth/login")
def login(req: LoginRequest):
    username = req.username.strip()
    if not username or not req.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")

    user = _authenticate_credentials(username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token, expires_at = _create_jwt(user["username"], user["role"])
    return {
        "token": token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": user,
    }


@app.get("/api/session")
def get_session(request: Request):
    username = getattr(request.state, "username", None)
    role = getattr(request.state, "role", _role_for_user(username))
    return {
        "auth_enabled": ASTELL_AUTH_ENABLED,
        "username": username or ("local" if not ASTELL_AUTH_ENABLED else None),
        "role": role,
        "available_roles": ["admin", "employee"],
    }


@app.get("/api/users")
def get_users():
    return {"users": _list_users()}


@app.post("/api/users")
def upsert_user(req: UserUpsertRequest):
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if req.role not in {"admin", "employee"}:
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 employee")

    password_hash = _hash_password(req.password) if req.password else None
    try:
        _upsert_user(username, password_hash, req.role, req.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "users": _list_users()}


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
def get_status(request: Request):
    active_project = get_active_project()
    role = getattr(request.state, "role", "employee")
    return {
        "active_project": active_project["path"] if active_project else "None",
        "active_prefix": active_project["prefix"] if active_project else "None",
        "library_wings": [d for d in os.listdir(LIBRARY_PATH) if d.startswith("wing_")] if os.path.exists(LIBRARY_PATH) else [],
        "all_projects": get_all_projects() if role == "admin" else [],
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


@app.post("/api/project/prefix")
def update_project_prefix(req: ProjectPrefixUpdate):
    new_prefix = req.new_prefix.strip()
    if not new_prefix:
        raise HTTPException(status_code=400, detail="项目前缀不能为空")

    project = get_active_project()
    if not project:
        raise HTTPException(status_code=400, detail="未设置活跃项目")

    output = _call_astell_tool(astell_tools.update_project_prefix, new_prefix)
    add_project(project["path"], new_prefix, bool(project.get("is_mc_project", True)))
    sync_active_project_to_env()
    return {"success": True, "output": output, "prefix": new_prefix}


@app.get("/api/astell/inventory")
def api_astell_inventory():
    output = _call_astell_tool(astell_tools.list_knowledge_inventory)
    return {"output": output}


@app.post("/api/astell/retrieve")
def api_astell_retrieve(req: AstellRetrieveRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="检索问题不能为空")
    output = _call_astell_tool(
        astell_tools.retrieve_astell_knowledge,
        query=req.query.strip(),
        current_project=req.current_project.strip() if req.current_project else None,
        strict_mode=req.strict_mode,
    )
    return {"output": output}


@app.post("/api/astell/trace")
def api_astell_trace(req: AstellTraceRequest):
    trace_type = req.type.strip()
    if trace_type not in {"dev", "problem", "search"}:
        raise HTTPException(status_code=400, detail="type 只能是 dev、problem 或 search")
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="留痕内容不能为空")
    output = _call_astell_tool(
        astell_tools.record_astell_trace,
        type=trace_type,
        content=req.content,
        title=req.title.strip() or "新记录",
    )
    return {"success": True, "output": output}


@app.post("/api/astell/resource")
def api_astell_resource(req: AstellResourceRequest):
    if not req.resource_id.strip():
        raise HTTPException(status_code=400, detail="资源 ID 不能为空")
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="资源描述不能为空")
    output = _call_astell_tool(
        astell_tools.register_resource_id,
        resource_id=req.resource_id.strip(),
        description=req.description.strip(),
        file_path=req.file_path.strip() or "N/A",
    )
    return {"success": True, "output": output}


@app.post("/api/astell/deep-research")
def api_astell_deep_research(req: AstellResearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="研究问题不能为空")
    output = _call_astell_tool(astell_tools.suggest_deep_research, req.query.strip())
    return {"output": output}


@app.get("/api/astell/audit-report")
def api_astell_audit_report():
    output = _call_astell_tool(astell_tools.audit_for_solidification)
    return {"output": output}

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
            try:
                full_dev_path = _resolve_under(get_active_project()["path"], m["dev_path"], must_be_file=True)
                with open(full_dev_path, "r", encoding="utf-8") as file:
                    if "<!-- SOLIDIFY_REJECTED -->" in file.read():
                        continue
            except Exception:
                pass
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


class RejectSolidifyRequest(BaseModel):
    rel_path: str
    reason: str = "暂不固化"


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


@app.post("/api/solidify/reject")
def reject_solidify(req: RejectSolidifyRequest):
    project = get_active_project()
    if not project:
        raise HTTPException(status_code=400, detail="未设置活跃项目")

    full_path = _resolve_under(project["path"], req.rel_path, must_be_file=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    reason = req.reason.strip() or "暂不固化"
    with open(full_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n> <!-- SOLIDIFY_REJECTED --> {timestamp} 管理员暂不固化：{reason}\n")
    return {"success": True}

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
