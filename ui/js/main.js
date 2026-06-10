import { state } from './state.js';
import { refreshStatus, showSwitchProjectModal, hideSwitchProjectModal, executeSwitchProject } from './project.js';
import { renderAuditList, selectAuditItem, approveSolidifyDirect, rejectSolidify } from './audit.js';
import { loadLibraryTree, renderLibraryTree, previewFile } from './library.js';
import { loadWorkspaceModules, selectWorkspaceModule } from './workspace.js';
// 视图切换逻辑
export function switchView(view) {
    state.activeView = view;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeBtn = document.getElementById(`nav-${view}`);
    if (activeBtn) activeBtn.classList.add('active');

    // 隐藏所有视图
    ['guide', 'audit', 'library', 'workspace'].forEach(v => {
        const viewEl = document.getElementById(`view-${v}`);
        if (viewEl) viewEl.classList.add('hidden');
    });
    // 显示目标视图
    const targetViewEl = document.getElementById(`view-${view}`);
    if (targetViewEl) targetViewEl.classList.remove('hidden');

    if (view === 'library') loadLibraryTree();
    if (view === 'workspace') loadWorkspaceModules();
}

// 将所有需要供 HTML 行内 onclick/onchange/input 调用的函数暴露给 window 对象
window.switchView = switchView;
window.refreshStatus = refreshStatus;
window.showSwitchProjectModal = showSwitchProjectModal;
window.hideSwitchProjectModal = hideSwitchProjectModal;
window.executeSwitchProject = executeSwitchProject;

window.renderAuditList = renderAuditList;
window.selectAuditItem = selectAuditItem;
window.approveSolidifyDirect = approveSolidifyDirect;
window.rejectSolidify = rejectSolidify;

window.loadLibraryTree = loadLibraryTree;
window.renderLibraryTree = renderLibraryTree;
window.previewFile = previewFile;

window.loadWorkspaceModules = loadWorkspaceModules;
window.selectWorkspaceModule = selectWorkspaceModule;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    refreshStatus();
    switchView('audit'); // 默认显示审批页面

    // 定时轮询
    setInterval(() => {
        refreshStatus();
    }, 5000);
});