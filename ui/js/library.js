import { state } from './state.js';

export async function loadLibraryTree() {
    try {
        const res = await fetch('/api/library/tree');
        const data = await res.json();
        state.libraryTreeData = data.tree || [];
        renderLibraryTree();
    } catch (e) {
        console.error(e);
    }
}

export function renderLibraryTree() {
    const container = document.getElementById('library-tree');
    container.innerHTML = '';
    
    if (state.libraryTreeData.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-500">记忆库中尚无分类</p>';
        return;
    }

    function renderNodes(nodes, parentEl, level = 0) {
        nodes.forEach(node => {
            const div = document.createElement('div');
            div.className = `flex items-center justify-between py-1.5 px-2 rounded-lg text-xs cursor-pointer hover:bg-slate-900 transition-colors group ${node.is_dir ? 'font-bold text-slate-300' : 'text-slate-400'}`;
            div.style.paddingLeft = `${level * 16 + 8}px`;
            
            const isExpanded = state.expandedPaths.has(node.path);
            let icon = '';
            const vectorizedIcon = node.is_vectorized
                ? '<i class="fa-solid fa-circle-check text-emerald-500 ml-auto" title="已向量化"></i>'
                : '<i class="fa-solid fa-circle-dot text-slate-600 ml-auto" title="待向量化"></i>';

            if (node.is_dir) {
                icon = isExpanded
                    ? '<i class="fa-solid fa-folder-open text-amber-500 mr-2"></i>'
                    : '<i class="fa-solid fa-folder text-amber-600 mr-2"></i>';
            } else {
                icon = '<i class="fa-solid fa-file-lines text-slate-500 mr-2"></i>';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = "flex items-center flex-grow overflow-hidden";
                contentDiv.innerHTML = `${icon} <span class="truncate">${node.name}</span>`;
                div.appendChild(contentDiv);
                div.innerHTML += vectorizedIcon;
            }
            
            if (node.is_dir) {
                const contentDiv = document.createElement('div');
                contentDiv.className = "flex items-center flex-grow overflow-hidden";
                contentDiv.innerHTML = `${icon} <span class="truncate">${node.name}</span>`;
                div.appendChild(contentDiv);
                div.innerHTML += vectorizedIcon;

                // 为目录添加“打包”按钮
                const mineBtn = document.createElement('button');
                mineBtn.className = "hidden group-hover:block px-1.5 py-0.5 bg-indigo-900/50 hover:bg-indigo-700 text-[9px] text-indigo-300 rounded border border-indigo-800 transition-all";
                mineBtn.innerHTML = '<i class="fa-solid fa-box-archive mr-1"></i>打包';
                mineBtn.onclick = (e) => {
                    e.stopPropagation();
                    mineDirectory(node.path);
                };
                div.appendChild(mineBtn);

                div.onclick = () => {
                    if (state.expandedPaths.has(node.path)) {
                        state.expandedPaths.delete(node.path);
                    } else {
                        state.expandedPaths.add(node.path);
                    }
                    renderLibraryTree();
                };
            } else {
                div.onclick = () => previewFile(node.path, node.name);
            }
            
            parentEl.appendChild(div);
            
            if (node.is_dir && isExpanded && node.children && node.children.length > 0) {
                const childContainer = document.createElement('div');
                parentEl.appendChild(childContainer);
                renderNodes(node.children, childContainer, level + 1);
            }
        });
    }
    
    renderNodes(state.libraryTreeData, container);
}

export async function mineDirectory(path) {
    if (!confirm(`是否立即对目录 ${path} 进行 MemPalace 记忆打包与向量化？`)) return;
    
    try {
        const res = await fetch('/api/library/mine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wing_path: path })
        });
        const data = await res.json();
        if (data.success) {
            alert(data.message);
            loadLibraryTree(); // 刷新树以更新向量化状态
        } else {
            alert("打包失败: " + data.detail);
        }
    } catch (e) {
        alert("打包请求失败: " + e.message);
    }
}

export async function previewFile(path, name) {
    try {
        const res = await fetch(`/api/library/read?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        
        document.getElementById('lib-empty').classList.add('hidden');
        document.getElementById('lib-preview-header').classList.remove('hidden');
        document.getElementById('lib-file-path').textContent = path;
        document.getElementById('lib-file-name').textContent = name;
        document.getElementById('lib-content').textContent = data.content;
    } catch (e) {
        alert("加载文件内容失败");
    }
}
