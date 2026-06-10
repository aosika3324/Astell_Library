const state = {
    role: localStorage.getItem("astell.role") || "employee",
    session: null,
    status: null,
    pending: [],
    selectedPending: -1,
    workspace: [],
    selectedWorkspace: -1,
    libraryTree: [],
    expandedPaths: new Set(),
    selectedLibraryFile: null,
    users: [],
    health: null,
    ready: null,
};

const titles = {
    dashboard: "总览",
    projects: "项目与成员",
    audit: "记忆审查",
    workspace: "项目记录",
    astell: "Astell 工具翼",
    library: "知识库",
    modsdk: "官方 SDK",
    system: "系统状态",
    guide: "工作规范",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.remove("hidden");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3600);
}

async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const text = await res.text();
    let data = {};
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            data = { detail: text };
        }
    }
    if (!res.ok) {
        throw new Error(data.detail || `${res.status} ${res.statusText}`);
    }
    return data;
}

function postJson(url, payload) {
    return fetchJson(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function isAdmin() {
    return state.role === "admin";
}

function setRole(role, { fromSession = false } = {}) {
    const sessionRole = state.session?.role || "employee";
    if (!fromSession && role === "admin" && sessionRole !== "admin") {
        showToast("当前账号不是管理员，不能切换到管理员视图。");
        role = "employee";
    }

    state.role = role;
    localStorage.setItem("astell.role", role);

    $$("[data-role-option]").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.roleOption === role);
    });

    $$("[data-admin-only]").forEach((el) => {
        el.classList.toggle("hidden", role !== "admin");
    });

    $$("[data-admin-action]").forEach((el) => {
        el.disabled = role !== "admin";
        el.title = role === "admin" ? "" : "需要管理员角色";
    });

    setText("session-role", role === "admin" ? "管理员" : "员工");

    const activeView = $(".view.is-active")?.id?.replace("view-", "") || "dashboard";
    if (role !== "admin" && $(`#view-${activeView}`)?.hasAttribute("data-admin-only")) {
        switchView("dashboard");
    }
}

function switchView(view) {
    const target = $(`#view-${view}`);
    if (!target) return;
    if (target.hasAttribute("data-admin-only") && !isAdmin()) {
        showToast("该页面需要管理员角色。");
        view = "dashboard";
    }

    $$(".view").forEach((el) => el.classList.toggle("is-active", el.id === `view-${view}`));
    $$(".nav-item").forEach((btn) => btn.classList.toggle("is-active", btn.dataset.view === view));
    setText("page-title", titles[view] || "Astell");

    if (view === "workspace") loadWorkspace();
    if (view === "library") loadLibrary();
    if (view === "audit" && isAdmin()) loadPending();
    if (view === "projects" && isAdmin()) loadUsers();
    if (view === "system") loadHealth();
}

function renderOverview() {
    const activeProject = state.status?.active_project || "None";
    const activePrefix = state.status?.active_prefix || "None";
    const wings = state.status?.library_wings || [];

    setText("sidebar-project", activePrefix !== "None" ? activePrefix : "未连接");
    setText("metric-project", activePrefix !== "None" ? activePrefix : "未连接");
    setText("metric-prefix", `path: ${activeProject}`);
    setText("metric-pending", String(state.pending.length));
    setText("nav-pending-count", String(state.pending.length));
    setText("metric-wings", String(wings.length));
    setText("metric-wing-list", wings.length ? wings.slice(0, 3).join(", ") : "暂无分区");
    setText("metric-service", state.health?.status === "ok" ? "在线" : "检查中");
    setText("metric-ready", `readyz: ${state.ready?.status || "-"}`);
    renderProjectTable();
}

function renderProjectTable() {
    const container = $("#project-table");
    if (!container) return;
    const projects = state.status?.all_projects || [];
    if (!projects.length) {
        container.innerHTML = `<div class="empty-state">还没有接入项目</div>`;
        return;
    }

    container.innerHTML = projects.map((item) => {
        const active = item.last_active > 0 ? "当前" : "历史";
        return `
            <div class="table-row">
                <div>
                    <strong>${escapeHtml(item.prefix || "未命名")}</strong>
                    <small>${escapeHtml(item.path || "")}</small>
                </div>
                <span class="status-pill ${item.is_mc_project ? "ok" : "warn"}">${item.is_mc_project ? "MC 项目" : "普通项目"}</span>
                <span class="status-pill ${item.last_active > 0 ? "ok" : ""}">${active}</span>
            </div>`;
    }).join("");
}

