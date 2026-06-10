import os
import sys
import json
import time
import sqlite3
from datetime import datetime
from pathlib import Path
from astell_config import (
    ASTELL_CONTROL_DB,
    ASTELL_LIBRARY_ROOT,
    MEMPALACE_DB as MEMPALACE_DB_PATH,
    MEMPALACE_SRC as MEMPALACE_SRC_PATH,
    add_runtime_paths,
)

# ==========================================
# 🛑 CRITICAL: MemPalace Environment Setup
# ==========================================
MEMPALACE_SRC = str(MEMPALACE_SRC_PATH)
MEMPALACE_DB = str(MEMPALACE_DB_PATH)
add_runtime_paths()

try:
    from mempalace.searcher import search_memories
    from mempalace.palace import get_collection, get_closets_collection
    from mempalace.miner import process_file, mine
    from mempalace_db.db_helper import add_project
    from modsdk_wing import (
        generate_modsdk_template as generate_modsdk_template_data,
        get_modsdk_best_practices as get_modsdk_best_practices_data,
        review_modsdk_code as review_modsdk_code_data,
        search_modsdk_official as search_modsdk_official_data,
    )
except ImportError as e:
    print(f"Error: Could not import MemPalace from {MEMPALACE_SRC}. Details: {e}")
    sys.exit(1)

# ==========================================
# 🌌 Initialization & Global Constants
# ==========================================
from fastmcp import FastMCP

mcp = FastMCP("Netease_TwinStar_Hub")

import shutil

# ==========================================
# 🚦 Global Constants
# ==========================================
MC_ENV_DISABLED_MSG = "⚠️ 当前工作区未检测到标准的 Minecraft 开发结构（需包含 resource 与 behavior 关键词），Astell MCP 工具已禁用。"

