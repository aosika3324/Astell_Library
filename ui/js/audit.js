import { state } from './state.js';
import { refreshStatus } from './project.js';

export function renderAuditList() {
    const listDiv = document.getElementById('pending-list');
    if (state.pendingData.length === 0) {
        listDiv.innerHTML = `
            <div class="p-12 text-center text-slate-500 bg-slate-900/40 rounded-2xl border border-slate-800">
                <i class="fa-solid fa-inbox text-3xl mb-3 opacity-20"></i>
                <p class="text-xs font-bold">暂无待固化申请</p>
            </div>`;
        return;
    }

    listDiv.innerHTML = '';
    state.pendingData.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = `p-4 rounded-xl border cursor-pointer transition-all ${state.selectedIndex === index ? 'bg-indigo-600 border-indigo-600 text-white shadow-md' : 'bg-slate-900 border-slate-850 text-slate-300 hover:border-slate-700'}`;
        card.onclick = () => selectAuditItem(index);
        
        const typeLabel = item.type === 'problem' ? '已解决报错' : '知识空白点';
        const typeIcon = item.type === 'problem' ? 'fa-bug-slash' : 'fa-magnifying-glass-chart';
        
        card.innerHTML = `
            <div class="flex items-start gap-3">
                <div class="mt-0.5 p-1.5 rounded-lg ${state.selectedIndex === index ? 'bg-white/20 text-white' : 'bg-slate-800 text-indigo-400'}">
                    <i class="fa-solid ${typeIcon} text-sm"></i>
                </div>
                <div class="flex-grow overflow-hidden">
                    <p class="text-[9px] font-black uppercase tracking-wider opacity-60 mb-0.5">${typeLabel}</p>
                    <h4 class="font-bold text-xs truncate">${item.title}</h4>
                </div>
            </div>
        `;
        listDiv.appendChild(card);
    });
}

export function selectAuditItem(index) {
    state.selectedIndex = index;
    renderAuditList();
    
    const item = state.pendingData[index];
    const panel = document.getElementById('detail-panel');
    const empty = document.getElementById('detail-empty');
    
    panel.classList.remove('hidden');
    empty.classList.add('hidden');
    
    const typeSpan = document.getElementById('detail-type');
    typeSpan.textContent = item.type === 'problem' ? 'Resolved Bug' : 'Knowledge Gap';
    typeSpan.className = `text-[9px] font-black px-2 py-0.5 rounded uppercase tracking-wider ${item.type === 'problem' ? 'bg-emerald-950 text-emerald-400 border border-emerald-900/35' : 'bg-amber-950 text-amber-400 border border-amber-900/35'}`;
    
    document.getElementById('detail-title').textContent = item.title;
    document.getElementById('detail-content').textContent = item.content;
}

export async function approveSolidifyDirect() {
    const item = state.pendingData[state.selectedIndex];
    if (!item || !item.rel_path) return;

    try {
        const res = await fetch('/api/solidify/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rel_path: item.rel_path,
                module_name: item.module_name
            })
        });
        const result = await res.json();
        if (result.success) {
            alert(`物理固化入库成功！\n共物理备份 ${result.copied_count} 个核心文件。\nMemPalace 索引状态: ${result.vector_status}`);
            state.pendingData.splice(state.selectedIndex, 1);
            state.selectedIndex = -1;
            document.getElementById('detail-panel').classList.add('hidden');
            document.getElementById('detail-empty').classList.remove('hidden');
            refreshStatus();
            if (state.activeView === 'workspace') window.loadWorkspaceModules();
        } else {
            alert('固化失败: ' + result.message);
        }
    } catch (e) {
        alert('审批固化出错: ' + e.message);
    }
}

export function rejectSolidify() {
    if (confirm('确定要忽略这条固化建议吗？')) {
        state.pendingData.splice(state.selectedIndex, 1);
        state.selectedIndex = -1;
        document.getElementById('detail-panel').classList.add('hidden');
        document.getElementById('detail-empty').classList.remove('hidden');
        renderAuditList();
    }
}