async function loadSession() {
    try {
        state.session = await fetchJson("/api/session");
    } catch {
        state.session = { username: "unknown", role: "employee", auth_enabled: true };
    }

    setText("session-user", state.session.username || "unknown");
    const initialRole = state.session.role === "admin" ? state.role : "employee";
    setRole(initialRole, { fromSession: true });
}

async function loadHealth() {
    try {
        state.health = await fetchJson("/healthz");
    } catch (e) {
        state.health = { status: "error", detail: e.message };
    }

    try {
        state.ready = await fetchJson("/readyz");
    } catch (e) {
        state.ready = { status: "not_ready", detail: e.message };
    }

    renderSystemHealth();
    renderOverview();
}

function renderSystemHealth() {
    const container = $("#system-health");
    if (!container) return;
    const checks = state.ready?.checks || {};
    const rows = [
        ["healthz", state.health?.status || "error"],
        ["readyz", state.ready?.status || "not_ready"],
        ["library", String(checks.library ?? "-")],
        ["mempalace_db", String(checks.mempalace_db ?? "-")],
        ["control_db", String(checks.control_db ?? "-")],
        ["auth", state.session?.auth_enabled ? "enabled" : "disabled"],
    ];
    container.innerHTML = rows.map(([name, value]) => {
        const ok = ["ok", "ready", "true", "enabled"].includes(String(value));
        return `<div class="status-item"><strong>${name}</strong><span class="status-pill ${ok ? "ok" : "warn"}">${value}</span></div>`;
    }).join("");
}

async function loadStatus() {
    state.status = await fetchJson("/api/status");
    renderOverview();
}

async function loadPending() {
    if (!isAdmin()) {
        state.pending = [];
        state.selectedPending = -1;
        renderOverview();
        return;
    }
    try {
        const data = await fetchJson("/api/pending");
        state.pending = data.pending || [];
        if (state.selectedPending >= state.pending.length) state.selectedPending = -1;
        renderPending();
        renderOverview();
    } catch (e) {
        showToast(`加载待审失败：${e.message}`);
    }
}

async function loadUsers() {
    if (!isAdmin()) {
        state.users = [];
        renderUsers();
        return;
    }
    try {
        const data = await fetchJson("/api/users");
        state.users = data.users || [];
        renderUsers();
    } catch (e) {
        showToast(`成员列表加载失败：${e.message}`);
    }
}

function renderUsers() {
    const container = $("#user-table");
    if (!container) return;
    if (!state.users.length) {
        container.innerHTML = `<div class="empty-state">未读取到成员配置</div>`;
        return;
    }
    container.innerHTML = state.users.map((user) => `
        <div class="table-row compact-table-row">
            <div>
                <strong>${escapeHtml(user.username)}</strong>
                <small>由环境变量配置，修改后需要重启服务</small>
            </div>
            <span class="status-pill ${user.role === "admin" ? "ok" : ""}">${user.role === "admin" ? "管理员" : "员工"}</span>
        </div>`).join("");
}

function renderPending() {
    const list = $("#pending-list");
    if (!list) return;
    if (!state.pending.length) {
        list.innerHTML = `<div class="empty-state">暂无待审固化</div>`;
        clearAuditDetail();
        return;
    }

    list.innerHTML = "";
    state.pending.forEach((item, index) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `list-card ${state.selectedPending === index ? "is-active" : ""}`;
        btn.innerHTML = `
            <strong>${escapeHtml(item.title || "未命名记录")}</strong>
            <small>${escapeHtml(item.type || "module")} · ${escapeHtml(item.rel_path || "")}</small>`;
        btn.addEventListener("click", () => selectPending(index));
        list.appendChild(btn);
    });
}

function selectPending(index) {
    state.selectedPending = index;
    renderPending();
    const item = state.pending[index];
    $("#audit-empty").classList.add("hidden");
    $("#audit-detail").classList.remove("hidden");
    setText("audit-type", item.type || "module");
    setText("audit-title", item.title || "未命名记录");
    setText("audit-content", item.content || "");
}

function clearAuditDetail() {
    $("#audit-empty")?.classList.remove("hidden");
    $("#audit-detail")?.classList.add("hidden");
}

async function approveSolidify() {
    if (!isAdmin()) return showToast("需要管理员角色。");
    const item = state.pending[state.selectedPending];
    if (!item) return;
    try {
        const result = await postJson("/api/solidify/execute", {
            rel_path: item.rel_path,
            module_name: item.module_name,
        });
        showToast(`固化成功：${result.copied_count || 0} 个文件`);
        state.selectedPending = -1;
        await Promise.all([loadPending(), loadLibrary()]);
    } catch (e) {
        showToast(`固化失败：${e.message}`);
    }
}