class AstellProjectManager:
    def __init__(self):
        self.active_path = None
        self.active_prefix = "Astell"
        self.file_types = {
            "dev": "开发日志",     # 文件夹
            "info": "信息记录.md",  # 单文件
            "problem": "问题记录", # 文件夹
            "search": "搜索日志.md" # 单文件
        }
        self.sync_with_db()

    def is_mc_environment(self, path=None):
        """
        [环境自检]：检查当前活跃项目路径（或指定路径）下是否同时包含 resource 和 behavior 关键字。
        """
        target = path if path else self.active_path
        if not target or not os.path.exists(target):
            return False
        
        try:
            # 递归检查两层深度，以防项目被包裹在子文件夹中
            for root, dirs, files in os.walk(target):
                # 计算相对于 target 的深度
                depth = root[len(target):].count(os.sep)
                if depth > 1:
                    continue
                
                low_dirs = [d.lower() for d in dirs]
                has_resource = any("resource" in d for d in low_dirs)
                has_behavior = any("behavior" in d for d in low_dirs)
                
                if has_resource and has_behavior:
                    return True
            return False
        except Exception:
            return False

    def sync_with_db(self):
        # 尝试从 SQLite 中读取最新活跃的项目配置以保持同步
        try:
            import sqlite3
            db_path = str(ASTELL_CONTROL_DB)
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                row = cursor.execute("SELECT * FROM projects WHERE last_active > 0 ORDER BY last_active DESC LIMIT 1").fetchone()
                if row:
                    self.active_path = row["path"]
                    self.active_prefix = row["prefix"]
                conn.close()
        except Exception as e:
            print(f"Error syncing with db in AstellProjectManager: {e}")

    def get_filename(self, key):
        self.sync_with_db()
        return f"{self.active_prefix}_{self.file_types.get(key)}"

    def get_filename_local(self, key, prefix=None):
        effective_prefix = prefix if prefix is not None else self.active_prefix
        return f"{effective_prefix}_{self.file_types.get(key)}"

    def set_project(self, path, prefix=None):
        if not os.path.exists(path):
            return f"❌ 路径不存在: {path}"
        
        if not self.is_mc_environment(path):
            return MC_ENV_DISABLED_MSG

        # 自动推断前缀
        if not prefix:
            prefix = os.path.basename(path).replace(" ", "_")

        # 🛑 核心修复：调用 db_helper 的 add_project，确保 last_active 唯一性并落盘
        try:
            add_project(path, prefix, True)
        except Exception as e:
            print(f"Error persisting project switch via db_helper: {e}")

        self.active_path = path
        self.active_prefix = prefix

        status = []
        for key in self.file_types.keys():
            # 初始化阶段严禁再次触发 sync_with_db，否则可能被数据库旧状态回滚
            name = self.get_filename_local(key, prefix=self.active_prefix)
            full_path = os.path.join(path, name)
            
            # 处理文件夹类型 (dev, problem)
            if key in ["dev", "problem"]:
                if not os.path.exists(full_path):
                    os.makedirs(full_path, exist_ok=True)
                    status.append(f"已创建文件夹 {name}")
                else:
                    status.append(f"检测到文件夹 {name}")
            else:
                # 处理单文件类型 (info, search)
                if not os.path.exists(full_path):
                    with open(full_path, "w", encoding="utf-8") as f:
                        if key == "info":
                            f.write("# 📇 信息记录\n\n| 资源ID | 描述 | 路径 | 记录时间 |\n| --- | --- | --- | --- |\n")
                        elif key == "search":
                            f.write("# 🔍 搜索日志\n\n")
                    status.append(f"已创建文件 {name}")
                else:
                    status.append(f"检测到文件 {name}")

        # 二次校验：确认四件套真实落盘后才允许返回成功
        expected_paths = [
            os.path.join(path, self.get_filename_local("dev", prefix=self.active_prefix)),
            os.path.join(path, self.get_filename_local("info", prefix=self.active_prefix)),
            os.path.join(path, self.get_filename_local("problem", prefix=self.active_prefix)),
            os.path.join(path, self.get_filename_local("search", prefix=self.active_prefix)),
        ]
        missing = [p for p in expected_paths if not os.path.exists(p)]
        if missing:
            return "❌ 项目初始化未完成，以下关键记录未成功创建:\n" + "\n".join(missing)

        return f"✅ 网易 MC 项目路径已切换: {path}\n" + "\n".join(status)

    def get_file_path(self, key, sub_filename=None):
        if not self.active_path:
            return None
        base_name = self.get_filename(key)
        if sub_filename and key in ["dev", "problem"]:
            # 确保 sub_filename 以 .md 结尾
            if not sub_filename.endswith(".md"):
                sub_filename += ".md"
            return os.path.join(self.active_path, base_name, sub_filename)
        return os.path.join(self.active_path, base_name)

manager = AstellProjectManager()

# ==========================================
# 🛰️ Core Tool: retrieve_astell_knowledge (取代旧的 verified_research)
# ==========================================

@mcp.tool()
def set_active_project(path: str, prefix: str = None):
    """
    [项目切换/开工契约]：设置当前开发的项目根路径。
    重要：调用此工具是所有工作的起点。AI 必须在获取任务后立即调用此工具，并根据需求自动推断合适的项目前缀（如 NightVisionCookie）。
    强制规则：
    1. 若未先调用本工具，则后续“开发日志 / 问题记录 / 搜索日志 / 信息记录”均视为无效工作。
    2. AI 严禁先口头汇报“已完成”再补调用；必须先完成真实落盘，再汇报。
    3. 返回成功后，才允许进入实现、检索、留痕与固化申请流程。
    """
    if not manager.is_mc_environment(path):
        return MC_ENV_DISABLED_MSG
    return manager.set_project(path, prefix)


