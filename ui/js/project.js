import { state } from './state.js';
import { renderAuditList } from './audit.js';

export async function refreshStatus() {
    try {
        const statusRes = await fetch('/api/status');
        const status = await statusRes.json();
        document.getElementById('current-project-name').textContent = status.active_prefix || '未设置活跃项目';

        const pendingRes = await fetch('/api/pending');
        const data = await pendingRes.json();
        state.pendingData = data.pending;
        document.getElementById('pending-count').textContent = state.pendingData.length;
        if (state.activeView === 'audit') renderAuditList();
    } catch (e) {
        console.error("Refresh status error:", e);
    }
}

export function showSwitchProjectModal() {
    document.getElementById('switch-project-modal').classList.remove('hidden');
}

export function hideSwitchProjectModal() {
    document.getElementById('switch-project-modal').classList.add('hidden');
}

export async function executeSwitchProject() {
    const path = document.getElementById('modal-proj-path').value.trim();
    const prefix = document.getElementById('modal-proj-prefix').value.trim();
    const isMC = document.getElementById('modal-proj-is-mc').checked;

    if (!path) {
        alert('请填写项目物理路径');
        return;
    }

    try {
        const res = await fetch('/api/project/switch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ path, prefix: prefix || null, is_mc_project: isMC })
        });
        const result = await res.json();
        if (result.success) {
            alert(`项目对接成功:\n${result.details.join('\n')}`);
            hideSwitchProjectModal();
            refreshStatus();
        } else {
            alert('切换失败: ' + result.message);
        }
    } catch (e) {
        alert('对接出错: ' + e.message);
    }
}