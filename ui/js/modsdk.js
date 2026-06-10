import { state } from './state.js';

function setOutput(text) {
    const output = document.getElementById('modsdk-output');
    if (output) output.textContent = text;
}

function renderSearchResults(data) {
    if (!data.results || data.results.length === 0) {
        setOutput(`未找到与「${data.query}」相关的官方资料。`);
        return;
    }

    const lines = [`查询: ${data.query} | scope=${data.scope}`, ''];
    data.results.forEach((item, index) => {
        lines.push(`${index + 1}. ${item.path} (score=${item.score})`);
        lines.push(item.snippet);
        lines.push('-'.repeat(40));
    });
    setOutput(lines.join('\n'));
}

function renderTemplate(data) {
    const lines = [`模板: ${data.kind} -> ${data.identifier}`, `显示名: ${data.display_name}`, ''];
    data.files.forEach(file => {
        lines.push(`### ${file.path}`);
        lines.push(file.content);
        lines.push('');
    });
    lines.push('后续动作:');
    data.next_steps.forEach(step => lines.push(`- ${step}`));
    setOutput(lines.join('\n'));
}

function renderReview(data) {
    const lines = [`代码审查: ${data.filename || 'snippet.py'}`, data.summary, ''];
    if (data.findings && data.findings.length > 0) {
        data.findings.forEach(item => {
            lines.push(`[${item.severity}] ${item.title}`);
            lines.push(item.detail);
            lines.push('');
        });
    } else {
        lines.push('未发现明显规则命中。', '');
    }
    lines.push('建议基线:');
    (data.best_practices || []).forEach(rule => lines.push(`- ${rule}`));
    setOutput(lines.join('\n'));
}

function renderPractices(data) {
    const lines = [`最佳实践: ${data.topic}`, ''];
    data.rules.forEach(rule => lines.push(`- ${rule}`));
    lines.push('', `可用 topic: ${data.available_topics.join(', ')}`);
    setOutput(lines.join('\n'));
}

async function postJson(url, payload) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '请求失败');
    return data;
}

export async function searchModsdkDocs() {
    const query = document.getElementById('modsdk-query').value.trim();
    const scope = document.getElementById('modsdk-scope').value;
    if (!query) {
        setOutput('请输入要检索的官方 SDK 关键词。');
        return;
    }
    setOutput('正在检索官方资料...');
    try {
        const data = await postJson('/api/modsdk/search', { query, scope, limit: 6 });
        state.modsdkLastResult = data;
        renderSearchResults(data);
    } catch (e) {
        setOutput(`检索失败: ${e.message}`);
    }
}

export async function generateModsdkTemplateUi() {
    const kind = document.getElementById('modsdk-template-kind').value;
    const namespace = document.getElementById('modsdk-template-namespace').value.trim() || 'astell';
    const identifier = document.getElementById('modsdk-template-id').value.trim();
    const displayName = document.getElementById('modsdk-template-name').value.trim() || null;
    if (!identifier) {
        setOutput('请输入资源 identifier 名称，例如 night_vision_cookie。');
        return;
    }
    setOutput('正在生成模板草稿...');
    try {
        const data = await postJson('/api/modsdk/template', {
            kind,
            namespace,
            identifier,
            display_name: displayName
        });
        state.modsdkLastResult = data;
        renderTemplate(data);
    } catch (e) {
        setOutput(`模板生成失败: ${e.message}`);
    }
}

export async function reviewModsdkCodeUi() {
    const filename = document.getElementById('modsdk-review-filename').value.trim() || 'snippet.py';
    const code = document.getElementById('modsdk-review-code').value;
    if (!code.trim()) {
        setOutput('请粘贴要审查的 ModSDK 代码。');
        return;
    }
    setOutput('正在审查代码...');
    try {
        const data = await postJson('/api/modsdk/review', { filename, code });
        state.modsdkLastResult = data;
        renderReview(data);
    } catch (e) {
        setOutput(`代码审查失败: ${e.message}`);
    }
}

export async function loadModsdkPractices() {
    const topic = document.getElementById('modsdk-practice-topic').value;
    setOutput('正在读取最佳实践...');
    try {
        const data = await postJson('/api/modsdk/practices', { topic });
        state.modsdkLastResult = data;
        renderPractices(data);
    } catch (e) {
        setOutput(`读取失败: ${e.message}`);
    }
}