@mcp.tool()
def update_project_prefix(new_prefix: str):
    """
    [前缀更新]：当 AI 对项目有了更深的理解后，可以使用此工具重命名当前的记录文件前缀。
    适用场景：仅当项目模块边界已经明确，且希望四件套记录名与真实功能域一致时使用。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    if not manager.active_path:
        return "❌ 尚未设置活跃项目路径。"
    
    old_prefix = manager.active_prefix
    manager.active_prefix = new_prefix
    
    results = [f"🔄 项目前缀从 '{old_prefix}' 更新为 '{new_prefix}'"]
    
    # 尝试重命名现有文件
    for key in manager.file_types.keys():
        old_name = f"{old_prefix}_{manager.file_types[key]}"
        new_name = f"{new_prefix}_{manager.file_types[key]}"
        old_path = os.path.join(manager.active_path, old_name)
        new_path = os.path.join(manager.active_path, new_name)
        
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                results.append(f"✅ 重命名: {old_name} -> {new_name}")
            except Exception as e:
                results.append(f"❌ 重命名失败 {old_name}: {str(e)}")
                
    return "\n".join(results)


@mcp.tool()
def list_knowledge_inventory():
    """
    [知识清单]：列出当前记忆宫殿中存储的所有知识分区（Wings）及其核心覆盖范围。
    在盲目搜索前，建议先调用此工具以了解知识库的边界。
    强制建议：若 AI 打算“凭经验回答”但尚未确认知识库边界，应先调用本工具，再决定是否进行检索。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    inventory = {
        "wing_Project_Memory": "项目级研发记忆：包含所有已结项或开发中的项目日志、架构决策及具体逻辑实现。",
        "wing_Special_Operation_Memory": "专项操作记忆：针对高性能渲染优化、复杂 AI 行为树、网络同步等特定技术攻关的成功案例。",
        "wing_Official_SDK": "网易官方接口文档、事件定义、组件用法（来自 interface.json 和官方手册）。",
        "ModSDK_Official_Tools": "官方 SDK 工具翼：面向网易 MC 的官方资料检索、基础资源模板生成与代码审查辅助。",
        "wing_Stark": "StarkEngine 高级引擎接口、开发规范及特定功能实现。",
        "wing_mod_*": "特定模组的增量记忆（通常在开发中实时固化）。"
    }
    output = ["🏰 [记忆宫殿] 当前知识储备概览：\n"]
    for wing, desc in inventory.items():
        output.append(f"📍 {wing}: {desc}")
    output.append("\n提示：若需查询具体技术细节，请使用 `retrieve_astell_knowledge`。")
    return "\n".join(output)