async function rejectSolidify() {
    if (!isAdmin()) return showToast("需要管理员角色。");
    const item = state.pending[state.selectedPending];
    if (!item) return;
    try {
        await postJson("/api/solidify/reject", {
            rel_path: item.rel_path,
            reason: "管理员在控制台选择暂不固化",
        });
        showToast("已标记为暂不固化。");
        state.selectedPending = -1;
        await loadPending();
    } catch (e) {
        showToast(`暂不固化失败：${e.message}`);
    }
}

async function loadWorkspace() {
    try {
        const data = await fetchJson("/api/workspace/modules");
        state.workspace = data.modules || [];
        if (state.selectedWorkspace >= state.workspace.length) state.selectedWorkspace = -1;
        renderWorkspace();
    } catch (e) {
        showToast(`加载项目记录失败：${e.message}`);
    }
}

function renderWorkspace() {
    const list = $("#workspace-list");
    if (!list) return;
    if (!state.workspace.length) {
        list.innerHTML = `<div class="empty-state">当前项目还没有记录</div>`;
        clearWorkspaceDetail();
        return;
    }

    list.innerHTML = "";
    state.workspace.forEach((item, index) => {
        const btn = document.createElement("button");
        const status = item.is_untrustworthy ? "不可信" : item.has_prob && !item.prob_resolved ? "有问题" : "可信";
        btn.type = "button";
        btn.className = `list-card ${state.selectedWorkspace === index ? "is-active" : ""}`;
        btn.innerHTML = `
            <strong>${escapeHtml(item.name || "未命名模块")}</strong>
            <small>${status} · ${item.has_dev ? "DEV" : "-"} ${item.has_prob ? "PROB" : ""}</small>`;
        btn.addEventListener("click", () => selectWorkspace(index));
        list.appendChild(btn);
    });
}

async function selectWorkspace(index) {
    state.selectedWorkspace = index;
    renderWorkspace();
    const item = state.workspace[index];

    $("#workspace-empty").classList.add("hidden");
    $("#workspace-detail").classList.remove("hidden");
    setText("workspace-title", item.name || "未命名模块");
    renderWorkspaceBadges(item);
    setText("workspace-dev", "加载中...");
    setText("workspace-prob", item.has_prob ? "加载中..." : "无问题记录");

    try {
        if (item.has_dev) {
            const data = await fetchJson(`/api/workspace/read?rel_path=${encodeURIComponent(item.dev_path)}`);
            setText("workspace-dev", data.content || "");
        } else {
            setText("workspace-dev", "暂无开发日志");
        }
        if (item.has_prob) {
            const data = await fetchJson(`/api/workspace/read?rel_path=${encodeURIComponent(item.prob_path)}`);
            setText("workspace-prob", data.content || "");
        }
    } catch (e) {
        showToast(`读取记录失败：${e.message}`);
    }
}

function renderWorkspaceBadges(item) {
    const badges = [];
    if (item.is_untrustworthy) badges.push(`<span class="badge bad">不可信</span>`);
    else if (item.has_prob && !item.prob_resolved) badges.push(`<span class="badge warn">问题未解决</span>`);
    else badges.push(`<span class="badge ok">可固化候选</span>`);
    if (item.has_dev) badges.push(`<span class="badge">开发日志</span>`);
    if (item.has_prob) badges.push(`<span class="badge">问题记录</span>`);
    $("#workspace-badges").innerHTML = badges.join("");
}

function clearWorkspaceDetail() {
    $("#workspace-empty")?.classList.remove("hidden");
    $("#workspace-detail")?.classList.add("hidden");
}

async function markWorkspaceUntrustworthy() {
    if (!isAdmin()) return showToast("需要管理员角色。");
    const item = state.workspace[state.selectedWorkspace];
    if (!item) return;
    const path = item.has_dev ? item.dev_path : item.prob_path;
    try {
        await postJson("/api/workspace/tag", { rel_path: path, tag: "untrustworthy" });
        showToast("已标记为不可信。");
        await loadWorkspace();
    } catch (e) {
        showToast(`标记失败：${e.message}`);
    }
}

async function loadLibrary() {
    try {
        const data = await fetchJson("/api/library/tree");
        state.libraryTree = data.tree || [];
        renderLibrary();
    } catch (e) {
        showToast(`加载知识库失败：${e.message}`);
    }
}

