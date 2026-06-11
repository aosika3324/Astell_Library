# Astell Library - 灰之魔女的星界工坊 (简约重构版)

这是一个基于 **Astell 极致开发核心规章** 建立的纯粹知识中枢工作区。
当前架构已进行全面极简重构，剥离了繁重的多级子代理框架（已存档入 Legacy），专注于提供**零幻觉、高精度的网易我的世界 (NetEase Minecraft) 知识检索**服务。

---

## ⚡ 快速开始 (换设备一键部署)

只需几步即可在任何新设备上启动这个强大的 MCP 知识库中枢：

### 1. 环境准备
确保你的设备上已安装 **Python 3.10+**。

### 2. 安装核心依赖
在终端中运行以下命令，安装运行 MCP 服务器和记忆宫殿所需的关键依赖：
```bash
pip install fastmcp
# MemPalace (记忆库引擎) 相关核心依赖
pip install chromadb sentence-transformers pydantic
```
*(注：如果有更深度的需要，可参考 `mempalace-develop` 目录使用 `pip install -e ./mempalace-develop` 进行完整本地挂载安装)*

### 3. 运行配置与挂载
当前作为 Cline 的 MCP Server 挂载，在 Cline 界面中配置自定义 MCP Server，指向 `mcp_server.py` 即可。Cline 会自动通过 `fastmcp` 与其通信。

---

## 📂 极简架构说明

| 文件 / 目录 | 核心作用 |
| :--- | :--- |
| **`.clinerules`** | **[绝对核心]** Astell 全局开发约束准则。规定了 AI 在本目录必须遵守的规则（如强制读写进度文档、严禁捏造 API、多用检索等）。 |
| **`mcp_server.py`** | 纯净的情报枢纽 MCP Server。仅暴露 `retrieve_astell_knowledge` 检索工具，让 AI 直接从向量记忆库中提取避坑指南和官方 SDK。 |
| **`mempalace_db/`** | 存放着 ChromaDB 向量数据库，这是真正的“记忆宫殿”，储存了历代开发的血泪教训与结晶。 |
| **`Library/`** | 知识库原文存放地。包含 `wing_Golden_Tutorials` (避坑教学) 和 `wing_Official_SDK` (官方文档)。 |
| **`Legacy_Astell_SubAgent_System/`** | **[已封存]** 旧版多级子代理调度框架和可视化 Dashboard 仪表盘代码。供未来演进参考。 |

---

## 🖥️ 服务化控制台

Astell 可以作为 Web 控制台部署，入口为 `mcp_ui_server.py`。控制台包含管理员和员工视图：员工可查官方 SDK、检索 Astell 知识、写入项目留痕、登记资源 ID；管理员额外可切换项目、更新项目前缀、审查固化、标记不可信记录和打包知识库。

Docker/Caddy 部署建议从容器目录初始化环境：

```bash
cd deploy/container
bash ./init_env.sh astell.example.com admin 'AdminPassword' admin@example.com employee 'EmployeePassword'
docker compose up -d --build
```

多账号由 SQLite 用户表和前端 JWT 登录处理。`.env` 中的账号配置只用于首次启动或重置时写入/更新用户表：

```dotenv
ASTELL_AUTH_USER=admin
ASTELL_AUTH_PASSWORD_SHA256=<admin-password-sha256>
ASTELL_AUTH_USERS_SHA256=admin:<admin-password-sha256>:admin,employee:<employee-password-sha256>:employee
ASTELL_ADMIN_USERS=admin
ASTELL_EMPLOYEE_USERS=employee
ASTELL_JWT_SECRET=<stable-random-secret>
ASTELL_JWT_EXPIRE_MINUTES=720
ASTELL_AUTH_BOOTSTRAP_MODE=seed
```

---

## 🏰 MemPalace 记忆宫殿运作机制

当前系统抛弃了让 AI 盲目扫描庞大项目的低效方式，而是通过 MCP 工具 `retrieve_astell_knowledge` 进行精准的“向量记忆召回”。

*   **提纯与检索**：遇到问题时，AI 会从 `mempalace_db` 中精准召回带有相似度距离排序的高质量笔记或代码片段。
*   **知识分区 (Wings)**：
    *   **`wing_Golden_Tutorials`**：存放高浓度的踩坑指南（如矿石种植防闪现、实体 AI 避坑）。
    *   **`wing_Official_SDK`**：网易官方的纯净 API 文档。

遵循 `.clinerules` 约束，开发过程中积累的所有错误与解决思路，最终都将被固化至这里，成为永不遗忘的财富。

---

## 🏰 记忆固化与 AAKK 提纯 (Memory Solidification)

为了防止 AI 产生长上下文幻觉，系统采用了 **“双层记忆存储”** 架构。AI 必须理解如何将新知识“固化”：

### 1. 双层存储：Drawer vs Closet
- **Drawer (抽屉)**：存放原汁原味的源码、带有“便利贴注释”的 JSON 和完整的 `.md` 开发日志。这是知识的**原文层**。
- **Closet (壁橱/AAKK)**：通过 AI 对原文进行“脱水提纯”生成的压缩摘要。这是知识的**意义层**。

### 2. 什么是 AAKK？
**AAKK (Astell Architecture Knowledge Kernel)** 是记忆宫殿的核心。它不记录代码细节，而是记录“这段代码解决了什么问题”、“有哪些核心 ID”、“有什么避坑经验”。

### 3. 如何执行固化 (AI 必读)
当你（AI）完成了一个阶段性的开发任务，并已将相关文档和带注释的代码放入对应的 `drawer` 文件夹后，**必须执行正统的固化动作**：

- **正统入口**：**禁止**自己编写文件遍历逻辑或直接循环调用底层的 `process_file`。必须调用 `mempalace.miner.mine()` 标准入口。
- **推荐工具**：直接运行 **`Astell_Scripts/MemPalace_Tests/official_mine_wings.py`**。该脚本已配置好对当前所有 Wing 的全量增量维护。
- **固化流程**：
  1. 将文件/代码拷贝至 `Library/wing_.../room_.../drawer/`。
  2. 运行 `official_mine_wings.py` 脚本。
  3. 系统会自动完成：扫描 -> 识别 Wing/Room -> **检测 mtime 修改时间 (自动跳过未修改文件)** -> 触发 AAKK 提纯 -> 入库。

**检索逻辑**：在使用 `retrieve_astell_knowledge` 时，系统会优先在 `Closet` (AAKK) 中进行“语义共鸣”，匹配成功后再精准调取 `Drawer` 里的原文。这种“以意找位，以位拿文”的机制是杜绝幻觉的终极手段。