@mcp.tool()
def record_astell_trace(type: str, content: str, title: str = "新记录"):
    """
    [原子化留痕 - 严禁口头汇报]
    凡涉及：1.实现功能 2.产生报错 3.知识空白，必须调用。
    - type: 'dev' (开发日志), 'problem' (问题记录), 'search' (搜索日志)
    - title: 必须是模块名（如: Texture_Fix）。对于 dev/problem，系统将创建同名原子文件。
    - content: 必须包含具体代码或排查结论。
    注意：如果此工具未被调用，人类将判定 AI 任务失败。
    强制工作流：
    1. 完成功能后立即写 dev。
    2. 遇到报错或异常后立即写 problem。
    3. 检索无果、知识库为空时立即写 search。
    4. 不允许只在对话里总结，而不产生物理文件。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    # 对于 dev 和 problem 类型，title 将作为子文件名
    if type in ["dev", "problem"]:
        path = manager.get_file_path(type, sub_filename=title)
        display_name = f"{manager.get_filename(type)}/{title}.md"
    else:
        path = manager.get_file_path(type)
        display_name = manager.get_filename(type)

    if not path:
        return "❌ 尚未设置活跃项目路径，请先调用 set_active_project。未开工契约前，所有留痕均无效。"
    
    # 强制检查 content 是否有实质性内容
    normalized_content = content.strip()
    if len(normalized_content) < 30:
        return (
            "❌ 留痕内容过短，已拒绝写入。"
            "\n要求：至少 30 个字符，且必须包含具体代码、修改说明、报错现象、排查结论之一。"
            "\n错误示例：'已修复'、'处理完成'、'查过了没问题'。"
            "\n正确示例：'将 food 组件的 on_use 回调改为添加 night_vision 效果，持续 200 tick，并同步更新客户端纹理引用。'"
        )

    if type in ["dev", "problem"] and title.strip() == "新记录":
        return "❌ dev/problem 类型禁止使用默认标题“新记录”。请将 title 明确写为模块名，如 Texture_Fix、NightVisionCookie、EffectSync。"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    mode = "a" if os.path.exists(path) else "w"
    with open(path, mode, encoding="utf-8") as f:
        if type == "dev":
            if mode == "w": f.write(f"# 📜 开发日志: {title}\n\n")
            f.write(f"## [{timestamp}] 记录\n")
            f.write(f"{normalized_content}\n")
            f.write("-" * 20 + "\n")
        elif type == "problem":
            if mode == "w": f.write(f"# ⚠️ 问题记录: {title}\n\n")
            f.write(f"### [{timestamp}] 故障描述 (状态: 尝试中)\n")
            f.write(f"{normalized_content}\n")
            f.write("\n> 解决尝试记录请通过后续追加更新。\n")
        elif type == "search":
            f.write(f"- [{timestamp}] 搜索空白: {title} | 上下文建议: {normalized_content}\n")
            
    return f"✅ [Astell 守则已履行] 成功计入 {display_name}"


@mcp.tool()
def register_resource_id(resource_id: str, description: str, file_path: str = "N/A"):
    """
    [资源注册]：将新定义的 ID (如实体ID、物品ID) 存入信息记录，自带重复校验。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    path = manager.get_file_path("info")
    if not path:
        return "❌ 尚未设置活跃项目路径。"
    
    # 重复校验
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            if resource_id in f.read():
                return f"⚠️ 冲突：资源 ID '{resource_id}' 已存在于记录中，请检查是否重复定义。"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"| {resource_id} | {description} | {file_path} | {timestamp} |\n")
        
    return f"✅ 资源 ID '{resource_id}' 已注册。"


@mcp.tool()
def suggest_deep_research(query: str):
    """
    [深度检索建议]：当常规搜索无法找到满意答案时，生成一个深度研究提示词供用户在主对话或新任务中使用。
    由于不再依赖外部 Cline 调度器，此工具现在改为生成高质量的研究建议。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    research_prompt = (
        f"🔍 [深度研究建议]\n"
        f"当前的常规检索未能找到关于 '{query}' 的详细信息。\n\n"
        f"建议主代理执行以下步骤：\n"
        f"1. 扩大搜索范围至整个 `Library/` 目录，特别是 `wing_Project_Memory`、`wing_Special_Operation_Memory` 和 `wing_Official_SDK`。\n"
        f"2. 检查 `mempalace_db` 中相关的原始文本段落。\n"
        f"3. 若仍无果，请尝试搜索相似功能的实现逻辑（如同类组件的初始化逻辑）。\n\n"
        f"你可以将此提示词复制到新任务中以启动深度分析。"
    )
    
    # 同时在搜索日志中留痕，方便后续固化
    record_astell_trace(
        type="search",
        title=f"深度研究建议: {query}",
        content="常规检索无果，已生成深度研究引导。"
    )
    
    return research_prompt


@mcp.tool()
def open_control_tower():
    """
    [控制塔启动]：在浏览器中打开 Astell MCP 可视化控制塔。
    用于人工审查待固化请求、查看项目状态以及管理知识库。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    # 设置环境变量供 UI 服务器感知状态
    os.environ["ASTELL_ACTIVE_PROJECT"] = manager.active_path or "None"
    os.environ["ASTELL_ACTIVE_PREFIX"] = manager.active_prefix or "None"
    
    import subprocess
    ui_script = ASTELL_LIBRARY_ROOT / "mcp_ui_server.py"
    
    # 异步启动 UI 服务器
    subprocess.Popen([sys.executable, str(ui_script)], creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0)
    
    return "🏰 Astell 控制塔已在后台启动。正在为你打开浏览器界面，请在其中进行人工审批。"


