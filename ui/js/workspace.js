import { state } from './state.js';

export async function loadWorkspaceModules() {
    try {
        const res = await fetch('/api/workspace/modules');
        const data = await res.json();
        state.workspaceModules = data.modules || [];
        renderWorkspaceModuleList();
    } catch (e) {
        console.error("加载工作区模块失败:", e);
    }
}

export function renderWorkspaceModuleList() {
    const container = document.getElementById('workspace-module-list');
    if (!container) return;
    container.innerHTML = '';
    
    if (state.workspaceModules.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-500 text-center py-8">暂无记录文件</p>';
        return;
    }
    
    state.workspaceModules.forEach((m, index) => {
        const div = document.createElement('div');
        div.className = `p-3 rounded-xl border cursor-pointer transition-all ${state.selectedWsIndex === index ? 'bg-indigo-600 border-indigo-600 text-white shadow-md' : 'bg-slate-900 border-slate-850 text-slate-300 hover:border-slate-700'}`;
        
        let statusIcon = '';
        if (m.is_untrustworthy) {
            statusIcon = '<i class="fa-solid fa-shield-virus text-rose-400 ml-auto" title="不可信"></i>';
        } else if (m.has_prob && !m.prob_resolved) {
            statusIcon = '<i class="fa-solid fa-triangle-exclamation text-amber-400 ml-auto" title="有报错待解决"></i>';
        } else if (m.has_dev) {
            statusIcon = '<i class="fa-solid fa-circle-check text-emerald-400 ml-auto" title="状态良好"></i>';
        }

        div.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="text-xs font-bold truncate flex-grow">${m.name}</div>
                ${statusIcon}
            </div>
            <div class="flex gap-1 mt-1.5">
                ${m.has_dev ? '<span class="text-[8px] px-1 rounded bg-indigo-950 text-indigo-400 border border-indigo-800/30">DEV</span>' : ''}
                ${m.has_prob ? '<span class="text-[8px] px-1 rounded bg-rose-950 text-rose-400 border border-rose-800/30">PROB</span>' : ''}
            </div>
        `;
        
        div.onclick = () => selectWorkspaceModule(index);
        container.appendChild(div);
    });
}

export async function selectWorkspaceModule(index) {
    state.selectedWsIndex = index;
    renderWorkspaceModuleList();
    
    const m = state.workspaceModules[index];
    const panel = document.getElementById('workspace-detail-panel');
    const empty = document.getElementById('workspace-empty');
    
    panel.classList.remove('hidden');
    empty.classList.add('hidden');
    
    document.getElementById('ws-detail-title').textContent = m.name;
    
    // 清空内容
    document.getElementById('ws-dev-content').textContent = '加载中...';
    document.getElementById('ws-prob-content').textContent = '无关联记录';
    
    const badgeContainer = document.getElementById('ws-status-badges');
    badgeContainer.innerHTML = '';
    
    if (m.is_untrustworthy) {
        badgeContainer.innerHTML += '<span class="text-[9px] font-black px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-900/30">不可信</span>';
    } else if (m.has_prob && !m.prob_resolved) {
        badgeContainer.innerHTML += '<span class="text-[9px] font-black px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-900/30">报错未解决</span>';
    } else {
        badgeContainer.innerHTML += '<span class="text-[9px] font-black px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-900/30">可信度高</span>';
    }

    // 绑定打标按钮
    const markBtn = document.getElementById('btn-mark-untrustworthy');
    if (m.is_untrustworthy) {
        markBtn.classList.add('opacity-50', 'pointer-events-none');
    } else {
        markBtn.classList.remove('opacity-50', 'pointer-events-none');
        markBtn.onclick = () => tagModuleUntrustworthy(m);
    }

    // 加载开发日志
    if (m.has_dev) {
        const res = await fetch(`/api/workspace/read?rel_path=${encodeURIComponent(m.dev_path)}`);
        const data = await res.json();
        document.getElementById('ws-dev-content').textContent = data.content;
    } else {
        document.getElementById('ws-dev-content').textContent = '暂无开发日志';
    }
    
    // 加载问题记录
    if (m.has_prob) {
        const res = await fetch(`/api/workspace/read?rel_path=${encodeURIComponent(m.prob_path)}`);
        const data = await res.json();
        document.getElementById('ws-prob-content').textContent = data.content;
    }
}

async function tagModuleUntrustworthy(m) {
    if (!confirm(`确定要将模块 "${m.name}" 的所有记录标记为不可信吗？这将阻止其进入长期记忆。`)) return;
    
    try {
        const path = m.has_dev ? m.dev_path : m.prob_path;
        const res = await fetch('/api/workspace/tag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rel_path: path, tag: 'untrustworthy' })
        });
        if (res.ok) {
            alert('已成功标记。');
            loadWorkspaceModules();
        }
    } catch (e) {
        alert('标记失败: ' + e.message);
    }
}