function renderLibrary() {
    const tree = $("#library-tree");
    if (!tree) return;
    if (!state.libraryTree.length) {
        tree.innerHTML = `<div class="empty-state">知识库为空</div>`;
        return;
    }
    tree.innerHTML = "";
    renderTreeNodes(state.libraryTree, tree, 0);
}

function renderTreeNodes(nodes, parent, level) {
    nodes.forEach((node) => {
        const row = document.createElement("div");
        row.className = "tree-row";
        row.style.paddingLeft = `${10 + level * 16}px`;

        const icon = node.is_dir ? (state.expandedPaths.has(node.path) ? "▾" : "▸") : "·";
        const indexed = node.is_vectorized ? "已索引" : "未索引";
        row.innerHTML = `
            <button type="button" class="tree-name">
                <span>${icon}</span>
                <span>${escapeHtml(node.name)}</span>
            </button>
            <div class="tree-actions">
                <span class="status-pill ${node.is_vectorized ? "ok" : ""}">${indexed}</span>
                ${node.is_dir && isAdmin() ? `<button type="button" data-mine="${escapeAttr(node.path)}">打包</button>` : ""}
            </div>`;

        row.querySelector(".tree-name").addEventListener("click", () => {
            if (node.is_dir) {
                if (state.expandedPaths.has(node.path)) state.expandedPaths.delete(node.path);
                else state.expandedPaths.add(node.path);
                renderLibrary();
            } else {
                previewLibraryFile(node);
            }
        });
        const mineBtn = row.querySelector("[data-mine]");
        if (mineBtn) mineBtn.addEventListener("click", () => mineLibrary(node.path));

        parent.appendChild(row);
        if (node.is_dir && state.expandedPaths.has(node.path) && node.children?.length) {
            renderTreeNodes(node.children, parent, level + 1);
        }
    });
}

async function previewLibraryFile(node) {
    try {
        const data = await fetchJson(`/api/library/read?path=${encodeURIComponent(node.path)}`);
        $("#library-empty").classList.add("hidden");
        $("#library-detail").classList.remove("hidden");
        setText("library-path", node.path);
        setText("library-title", node.name);
        setText("library-content", data.content || "");
    } catch (e) {
        showToast(`读取知识文件失败：${e.message}`);
    }
}

async function mineLibrary(path) {
    if (!isAdmin()) return showToast("需要管理员角色。");
    try {
        const data = await postJson("/api/library/mine", { wing_path: path });
        showToast(data.message || "打包完成。");
        await loadLibrary();
    } catch (e) {
        showToast(`打包失败：${e.message}`);
    }
}

async function switchProject(event) {
    event.preventDefault();
    if (!isAdmin()) return showToast("需要管理员角色。");
    const path = $("#project-path").value.trim();
    const prefix = $("#project-prefix").value.trim();
    const isMC = $("#project-is-mc").checked;
    if (!path) return showToast("请填写项目路径。");
    try {
        const data = await postJson("/api/project/switch", {
            path,
            prefix: prefix || null,
            is_mc_project: isMC,
        });
        showToast(data.success ? "项目已接入。" : "项目切换失败。");
        await refreshAll();
        switchView("dashboard");
    } catch (e) {
        showToast(`项目接入失败：${e.message}`);
    }
}

function setAstellOutput(text) {
    setText("astell-output", text);
}

async function retrieveAstellKnowledge(event) {
    event.preventDefault();
    const query = $("#astell-query").value.trim();
    if (!query) return showToast("请输入要检索的问题。");
    setAstellOutput("检索中...");
    try {
        const data = await postJson("/api/astell/retrieve", {
            query,
            current_project: $("#astell-current-project").value.trim() || null,
            strict_mode: $("#astell-strict-mode").checked,
        });
        setAstellOutput(data.output || "");
        await loadPending();
    } catch (e) {
        setAstellOutput(`检索失败：${e.message}`);
    }
}

async function recordTrace(event) {
    event.preventDefault();
    const content = $("#trace-content").value.trim();
    if (!content) return showToast("请输入留痕内容。");
    setAstellOutput("写入中...");
    try {
        const data = await postJson("/api/astell/trace", {
            type: $("#trace-type").value,
            title: $("#trace-title").value.trim() || "新记录",
            content,
        });
        setAstellOutput(data.output || "已写入项目记录。");
        $("#trace-content").value = "";
        await Promise.allSettled([loadWorkspace(), loadPending()]);
    } catch (e) {
        setAstellOutput(`留痕失败：${e.message}`);
    }
}