@mcp.tool()
def solidify_memory():
    """
    [记忆固化申请]：提醒人类通过控制塔 UI 对当前项目的开发记录进行物理固化。
    注意：AI Agent 严禁直接修改 Library 知识库。所有入库操作必须经过人类在 UI 界面中的“记忆审查”手动批准。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    if not manager.active_path:
        return "❌ 尚未设置活跃项目路径。"

    prompt = (
        f"🛡️ [固化安全拦截]\n"
        f"项目 '{manager.active_prefix}' 的阶段性开发记录已准备好入库。\n\n"
        f"⚠️ 根据安全规程，AI Agent 无权直接对 Library 分区执行物理写操作。\n"
        f"请人类执行以下操作：\n"
        f"1. 调用 `open_control_tower` 打开可视化控制塔。\n"
        f"2. 进入“记忆审批 (Memory Audit)”视图。\n"
        f"3. 审查待处理的固化提案，过滤冗余信息后点击“立即物理固化入库”。\n\n"
        f"只有经过人类审计的经验才具有长期的参考价值。"
    )
    
    return prompt




@mcp.tool()
def audit_for_solidification():
    """
    [固化审计]：在发起人工固化前，对比开发日志文件夹与问题记录文件夹，通过同名原子文件进行交叉逻辑审计。
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    dev_dir = manager.get_file_path("dev")
    prob_dir = manager.get_file_path("problem")
    search_path = manager.get_file_path("search")
    
    if not dev_dir or not os.path.exists(dev_dir):
        return "❌ 尚未设置活跃项目路径或开发日志文件夹不存在。"
        
    report = [f"🔍 [原子化固化审计报告] 项目: {manager.active_prefix}\n"]
    report.append("-" * 30)

    modules = []
    if os.path.exists(dev_dir):
        for f in os.listdir(dev_dir):
            if f.endswith(".md"):
                m_name = f[:-3]
                # 交叉审计：寻找同名问题记录
                prob_file = os.path.join(prob_dir, f)
                status = "✅ 可固化"
                reason = "无挂起报错"
                
                if os.path.exists(prob_file):
                    with open(prob_file, "r", encoding="utf-8") as pf:
                        content = pf.read()
                        if "状态: 尝试中" in content or "未解决" in content:
                            status = "❌ 拦截"
                            reason = "存在未闭环报错"
                        else:
                            reason = "报错已闭环"
                
                # 检查不可信标记
                with open(os.path.join(dev_dir, f), "r", encoding="utf-8") as df:
                    if "UNTRUSTWORTHY" in df.read():
                        status = "🚫 拦截"
                        reason = "人工标记为不可信"

                modules.append(f"- [{m_name}] {status} ({reason})")

    if not modules:
        report.append("ℹ️ 未发现任何原子开发日志。")
    else:
        report.append("📂 模块审计清单：")
        report.extend(modules)

    # 检索搜索日志中的空白
    if os.path.exists(search_path):
        with open(search_path, "r", encoding="utf-8") as f:
            gaps = [l.strip() for l in f.readlines() if "搜索空白" in l]
            if gaps:
                report.append(f"\n💡 知识空白补充（来自搜索日志）：")
                report.extend(gaps[:3])
        
    report.append("\n⚖️ 结论：请人类通过控制塔 UI 的“工作区记录”视图进行终审。只有 ✅ 标记且经人工核对的模块才建议执行物理入库。")
    return "\n".join(report)


@mcp.tool()
def retrieve_astell_knowledge(query: str, current_project: str = None, strict_mode: bool = False):
    """
    [智能检索]：从向量库中提取官方 SDK 或历史项目经验。
    注意：如果检索结果为空，AI 必须立即调用 record_astell_trace(type='search') 记录该知识空白，严禁盲猜 API！
    """
    if not manager.is_mc_environment():
        return MC_ENV_DISABLED_MSG
        
    # 解除一切对主脑的智障拦截限制。
    
    # 校准真实的、存在于 Astell_Library 中的知识库分区
    # wing_Project_Memory 存放项目日志与决策
    # wing_Special_Operation_Memory 存放专项技术攻坚成功案例
    # wing_Official_SDK 存放了网易官方的接口文档
    # wing_Stark 存放了starkengine的强大功能接口和开发规范
    active_wings = ["wing_Project_Memory", "wing_Special_Operation_Memory", "wing_Official_SDK", "wing_Stark"]
    
    if current_project:
        # 针对当前正在写的模块进行上下文检索（如果有固化过内容）
        active_wings.append(f"wing_mod_{current_project}")
        
    all_results = []
    # MemPalace 默认采用余弦或 L2 距离，越小越相似。0.5 在宽泛模式下能捞出更多结果。
    max_dist = 0.35 if strict_mode else 0.55
    
    for wing in active_wings:
        try:
            results_dict = search_memories(
                query=query,
                palace_path=MEMPALACE_DB,
                wing=wing,
                n_results=5,
                max_distance=max_dist
            )
            hits = results_dict.get("results", [])
            all_results.extend(hits)
        except Exception as e:
            print(f"[Astell] Search error in wing {wing}: {e}")
            continue

    if not all_results:
        auto_trace_note = "⚠️ 自动留痕失败。"
        search_path = manager.get_file_path("search")
        duplicate_found = False

        if search_path and os.path.exists(search_path):
            try:
                with open(search_path, "r", encoding="utf-8") as f:
                    recent_lines = f.readlines()[-20:]
                duplicate_found = any("搜索空白" in line and query in line for line in recent_lines)
            except Exception as e:
                print(f"[Astell] Failed to inspect search log for duplicates: {e}")

        if duplicate_found:
            auto_trace_note = "ℹ️ 已检测到同主题搜索空白记录，已跳过重复留痕。"
        else:
            trace_result = record_astell_trace(
                type="search",
                title=query,
                content=(
                    f"检索主题: {query}；"
                    f"检索范围: {', '.join(active_wings)}；"
                    f"检索模式: {'精准' if strict_mode else '宽泛'}；"
                    f"当前知识库未命中合适示例，可在后续实现完成后评估是否将该开发日志作为新增方法进行固化。"
                )
            )
            auto_trace_note = f"📝 已自动记录搜索日志：{trace_result}"

        return (f"🔮 [记忆宫殿] 检索完成。在现有知识库中未找到关于 '{query}' 的相关记忆。\n"
                f"{auto_trace_note}\n"
                f"💡 建议：\n"
                f"1. 若该功能极度重要，调用 `suggest_deep_research` 获取深度搜索建议。\n"
                f"2. 后续若成功实现，请在开发完成后补充对应模块的开发日志，供人工审查是否固化。")

    # 修复破败的优先级排序字典（让精华教程优先级最高）
    priority = {
        "wing_Project_Memory": 1,
        "wing_Special_Operation_Memory": 2,
        "wing_Official_SDK": 3,
        "wing_Stark": 4,
        "wing_mod_Current_Project": 5
    }
    
    # 按照知识库优先级，以及相似度距离（distance越小越精准）进行综合排序
    all_results.sort(key=lambda x: (priority.get(x.get("wing", "Unknown"), 9), x.get("similarity", 9.9)))
    
    output = [f"📚 [记忆宫殿] 检索结果: '{query}' (模式: {'精准' if strict_mode else '宽泛'})\n"]
    
    # 限制返回篇幅以防爆掉 Token 窗口，最多返回前 4 个高质量片段
    for i, hit in enumerate(all_results[:4], 1):
        source = hit.get("source_file", "?")
        wing = hit.get("wing", "?")
        text = hit.get("text", "").strip()
        dist = hit.get("similarity", 9.9)
        
        # 将距离转换为更直观的置信度 (0.0 -> 100%, 1.0 -> 0%)
        confidence = max(0, int((1.0 - dist) * 100))
        label = "🔥 最优匹配" if i == 1 and confidence > 70 else f"📑 相关参考 {i}"
        
        output.append(f"{label} [{wing}] -> {source} (匹配度: {confidence}%)")
        
        # 简单判断是否包含代码块，增强 Cline 对代码的识别能力
        if "def " in text or "class " in text or "import " in text or "{" in text:
            output.append("```python")
            output.append(text)
            output.append("```")
        else:
            output.append(text)
            
        output.append("-" * 30)

    output.append("\n💡 提示：如果以上内容解决了你的问题，请直接应用。如果未找到目标 API，请考虑库中可能尚未收录该特定细节。")
    return "\n".join(output)