async function registerResource(event) {
    event.preventDefault();
    const resourceId = $("#resource-id").value.trim();
    const description = $("#resource-description").value.trim();
    if (!resourceId || !description) return showToast("资源 ID 和描述都需要填写。");
    setAstellOutput("登记中...");
    try {
        const data = await postJson("/api/astell/resource", {
            resource_id: resourceId,
            description,
            file_path: $("#resource-path").value.trim() || "N/A",
        });
        setAstellOutput(data.output || "资源已登记。");
        await loadWorkspace();
    } catch (e) {
        setAstellOutput(`资源登记失败：${e.message}`);
    }
}

async function updatePrefix(event) {
    event.preventDefault();
    if (!isAdmin()) return showToast("需要管理员角色。");
    const newPrefix = $("#new-prefix").value.trim();
    if (!newPrefix) return showToast("请输入新的项目前缀。");
    setAstellOutput("更新项目前缀中...");
    try {
        const data = await postJson("/api/project/prefix", { new_prefix: newPrefix });
        setAstellOutput(data.output || `项目前缀已更新为 ${data.prefix}`);
        $("#new-prefix").value = "";
        await refreshAll();
    } catch (e) {
        setAstellOutput(`前缀更新失败：${e.message}`);
    }
}

async function loadKnowledgeInventory() {
    setAstellOutput("读取知识清单中...");
    try {
        const data = await fetchJson("/api/astell/inventory");
        setAstellOutput(data.output || "");
    } catch (e) {
        setAstellOutput(`知识清单读取失败：${e.message}`);
    }
}

async function loadAuditReport() {
    setAstellOutput("生成固化审计报告中...");
    try {
        const data = await fetchJson("/api/astell/audit-report");
        setAstellOutput(data.output || "");
        await loadPending();
    } catch (e) {
        setAstellOutput(`固化审计失败：${e.message}`);
    }
}

async function suggestDeepResearch(event) {
    event.preventDefault();
    const query = $("#deep-research-query").value.trim();
    if (!query) return showToast("请输入需要深研的问题。");
    setAstellOutput("生成深研建议中...");
    try {
        const data = await postJson("/api/astell/deep-research", { query });
        setAstellOutput(data.output || "");
        await loadPending();
    } catch (e) {
        setAstellOutput(`深研建议生成失败：${e.message}`);
    }
}

function copyAstellOutput() {
    const text = $("#astell-output").textContent;
    if (!navigator.clipboard?.writeText) {
        showToast("浏览器不支持自动复制，请手动选择文本。");
        return;
    }
    navigator.clipboard.writeText(text).then(
        () => showToast("已复制。"),
        () => showToast("复制失败，请手动选择文本。"),
    );
}

function setModsdkOutput(text) {
    setText("modsdk-output", text);
}

function formatJson(data) {
    return JSON.stringify(data, null, 2);
}

async function searchModsdk(event) {
    event.preventDefault();
    const query = $("#modsdk-query").value.trim();
    const scope = $("#modsdk-scope").value;
    if (!query) return showToast("请输入检索关键词。");
    setModsdkOutput("检索中...");
    try {
        const data = await postJson("/api/modsdk/search", { query, scope, limit: 6 });
        if (!data.results?.length) {
            setModsdkOutput(`未找到结果：${data.query}`);
            return;
        }
        const lines = [`查询：${data.query}`, `范围：${data.scope}`, ""];
        data.results.forEach((item, index) => {
            lines.push(`${index + 1}. ${item.path}  score=${item.score}`);
            lines.push(item.snippet);
            lines.push("");
        });
        setModsdkOutput(lines.join("\n"));
    } catch (e) {
        setModsdkOutput(`检索失败：${e.message}`);
    }
}

async function generateTemplate(event) {
    event.preventDefault();
    const identifier = $("#modsdk-identifier").value.trim();
    if (!identifier) return showToast("请填写 identifier。");
    setModsdkOutput("生成中...");
    try {
        const data = await postJson("/api/modsdk/template", {
            kind: $("#modsdk-kind").value,
            namespace: $("#modsdk-namespace").value.trim() || "astell",
            identifier,
            display_name: $("#modsdk-display-name").value.trim() || null,
        });
        const lines = [`模板：${data.kind} -> ${data.identifier}`, ""];
        data.files.forEach((file) => {
            lines.push(`### ${file.path}`);
            lines.push(file.content);
            lines.push("");
        });
        lines.push("后续动作：");
        data.next_steps.forEach((step) => lines.push(`- ${step}`));
        setModsdkOutput(lines.join("\n"));
    } catch (e) {
        setModsdkOutput(`模板生成失败：${e.message}`);
    }
}