def _format_modsdk_search(data):
    results = data.get("results", [])
    if not results:
        return f"📘 [ModSDK 官方工具翼] 未找到与 `{data.get('query')}` 相关的官方资料。"

    lines = [
        f"📘 [ModSDK 官方工具翼] 查询: {data.get('query')} | scope={data.get('scope')}",
        "",
    ]
    for idx, item in enumerate(results, 1):
        lines.append(f"{idx}. {item['path']} (score={item['score']})")
        lines.append(item["snippet"])
        lines.append("-" * 30)
    return "\n".join(lines)


@mcp.tool()
def search_modsdk_official(query: str, scope: str = "docs", limit: int = 5):
    """
    [官方 SDK 工具翼 / 检索]：从本地 wing_Official_SDK 中检索网易 MC / Bedrock 官方资料。
    scope 可用 docs/api/event；该工具只负责查官方资料，不写项目日志。
    """
    data = search_modsdk_official_data(query=query, scope=scope, limit=limit)
    return _format_modsdk_search(data)


@mcp.tool()
def generate_modsdk_template(kind: str, identifier: str, namespace: str = "astell", display_name: str = None):
    """
    [官方 SDK 工具翼 / 模板]：生成常见行为包与资源包 JSON 草稿。
    kind 支持 item/block/entity/recipe/loot_table/spawn_rule/food/sword/pickaxe/axe/shovel/hoe/armor/bow/throwable。
    注意：该工具只返回文件草稿，不直接写盘；落地后必须 register_resource_id 并 record_astell_trace。
    """
    try:
        data = generate_modsdk_template_data(kind, identifier, namespace, display_name)
    except ValueError as e:
        return f"❌ 模板生成失败: {e}"

    lines = [
        f"🧩 [ModSDK 模板草稿] {data['kind']} -> {data['identifier']}",
        f"显示名: {data['display_name']}",
        "",
    ]
    for file in data["files"]:
        lines.append(f"### {file['path']}")
        lines.append("```json" if file["path"].endswith(".json") else "```text")
        lines.append(file["content"])
        lines.append("```")
    lines.append("后续动作:")
    lines.extend(f"- {step}" for step in data["next_steps"])
    return "\n".join(lines)


@mcp.tool()
def review_modsdk_code(code: str, filename: str = "snippet.py"):
    """
    [官方 SDK 工具翼 / 审查]：按网易 MC ModSDK 常见坑检查代码片段，尤其关注 Python 2.7、事件注册和高频路径。
    """
    data = review_modsdk_code_data(code)
    lines = [f"🔎 [ModSDK 代码审查] {filename}", data["summary"], ""]
    if data["findings"]:
        for finding in data["findings"]:
            lines.append(f"- [{finding['severity']}] {finding['title']}: {finding['detail']}")
    else:
        lines.append("- 未发现明显规则命中。")
    lines.append("")
    lines.append("建议基线:")
    lines.extend(f"- {rule}" for rule in data["best_practices"])
    return "\n".join(lines)


@mcp.tool()
def get_modsdk_best_practices(topic: str = "general"):
    """
    [官方 SDK 工具翼 / 规范]：获取网易 MC ModSDK 开发建议。topic 可用 general/event/performance/python2/resource。
    """
    data = get_modsdk_best_practices_data(topic)
    lines = [f"📏 [ModSDK 最佳实践] topic={data['topic']}"]
    lines.extend(f"- {rule}" for rule in data["rules"])
    lines.append(f"可用 topic: {', '.join(data['available_topics'])}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