async function reviewCode(event) {
    event.preventDefault();
    const code = $("#modsdk-code").value;
    if (!code.trim()) return showToast("请粘贴代码。");
    setModsdkOutput("审查中...");
    try {
        const data = await postJson("/api/modsdk/review", {
            filename: $("#modsdk-filename").value.trim() || "snippet.py",
            code,
        });
        setModsdkOutput(formatReview(data));
    } catch (e) {
        setModsdkOutput(`审查失败：${e.message}`);
    }
}

function formatReview(data) {
    const lines = [`代码审查：${data.filename || "snippet.py"}`, data.summary || "", ""];
    if (data.findings?.length) {
        data.findings.forEach((item) => {
            lines.push(`[${item.severity}] ${item.title}`);
            lines.push(item.detail);
            lines.push("");
        });
    } else {
        lines.push("未发现明显规则命中。", "");
    }
    lines.push("建议基线：");
    (data.best_practices || []).forEach((rule) => lines.push(`- ${rule}`));
    return lines.join("\n");
}

async function loadPractices(event) {
    event.preventDefault();
    setModsdkOutput("读取中...");
    try {
        const data = await postJson("/api/modsdk/practices", { topic: $("#modsdk-topic").value });
        setModsdkOutput(formatJson(data));
    } catch (e) {
        setModsdkOutput(`读取失败：${e.message}`);
    }
}

function copyModsdkOutput() {
    const text = $("#modsdk-output").textContent;
    if (!navigator.clipboard?.writeText) {
        showToast("浏览器不支持自动复制，请手动选择文本。");
        return;
    }
    navigator.clipboard.writeText(text).then(
        () => showToast("已复制。"),
        () => showToast("复制失败，请手动选择文本。"),
    );
}

async function refreshAll() {
    const tasks = [loadStatus(), loadHealth()];
    if (isAdmin()) {
        tasks.push(loadPending(), loadUsers());
    } else {
        state.pending = [];
        state.users = [];
    }
    await Promise.allSettled(tasks);
    renderOverview();
}

function bindEvents() {
    $$(".nav-item[data-view]").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
    $$("[data-view-jump]").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.viewJump)));
    $$("[data-role-option]").forEach((btn) => btn.addEventListener("click", async () => {
        setRole(btn.dataset.roleOption);
        await refreshAll();
    }));

    $("#refresh-all")?.addEventListener("click", refreshAll);
    $("#reload-pending")?.addEventListener("click", loadPending);
    $("#reload-workspace")?.addEventListener("click", loadWorkspace);
    $("#reload-library")?.addEventListener("click", loadLibrary);
    $("#project-form")?.addEventListener("submit", switchProject);
    $("#approve-solidify")?.addEventListener("click", approveSolidify);
    $("#reject-solidify")?.addEventListener("click", rejectSolidify);
    $("#mark-untrustworthy")?.addEventListener("click", markWorkspaceUntrustworthy);
    $("#astell-retrieve-form")?.addEventListener("submit", retrieveAstellKnowledge);
    $("#astell-trace-form")?.addEventListener("submit", recordTrace);
    $("#resource-form")?.addEventListener("submit", registerResource);
    $("#prefix-form")?.addEventListener("submit", updatePrefix);
    $("#load-inventory")?.addEventListener("click", loadKnowledgeInventory);
    $("#load-audit-report")?.addEventListener("click", loadAuditReport);
    $("#deep-research-form")?.addEventListener("submit", suggestDeepResearch);
    $("#copy-astell-output")?.addEventListener("click", copyAstellOutput);
    $("#modsdk-search-form")?.addEventListener("submit", searchModsdk);
    $("#modsdk-template-form")?.addEventListener("submit", generateTemplate);
    $("#modsdk-review-form")?.addEventListener("submit", reviewCode);
    $("#modsdk-practice-form")?.addEventListener("submit", loadPractices);
    $("#copy-modsdk-output")?.addEventListener("click", copyModsdkOutput);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
    return escapeHtml(value).replaceAll("`", "&#096;");
}

document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    await loadSession();
    await refreshAll();
    switchView("dashboard");
    setInterval(refreshAll, 15000);
});
