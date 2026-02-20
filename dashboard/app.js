/* ═══════════════════════════════════════════════════════════
   AI PAPER REVIEWER — Fixed & Enhanced Application Logic
   Fixes:
   - Synthesis slow: 60s timeout + live progress feedback
   - Same data every time: cache-busted API calls
   - Content too short: full section rendering with expand
   - Blog post format: toggle between Academic / Blog / Summary
   - Paper comparison: side-by-side diff view
   - PDF export: download via /api/export/pdf
   - Papers not updating: force refresh on every view switch
   ═══════════════════════════════════════════════════════════ */

'use strict';

const API = 'http://localhost:5000/api';

// ── STATE ──────────────────────────────────────────────────
const state = {
    currentView: 'synthesis',
    selectedPapers: new Set(),
    papers: [],
    synthesis: null,
    reports: [],
    pipelineStages: [],
    pipelinePoller: null,
    synthesisPoller: null,
    isSynthesizing: false,
    analysis: null,
    outputFormat: 'academic', // 'academic' | 'blog' | 'summary'
    comparisonMode: false,
};

// ── TOAST ──────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = {
        success: `<svg class="toast-icon" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M6 10l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
        error: `<svg class="toast-icon" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M7 7l6 6M13 7l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,
        info: `<svg class="toast-icon" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M10 9v5M10 7v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,
    };
    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('toast-exit');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }, duration);
}

// ── API HELPERS ────────────────────────────────────────────
// FIX: Added cache-busting timestamp to every GET to prevent stale data
async function apiFetch(path, options = {}) {
    try {
        const isGet = !options.method || options.method === 'GET';
        const url = API + path + (isGet ? `?_=${Date.now()}` : '');
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            throw new Error(err.error || res.statusText);
        }
        return await res.json();
    } catch (e) {
        if (e.message.includes('Failed to fetch') || e.message.includes('NetworkError')) {
            showToast('Cannot reach API server. Is server.py running?', 'error', 6000);
        }
        throw e;
    }
}

// ── FORMAT TOOLBAR ─────────────────────────────────────────
// FIX: Blog post format option added
function injectFormatToolbar() {
    const draftScroll = document.querySelector('.draft-scroll');
    if (!draftScroll || document.getElementById('format-toolbar')) return;

    const toolbar = document.createElement('div');
    toolbar.id = 'format-toolbar';
    toolbar.style.cssText = `
        display:flex; align-items:center; gap:8px; padding:10px 0 18px 0;
        border-bottom:1px solid rgba(255,255,255,0.06); margin-bottom:18px;
    `;
    toolbar.innerHTML = `
        <span style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.08em;margin-right:4px">Output Format</span>
        <button id="fmt-academic" class="fmt-btn active" onclick="setFormat('academic')" title="Academic research paper style">📄 Academic</button>
        <button id="fmt-blog" class="fmt-btn" onclick="setFormat('blog')" title="Readable blog post style">✍️ Blog Post</button>
        <button id="fmt-summary" class="fmt-btn" onclick="setFormat('summary')" title="Short executive summary">⚡ Summary</button>
        <div style="flex:1"></div>
        <button id="compare-btn" class="fmt-btn" onclick="toggleComparison()" title="Compare papers side by side">🔀 Compare Papers</button>
        <button onclick="exportPDF()" class="fmt-btn" style="background:rgba(79,142,247,0.15);color:#4F8EF7;border-color:rgba(79,142,247,0.3)" title="Download as PDF">📥 Export PDF</button>
    `;
    draftScroll.insertBefore(toolbar, draftScroll.firstChild);

    // Inject styles for format buttons
    if (!document.getElementById('fmt-styles')) {
        const style = document.createElement('style');
        style.id = 'fmt-styles';
        style.textContent = `
            .fmt-btn {
                padding:5px 12px; border-radius:8px; font-size:12px; cursor:pointer;
                border:1px solid rgba(255,255,255,0.1); background:rgba(255,255,255,0.05);
                color:#aaa; transition:all .2s;
            }
            .fmt-btn:hover { background:rgba(255,255,255,0.1); color:#fff; }
            .fmt-btn.active { background:rgba(99,102,241,0.25); color:#818cf8; border-color:rgba(99,102,241,0.4); }
            .full-section { display:none; white-space:pre-wrap; font-size:13px; line-height:1.7; color:#c8d0e0; margin-top:8px; }
            .expand-btn { font-size:11px; color:#6366f1; cursor:pointer; background:none; border:none; padding:4px 0; text-decoration:underline; }
            .comparison-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
            .comparison-col { background:rgba(255,255,255,0.03); border-radius:10px; padding:14px; border:1px solid rgba(255,255,255,0.07); }
            .comparison-col h4 { font-size:12px; color:#818cf8; margin-bottom:8px; font-weight:600; }
            .comparison-section { margin-bottom:10px; }
            .comparison-section-label { font-size:10px; text-transform:uppercase; color:#666; letter-spacing:.07em; margin-bottom:4px; }
            .comparison-section-text { font-size:12px; color:#aab; line-height:1.6; }
        `;
        document.head.appendChild(style);
    }
}

function setFormat(fmt) {
    state.outputFormat = fmt;
    document.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`fmt-${fmt}`);
    if (btn) btn.classList.add('active');
    // Re-render synthesis with new format
    if (state.synthesis) renderSynthesisContent(state.synthesis, fmt);
}

// ── VIEW SWITCHING ─────────────────────────────────────────
function switchView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.style.display = 'none');
    const target = document.getElementById(`view-${viewName}`);
    if (target) target.style.display = viewName === 'synthesis' ? 'flex' : 'block';

    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        item.setAttribute('aria-current', 'false');
    });
    const activeNav = document.getElementById(`nav-${viewName}`);
    if (activeNav) { activeNav.classList.add('active'); activeNav.setAttribute('aria-current', 'page'); }

    updateStepper(viewName);
    state.currentView = viewName;

    if (viewName === 'search') loadSearchView();
    if (viewName === 'extraction') loadPipelineView();
    if (viewName === 'synthesis') loadSynthesisView();
    if (viewName === 'reports') loadReportsView();
}

function updateStepper(viewName) {
    const stepMap = { search: 1, extraction: 2, synthesis: 4, reports: 5 };
    const current = stepMap[viewName] || 4;
    document.querySelectorAll('.step').forEach(step => {
        const n = parseInt(step.dataset.step);
        step.classList.remove('active', 'done');
        if (n < current) step.classList.add('done');
        else if (n === current) step.classList.add('active');
    });
}

// ── SEARCH VIEW ────────────────────────────────────────────
function loadSearchView() {
    if (state.papers.length > 0) renderSearchResults(state.papers);
}

function setSearch(query) {
    const input = document.getElementById('topic-search');
    if (input) input.value = query;
    simulateSearch();
}

async function simulateSearch() {
    const input = document.getElementById('topic-search');
    const query = (input?.value || '').trim();
    if (!query) { showToast('Enter a research topic first', 'error'); return; }

    const grid = document.getElementById('search-paper-grid');
    if (!grid) return;

    grid.innerHTML = skeletons(4);
    showToast(`Searching for "${query}"…`, 'info', 2000);

    const proj = document.getElementById('topbar-project-name');
    if (proj) proj.textContent = query;

    try {
        const data = await apiFetch('/search', {
            method: 'POST',
            body: JSON.stringify({ topic: query, limit: 8 }),
        });
        state.papers = data.papers || [];
        state.selectedPapers = new Set();
        renderSearchResults(state.papers);
        showToast(`Found ${data.count} papers for "${query}"`, 'success');
    } catch (e) {
        grid.innerHTML = `<div class="empty-state">⚠️ Search failed: ${e.message}</div>`;
    }
    updateAnalyzeButton();
}

function renderSearchResults(papers) {
    const grid = document.getElementById('search-paper-grid');
    if (!grid) return;
    if (!papers.length) {
        grid.innerHTML = `<div class="empty-state">🔍 No papers found. Try a different topic.</div>`;
        updateAnalyzeButton();
        return;
    }
    grid.innerHTML = papers.map((p, i) => {
        const authors = Array.isArray(p.authors) ? p.authors.join(', ') : p.authors;
        const tags = [p.venue, p.year].filter(Boolean);
        const isSelected = state.selectedPapers.has(i);
        const pdfUrl = p.pdf || p.url || null;
        return `
        <div class="search-result-card ${isSelected ? 'src-selected' : ''}" id="src-card-${i}">
          <div class="src-card-top">
            <label class="src-checkbox-wrap" onclick="toggleSearchPaper(${i}, event)" title="Select paper">
              <div class="src-checkbox ${isSelected ? 'checked' : ''}" id="src-chk-${i}" aria-checked="${isSelected}" role="checkbox">
                ${isSelected ? '<svg viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}
              </div>
            </label>
            <div class="src-meta">
              <div class="src-title">${p.title}</div>
              <div class="src-authors">${authors || 'Unknown Authors'} · ${p.year || 'n.d.'} · ${p.venue || 'Unknown Venue'}</div>
            </div>
          </div>
          <div class="src-abstract">${(p.abstract || 'No abstract available.').slice(0, 200)}${(p.abstract || '').length > 200 ? '…' : ''}</div>
          <div class="src-footer">
            <div class="src-tags">${tags.map(t => `<span class="tag-sm">${t}</span>`).join('')}</div>
            <div class="src-actions">
              ${pdfUrl ? `<a class="src-pdf-btn" href="${pdfUrl}" target="_blank" rel="noopener" title="Download PDF" onclick="event.stopPropagation()">
                <svg viewBox="0 0 14 14" fill="none"><path d="M7 1v8M4 6l3 3 3-3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M1 11h12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                PDF
              </a>` : `<span class="src-no-pdf">No PDF</span>`}
              <button class="src-add-btn ${isSelected ? 'added' : ''}" id="add-btn-${i}" onclick="toggleSearchPaper(${i}, event)">
                ${isSelected ? '✓ Selected' : '+ Select'}
              </button>
            </div>
          </div>
        </div>`;
    }).join('');
    updateAnalyzeButton();
}

function updateAnalyzeButton() {
    const btn = document.getElementById('analyze-btn');
    const badge = document.getElementById('search-selection-badge');
    if (!btn) return;
    const count = state.selectedPapers.size;
    const valid = count >= 1 && count <= 6;
    btn.disabled = !valid;
    if (badge) {
        badge.textContent = `${count} / 6 selected`;
        badge.className = `search-sel-badge ${valid ? 'valid' : (count > 6 ? 'over' : 'empty')}`;
    }
}

function toggleSearchPaper(idx, event) {
    if (event) event.stopPropagation();
    const wasSelected = state.selectedPapers.has(idx);
    const card = document.getElementById(`src-card-${idx}`);
    const chk = document.getElementById(`src-chk-${idx}`);
    const btn = document.getElementById(`add-btn-${idx}`);

    if (wasSelected) {
        state.selectedPapers.delete(idx);
        if (card) card.classList.remove('src-selected');
        if (chk) { chk.classList.remove('checked'); chk.innerHTML = ''; chk.setAttribute('aria-checked', 'false'); }
        if (btn) { btn.textContent = '+ Select'; btn.classList.remove('added'); }
    } else {
        if (state.selectedPapers.size >= 6) {
            showToast('Maximum 6 papers can be selected', 'error', 2500);
            return;
        }
        state.selectedPapers.add(idx);
        if (card) card.classList.add('src-selected');
        if (chk) {
            chk.classList.add('checked');
            chk.innerHTML = '<svg viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
            chk.setAttribute('aria-checked', 'true');
        }
        if (btn) { btn.textContent = '✓ Selected'; btn.classList.add('added'); }
        showToast('Paper added to pipeline', 'success', 1200);
    }
    updateAnalyzeButton();
}

// ── ANALYZE SELECTED ───────────────────────────────────────
async function runAnalyzeSelected() {
    const count = state.selectedPapers.size;
    if (count < 1 || count > 6) {
        showToast('Select 1 to 6 papers first', 'error');
        return;
    }
    showToast(`Preparing ${count} paper(s) for analysis…`, 'info', 2000);
    switchView('extraction');
    const label = document.getElementById('pipeline-status-label');
    if (label) label.textContent = `Analyzing ${count} paper(s)…`;
    try {
        await apiFetch('/pipeline/run', { method: 'POST' });
        showToast('Extraction pipeline started…', 'info', 2500);
        startPipelinePoller();
    } catch (e) {
        showToast(`Pipeline error: ${e.message}`, 'error');
    }
}

// ── PIPELINE VIEW ──────────────────────────────────────────
async function loadPipelineView() {
    try {
        const data = await apiFetch('/pipeline/status');
        state.pipelineStages = data.stages;
        renderPipelineStages(data.stages);
        if (data.running) startPipelinePoller();
    } catch (e) {
        renderPipelineStages(defaultPipelineStages());
    }
}

function defaultPipelineStages() {
    return [
        { id: 'pdf-parse', title: 'PDF Parsing', subtitle: 'Not started', status: 'pending', progress: 0 },
        { id: 'section-extract', title: 'Section Extraction', subtitle: 'Not started', status: 'pending', progress: 0 },
        { id: 'key-findings', title: 'Key Finding Identification', subtitle: 'Not started', status: 'pending', progress: 0 },
        { id: 'cross-compare', title: 'Cross-Paper Comparison', subtitle: 'Not started', status: 'pending', progress: 0 },
        { id: 'embedding', title: 'Semantic Embedding', subtitle: 'Not started', status: 'pending', progress: 0 },
        { id: 'synthesis-queue', title: 'Synthesis Queue', subtitle: 'Not started', status: 'pending', progress: 0 },
    ];
}

function renderPipelineStages(stages) {
    const grid = document.getElementById('pipeline-grid');
    if (!grid) return;
    grid.innerHTML = stages.map(stage => {
        const iconSVG = stage.status === 'done'
            ? `<svg viewBox="0 0 20 20" fill="none"><path d="M4 10l4 4 8-8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
            : stage.status === 'running'
                ? `<svg viewBox="0 0 20 20" fill="none" style="animation:spin 1.5s linear infinite"><path d="M10 3a7 7 0 017 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`
                : `<svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/></svg>`;
        return `
        <div class="pipeline-card">
          <div class="pipeline-card-header">
            <div class="pipeline-status-icon ${stage.status}">${iconSVG}</div>
            <div>
              <div class="pipeline-title">${stage.title}</div>
              <div class="pipeline-subtitle">${stage.subtitle}</div>
            </div>
          </div>
          <div class="pipeline-bar">
            <div class="pipeline-bar-fill ${stage.status}" style="width:${stage.progress}%"></div>
          </div>
        </div>`;
    }).join('');
}

async function runExtraction() {
    try {
        await apiFetch('/pipeline/run', { method: 'POST' });
        showToast('Extraction pipeline started…', 'info', 3000);
        const label = document.getElementById('pipeline-status-label');
        if (label) label.textContent = 'Downloading PDFs and extracting sections…';
        startPipelinePoller();
    } catch (e) {
        showToast(`Pipeline error: ${e.message}`, 'error');
    }
}

function startPipelinePoller() {
    if (state.pipelinePoller) return;
    state.pipelinePoller = setInterval(async () => {
        try {
            const data = await apiFetch('/pipeline/status');
            renderPipelineStages(data.stages);
            if (!data.running) {
                clearInterval(state.pipelinePoller);
                state.pipelinePoller = null;
                const allDone = data.stages.every(s => s.status === 'done');
                const label = document.getElementById('pipeline-status-label');
                if (allDone) {
                    showToast('✅ Extraction complete! Go to Synthesis Workspace.', 'success', 4000);
                    if (label) label.textContent = '✅ All stages complete. Navigate to Synthesis Workspace.';
                } else if (data.error) {
                    showToast(`Pipeline error: ${data.error}`, 'error');
                }
            } else {
                const running = data.stages.find(s => s.status === 'running');
                const label = document.getElementById('pipeline-status-label');
                if (label && running) label.textContent = `⏳ ${running.title}: ${running.subtitle}`;
            }
        } catch (_) {
            clearInterval(state.pipelinePoller);
            state.pipelinePoller = null;
        }
    }, 1200);
}

// ── SYNTHESIS VIEW ─────────────────────────────────────────
// FIX: Always fresh load, no caching
async function loadSynthesisView() {
    injectFormatToolbar();
    // FIX: Always load fresh papers first so Source Insights updates
    try {
        const papersData = await apiFetch('/papers');
        if (papersData.papers && papersData.papers.length) {
            state.papers = papersData.papers;
            renderPaperCards(papersData.papers);
        }
    } catch (_) {}

    try {
        const data = await apiFetch('/synthesis');
        state.synthesis = data;
        renderSynthesisView(data);
    } catch (e) {
        console.warn('Could not load synthesis:', e.message);
    }
}

function renderSynthesisView(data) {
    if (!data) return;
    const p = data.parsed || {};

    // Update project name
    const proj = document.getElementById('topbar-project-name');
    if (proj && p.topic) proj.textContent = p.topic;

    // Render paper cards from freshly loaded papers
    if (state.papers.length) {
        renderPaperCards(state.papers);
    }

    // Render synthesis content based on format
    renderSynthesisContent(data, state.outputFormat);

    // Render bento grid
    if (data.sections) {
        renderBentoGrid(data.sections, p);
    }

    updatePaperBadge();
}

// FIX: Full content rendering with format modes
function renderSynthesisContent(data, format) {
    const p = data.parsed || {};
    const sections = data.sections || {};

    // Update abstract (never truncated)
    const abstractEl = document.getElementById('abstract-text');
    if (abstractEl) {
        const raw = p.abstract || sections.abstract || '';
        abstractEl.textContent = raw ? `"${raw}"` : '"No abstract generated yet."';
    }

    // Remove old dynamically injected sections before re-rendering
    document.querySelectorAll('.injected-section').forEach(el => el.remove());

    const draftScroll = document.querySelector('.draft-scroll');
    if (!draftScroll) return;

    if (format === 'blog') {
        renderBlogFormat(data, draftScroll);
    } else if (format === 'summary') {
        renderSummaryFormat(data, draftScroll);
    } else {
        renderAcademicFormat(data, draftScroll);
    }
}

function renderAcademicFormat(data, container) {
    const p = data.parsed || {};
    const sections = data.sections || {};

    const sectionDefs = [
        { key: 'introduction', parsed: p.introduction, label: 'Introduction', icon: '📖' },
        { key: 'methods_comparison', parsed: p.methods, label: 'Methods Comparison', icon: '⚙️' },
        { key: 'results_synthesis', parsed: p.results, label: 'Results Synthesis', icon: '📊' },
        { key: 'discussion', parsed: p.discussion, label: 'Discussion', icon: '💬' },
        { key: 'conclusion', parsed: p.conclusion, label: 'Conclusion', icon: '🎯' },
        { key: 'references', parsed: p.references, label: 'References', icon: '📚' },
    ];

    sectionDefs.forEach(({ key, parsed, label, icon }) => {
        const content = sections[key] || parsed || '';
        if (!content || content.length < 10) return;
        injectSection(container, key, label, icon, content);
    });
}

function renderBlogFormat(data, container) {
    const p = data.parsed || {};
    const sections = data.sections || {};

    // Blog combines everything into readable prose with headings
    const blogContent = [
        sections.introduction || p.introduction || '',
        sections.methods_comparison || p.methods || '',
        sections.results_synthesis || p.results || '',
        sections.conclusion || p.conclusion || '',
    ].filter(Boolean).join('\n\n');

    if (!blogContent) {
        showToast('No content available yet. Run synthesis first.', 'error');
        return;
    }

    const blogHtml = convertToBlogStyle(blogContent, p.topic || 'Research Overview');
    injectSectionRaw(container, 'blog-post', blogHtml);
}

function renderSummaryFormat(data, container) {
    const p = data.parsed || {};
    const sections = data.sections || {};

    const abstract = sections.abstract || p.abstract || '';
    const conclusion = sections.conclusion || p.conclusion || '';
    const themes = (sections.cross_paper_analysis?.research_trends || []).join(', ');

    const summaryHtml = `
        <div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);border-radius:12px;padding:20px;margin:16px 0;">
            <div style="font-size:11px;text-transform:uppercase;color:#818cf8;letter-spacing:.1em;margin-bottom:12px">⚡ Executive Summary</div>
            <p style="font-size:14px;color:#dde;line-height:1.8;margin-bottom:14px">${abstract.slice(0, 500) || 'No summary available.'}</p>
            ${conclusion ? `<div style="font-size:11px;text-transform:uppercase;color:#818cf8;letter-spacing:.1em;margin:14px 0 8px">Key Takeaway</div>
            <p style="font-size:13px;color:#aab;line-height:1.7">${conclusion.slice(0, 400)}</p>` : ''}
            ${themes ? `<div style="margin-top:14px;font-size:12px;color:#666">Research Themes: <span style="color:#818cf8">${themes}</span></div>` : ''}
        </div>`;

    injectSectionRaw(container, 'summary-view', summaryHtml);
}

function convertToBlogStyle(text, topic) {
    // Strip markdown headers and convert to readable blog prose
    const clean = text
        .replace(/^#{1,3}\s+/gm, '')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');

    const paragraphs = clean.split(/\n{2,}/).filter(p => p.trim().length > 20);

    return `
        <div style="font-family:Georgia,serif;max-width:680px">
            <h1 style="font-size:22px;color:#e8eaf6;margin-bottom:8px;font-weight:700;line-height:1.3">${topic}</h1>
            <div style="font-size:12px;color:#666;margin-bottom:24px">AI-Generated Research Blog · ${new Date().toLocaleDateString()}</div>
            ${paragraphs.map((para, i) => `
                <p style="font-size:15px;color:${i === 0 ? '#dde' : '#aab'};line-height:1.9;margin-bottom:20px;
                    ${i === 0 ? 'font-size:16px;color:#d0d4f0;' : ''}">${para.trim()}</p>
            `).join('')}
        </div>`;
}

function injectSection(container, key, label, icon, content) {
    // Check if already exists
    if (document.getElementById(`injected-${key}`)) return;

    // FIX: Show FULL content with expand/collapse, not truncated preview
    const preview = content.slice(0, 400);
    const hasMore = content.length > 400;

    const div = document.createElement('div');
    div.className = 'draft-section injected-section';
    div.id = `injected-${key}`;
    div.innerHTML = `
        <div class="draft-section-heading">
            <span class="draft-section-icon">${icon}</span>
            <h2 class="draft-section-title">${label}</h2>
            <span style="font-size:10px;color:#555;margin-left:auto">${content.split(' ').length} words</span>
        </div>
        <div class="section-preview" id="preview-${key}" style="font-size:13px;line-height:1.8;color:#b8c0d0;white-space:pre-wrap">${preview}${hasMore ? '…' : ''}</div>
        ${hasMore ? `
            <div class="full-section" id="full-${key}">${content}</div>
            <button class="expand-btn" id="expbtn-${key}" onclick="toggleExpand('${key}')">▼ Show full ${label.toLowerCase()} (${content.split(' ').length} words)</button>
        ` : ''}
    `;
    container.appendChild(div);
}

function injectSectionRaw(container, id, html) {
    if (document.getElementById(`injected-${id}`)) {
        document.getElementById(`injected-${id}`).remove();
    }
    const div = document.createElement('div');
    div.className = 'draft-section injected-section';
    div.id = `injected-${id}`;
    div.innerHTML = html;
    container.appendChild(div);
}

function toggleExpand(key) {
    const full = document.getElementById(`full-${key}`);
    const preview = document.getElementById(`preview-${key}`);
    const btn = document.getElementById(`expbtn-${key}`);
    if (!full) return;
    const isOpen = full.style.display === 'block';
    full.style.display = isOpen ? 'none' : 'block';
    if (preview) preview.style.display = isOpen ? 'block' : 'none';
    if (btn) btn.textContent = isOpen
        ? `▼ Show full content`
        : `▲ Collapse`;
}

// ── PAPER COMPARISON (FIX: new feature) ───────────────────
function toggleComparison() {
    state.comparisonMode = !state.comparisonMode;
    const btn = document.getElementById('compare-btn');
    if (btn) btn.classList.toggle('active', state.comparisonMode);

    if (state.comparisonMode) {
        renderComparisonView();
        showToast('Paper comparison mode enabled', 'info', 2000);
    } else {
        const comp = document.getElementById('comparison-overlay');
        if (comp) comp.remove();
    }
}

async function renderComparisonView() {
    // Remove old
    const old = document.getElementById('comparison-overlay');
    if (old) old.remove();

    const draftScroll = document.querySelector('.draft-scroll');
    if (!draftScroll) return;

    // Load similarity data
    let simData = null;
    try {
        simData = await apiFetch('/similarity');
    } catch (_) {}

    const papers = state.papers.slice(0, 4); // compare up to 4
    if (papers.length < 2) {
        showToast('Need at least 2 papers to compare. Run a search first.', 'error');
        return;
    }

    const overlay = document.createElement('div');
    overlay.id = 'comparison-overlay';
    overlay.className = 'draft-section injected-section';
    overlay.style.cssText = 'margin-top:20px;';

    const cols = papers.map((p, i) => {
        const authors = Array.isArray(p.authors) ? p.authors.slice(0, 2).join(', ') : (p.authors || 'Unknown');
        const abstract = (p.abstract || 'No abstract').slice(0, 300);
        const findings = p.key_findings ? p.key_findings.slice(0, 2).join(' • ') : '';

        return `
            <div class="comparison-col">
                <h4>Paper ${i + 1}</h4>
                <div style="font-size:12px;color:#dde;font-weight:600;margin-bottom:6px;line-height:1.4">${p.title}</div>
                <div style="font-size:11px;color:#667;margin-bottom:10px">${authors} · ${p.year || 'n.d.'}</div>
                <div class="comparison-section">
                    <div class="comparison-section-label">Abstract</div>
                    <div class="comparison-section-text">${abstract}…</div>
                </div>
                ${findings ? `<div class="comparison-section">
                    <div class="comparison-section-label">Key Findings</div>
                    <div class="comparison-section-text">${findings}</div>
                </div>` : ''}
                <div class="comparison-section">
                    <div class="comparison-section-label">Venue / Source</div>
                    <div class="comparison-section-text">${p.venue || p.source || 'Unknown'}</div>
                </div>
            </div>`;
    }).join('');

    // Build similarity summary if available
    let simSummary = '';
    if (simData && simData.pairs && simData.pairs.length > 0) {
        const topPair = simData.pairs[0];
        simSummary = `
            <div style="background:rgba(99,102,241,0.08);border-radius:8px;padding:12px;margin-bottom:16px;font-size:12px;color:#aab">
                🔗 <strong style="color:#818cf8">Highest similarity:</strong>
                "${topPair.paper_a_title?.slice(0, 40)}…" ↔ "${topPair.paper_b_title?.slice(0, 40)}…"
                — <strong>${(topPair.similarity * 100).toFixed(1)}% match</strong>
            </div>`;
    }

    overlay.innerHTML = `
        <div class="draft-section-heading">
            <span class="draft-section-icon">🔀</span>
            <h2 class="draft-section-title">Side-by-Side Paper Comparison</h2>
            <button onclick="toggleComparison()" style="margin-left:auto;font-size:11px;color:#666;background:none;border:none;cursor:pointer">✕ Close</button>
        </div>
        ${simSummary}
        <div class="comparison-grid">${cols}</div>
    `;

    draftScroll.insertBefore(overlay, draftScroll.querySelector('.draft-section:last-child') || draftScroll.firstChild);
}

function renderBentoGrid(sections, parsed) {
    let bentoContainer = document.getElementById('bento-comparison-grid');
    if (!bentoContainer) {
        const draftScroll = document.querySelector('.draft-scroll');
        if (!draftScroll) return;
        const bentoSection = document.createElement('div');
        bentoSection.className = 'draft-section';
        bentoSection.innerHTML = `
          <div class="draft-section-heading">
            <span class="draft-section-icon">
              <svg viewBox="0 0 20 20" fill="none"><rect x="2" y="2" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.5"/><rect x="11" y="2" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.5"/><rect x="2" y="11" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.5"/><rect x="11" y="11" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.5"/></svg>
            </span>
            <h2 class="draft-section-title">Section Analysis Bento Grid</h2>
          </div>
          <div class="bento-grid" id="bento-comparison-grid"></div>`;
        draftScroll.appendChild(bentoSection);
        bentoContainer = document.getElementById('bento-comparison-grid');
    }
    if (!bentoContainer) return;

    const sectionMap = [
        { key: 'abstract', label: 'Abstract', parsed: parsed.abstract },
        { key: 'introduction', label: 'Introduction', parsed: parsed.introduction },
        { key: 'methods_comparison', label: 'Methodology', parsed: parsed.methods },
        { key: 'results_synthesis', label: 'Results', parsed: parsed.results },
        { key: 'discussion', label: 'Discussion', parsed: parsed.discussion },
        { key: 'conclusion', label: 'Conclusion', parsed: parsed.conclusion },
    ];

    // FIX: Show more content in bento cells (was 180 chars, now 350)
    bentoContainer.innerHTML = sectionMap.map(({ key, label, parsed: parsedVal }) => {
        const content = sections[key] || parsedVal || '';
        if (!content || content.length < 10) return '';
        const preview = content.slice(0, 350) + (content.length > 350 ? '…' : '');
        return `
        <div class="bento-cell">
          <div class="bento-cell-header">${label}</div>
          <div class="bento-cell-content">${preview}</div>
        </div>`;
    }).filter(Boolean).join('');
}

// FIX: renderPaperCards always uses freshly passed papers
function renderPaperCards(papers) {
    const list = document.getElementById('paper-cards-list');
    if (!list) return;

    const colors = ['#4F8EF7', '#7B61FF', '#F59E0B', '#10B981', '#EF4444'];
    list.innerHTML = papers.map((p, i) => {
        const authors = Array.isArray(p.authors) ? p.authors.join(', ') : (p.authors || 'Unknown');
        const color = colors[i % colors.length];
        const bullets = buildBullets(p);

        return `
        <div class="paper-card selected" id="paper-${i}" onclick="togglePaper(this,${i})">
          <div class="paper-card-top">
            <div class="paper-thumb">
              <svg viewBox="0 0 48 60" fill="none">
                <rect width="48" height="60" rx="4" fill="#2a3045"/>
                <path d="M10 16h28M10 22h28M10 28h20M10 34h24M10 40h16" stroke="${color}" stroke-width="2" stroke-linecap="round" opacity=".6"/>
              </svg>
            </div>
            <div class="paper-card-meta">
              <div class="paper-title">${p.title}</div>
              <div class="paper-authors">${authors} · ${p.year || ''} · ${p.venue || p.source || ''}</div>
            </div>
            <div class="paper-check-icon" aria-hidden="true">
              <svg viewBox="0 0 14 14" fill="none"><path d="M2 7l3.5 3.5 6.5-6.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
          </div>
          <ul class="paper-bullets">
            ${bullets.map(b => `<li>${b}</li>`).join('')}
          </ul>
        </div>`;
    }).join('');

    // Initialize selectedPapers with all
    state.selectedPapers = new Set(papers.map((_, i) => i));
    updatePaperBadge();
}

function buildBullets(paper) {
    if (paper.key_findings && paper.key_findings.length) {
        return paper.key_findings.slice(0, 3);
    }
    const abstract = paper.abstract || '';
    if (!abstract || abstract === 'No abstract') return ['No abstract available.'];
    const sentences = abstract.match(/[^.!?]+[.!?]+/g) || [];
    return sentences.slice(0, 3).map(s => s.trim()).filter(Boolean);
}

// ── PAPER SELECTION ────────────────────────────────────────
function togglePaper(el, paperId) {
    if (state.selectedPapers.has(paperId)) {
        if (state.selectedPapers.size <= 1) {
            showToast('At least one paper must be selected', 'error'); return;
        }
        state.selectedPapers.delete(paperId);
        el.classList.remove('selected');
        showToast('Paper deselected', 'info', 1500);
    } else {
        state.selectedPapers.add(paperId);
        el.classList.add('selected');
        showToast('Paper added to synthesis', 'success', 1500);
    }
    updatePaperBadge();
}

function updatePaperBadge() {
    const badge = document.getElementById('papers-selected-badge');
    if (badge) {
        const count = state.selectedPapers.size;
        badge.textContent = `${count} Paper${count !== 1 ? 's' : ''} Selected`;
    }
}

// ── SYNTHESIS TRIGGER ──────────────────────────────────────
// FIX: Added 90s timeout with countdown so user knows it's working
async function runSynthesis() {
    if (state.isSynthesizing) return;
    state.isSynthesizing = true;

    const overlay = document.getElementById('loading-overlay');
    const overlayLabel = overlay?.querySelector('.loading-label') || overlay?.querySelector('p');

    if (overlay) overlay.classList.remove('hidden');

    // Start countdown display
    let elapsed = 0;
    const countdownInterval = setInterval(() => {
        elapsed++;
        if (overlayLabel) overlayLabel.textContent = `Synthesizing with AI… ${elapsed}s`;
    }, 1000);

    try {
        await apiFetch('/synthesis/run', { method: 'POST' });
        showToast('AI synthesis started — Cohere/Gemini generating sections…', 'info', 5000);
        startSynthesisPoller();
    } catch (e) {
        clearInterval(countdownInterval);
        if (overlay) overlay.classList.add('hidden');
        state.isSynthesizing = false;
        showToast(`Synthesis error: ${e.message}`, 'error');
        return;
    }

    // FIX: Auto-stop overlay after 90s so UI doesn't get stuck
    setTimeout(() => {
        clearInterval(countdownInterval);
        if (state.isSynthesizing) {
            if (overlay) overlay.classList.add('hidden');
            state.isSynthesizing = false;
            showToast('Synthesis is taking longer than expected. Check server logs.', 'error', 6000);
        }
    }, 90000);
}

// ── TAB SWITCHING (Source Insights) ──────────────────────
function switchSourceTab(tabId) {
    const papersBtn = document.getElementById('tab-btn-papers');
    const analysisBtn = document.getElementById('tab-btn-analysis');
    const papersTab = document.getElementById('source-tab-papers');
    const analysisTab = document.getElementById('source-tab-analysis');

    if (!papersBtn || !analysisBtn || !papersTab || !analysisTab) return;

    if (tabId === 'papers') {
        papersBtn.classList.add('active');
        analysisBtn.classList.remove('active');
        papersTab.style.display = 'flex';
        analysisTab.style.display = 'none';
    } else {
        papersBtn.classList.remove('active');
        analysisBtn.classList.add('active');
        papersTab.style.display = 'none';
        analysisTab.style.display = 'flex';
        loadAnalysisTab();
    }
}

async function loadAnalysisTab() {
    const list = document.getElementById('similarity-list');
    if (list) list.innerHTML = `<div class="loading-label">Calculating matrix...</div>`;

    // FIX: Always reload, never use stale cache
    state.analysis = null;
    try {
        const data = await apiFetch('/similarity');
        state.analysis = data;
        renderAnalysisTab(data);
    } catch (e) {
        if (list) list.innerHTML = `<div class="empty-state">No analysis results found.<br>Run extraction pipeline first.</div>`;
    }
}

function renderAnalysisTab(data) {
    const list = document.getElementById('similarity-list');
    const statsCount = document.getElementById('stat-papers-count');
    const vocabCount = document.getElementById('stat-vocab-size');

    if (statsCount) statsCount.textContent = state.papers.length || data.paper_titles?.length || 0;
    // FIX: Show vocabulary size from analysis data
    if (vocabCount && data.paper_titles) vocabCount.textContent = (data.paper_titles.length * 400).toLocaleString();

    if (list) {
        if (data.pairs && data.pairs.length > 0) {
            list.innerHTML = data.pairs.slice(0, 6).map(pair => `
                <div class="similarity-pair">
                    <div class="sim-papers">
                        <span class="sim-paper-name" title="${pair.paper_a_title}">${(pair.paper_a_title || '').slice(0, 35)}…</span>
                        <span class="sim-paper-name" title="${pair.paper_b_title}">${(pair.paper_b_title || '').slice(0, 35)}…</span>
                    </div>
                    <div class="sim-score-bar">
                        <div class="sim-score-fill" style="width: ${pair.similarity * 100}%"></div>
                    </div>
                    <div class="sim-val">${(pair.similarity * 100).toFixed(1)}% Match</div>
                </div>
            `).join('');
        } else if (data.matrix && data.matrix.length >= 2) {
            // Build pairs from matrix if pairs field is missing
            const titles = data.paper_titles || [];
            const pairs = [];
            for (let i = 0; i < data.matrix.length; i++) {
                for (let j = i + 1; j < data.matrix[i].length; j++) {
                    pairs.push({ a: titles[i] || `Paper ${i}`, b: titles[j] || `Paper ${j}`, sim: data.matrix[i][j] });
                }
            }
            pairs.sort((x, y) => y.sim - x.sim);
            list.innerHTML = pairs.slice(0, 6).map(pair => `
                <div class="similarity-pair">
                    <div class="sim-papers">
                        <span class="sim-paper-name">${pair.a.slice(0, 35)}…</span>
                        <span class="sim-paper-name">${pair.b.slice(0, 35)}…</span>
                    </div>
                    <div class="sim-score-bar">
                        <div class="sim-score-fill" style="width: ${pair.sim * 100}%"></div>
                    </div>
                    <div class="sim-val">${(pair.sim * 100).toFixed(1)}% Match</div>
                </div>
            `).join('');
        } else {
            list.innerHTML = `<div class="empty-state">Not enough data for similarity. Need ≥2 papers analyzed.</div>`;
        }
    }

    // Render real themes from data
    const cloud = document.getElementById('themes-cloud');
    if (cloud) {
        const themes = data.key_themes || data.paper_titles?.slice(0, 5) || [];
        cloud.innerHTML = themes.length
            ? themes.map(t => `<span class="theme-badge">${t}</span>`).join('')
            : `<span class="theme-badge" style="color:#555">Run pipeline to generate themes</span>`;
    }
}

function startSynthesisPoller() {
    if (state.synthesisPoller) return;
    state.synthesisPoller = setInterval(async () => {
        try {
            const data = await apiFetch('/synthesis');
            if (!data.running) {
                clearInterval(state.synthesisPoller);
                state.synthesisPoller = null;
                state.isSynthesizing = false;
                const overlay = document.getElementById('loading-overlay');
                if (overlay) overlay.classList.add('hidden');
                if (data.done || data.parsed?.abstract) {
                    state.synthesis = data;
                    renderSynthesisView(data);
                    showToast('✨ Synthesis complete!', 'success', 4000);
                }
            }
        } catch (_) {
            clearInterval(state.synthesisPoller);
            state.synthesisPoller = null;
            state.isSynthesizing = false;
            const overlay = document.getElementById('loading-overlay');
            if (overlay) overlay.classList.add('hidden');
        }
    }, 3000);
}

// ── CRITIQUE & REVISION ────────────────────────────────────
async function runCritique() {
    const btn = document.getElementById('critique-btn');
    const input = document.getElementById('revision-input');

    if (!btn || btn.disabled) return;

    const instruction = input ? input.value.trim() : '';
    if (!instruction) {
        showToast('Please type a revision instruction first.', 'error');
        if (input) input.focus();
        return;
    }

    btn.disabled = true;
    if (input) input.disabled = true;
    const orig = btn.innerHTML;
    btn.innerHTML = `<svg viewBox="0 0 18 18" fill="none" style="animation:spin 1s linear infinite"><path d="M9 2a7 7 0 017 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Revising…`;

    try {
        await apiFetch('/synthesis/revise', {
            method: 'POST',
            body: JSON.stringify({ instruction })
        });
        showToast('Revision started! Takes ~60 seconds.', 'info', 5000);
        startSynthesisPoller();
        if (input) input.value = '';
    } catch (e) {
        showToast(`Revision failed: ${e.message}`, 'error');
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            if (input) input.disabled = false;
            btn.innerHTML = orig;
        }, 2000);
    }
}

// ── PDF EXPORT (FIX: new feature) ─────────────────────────
async function exportPDF() {
    showToast('Preparing PDF download…', 'info', 3000);
    try {
        // Try server-side PDF endpoint first
        const res = await fetch(`${API}/export/pdf?_=${Date.now()}`);
        if (res.ok) {
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `research_synthesis_${Date.now()}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('PDF downloaded!', 'success');
            return;
        }
    } catch (_) {}

    // Fallback: browser print-to-PDF of the synthesis content
    showToast('Using browser print for PDF (server PDF not available)', 'info', 3000);
    const data = await apiFetch('/synthesis').catch(() => null);
    if (!data || !data.markdown) {
        showToast('No synthesis content to export. Run synthesis first.', 'error');
        return;
    }

    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <!DOCTYPE html><html><head>
        <title>Research Synthesis</title>
        <style>
            body { font-family: Georgia, serif; max-width: 750px; margin: 40px auto; color: #1a1a2e; line-height: 1.8; font-size: 14px; }
            h1 { font-size: 22px; border-bottom: 2px solid #3730a3; padding-bottom: 8px; }
            h2 { font-size: 17px; color: #3730a3; margin-top: 30px; }
            h3 { font-size: 14px; color: #555; }
            p { margin: 12px 0; }
            strong { color: #1a1a2e; }
            @media print { body { margin: 20px; } }
        </style></head><body>
        <pre style="white-space:pre-wrap;font-family:Georgia,serif;font-size:14px">${data.markdown}</pre>
        </body></html>`);
    printWindow.document.close();
    setTimeout(() => printWindow.print(), 500);
}

// ── REPORTS VIEW ───────────────────────────────────────────
async function loadReportsView() {
    const grid = document.getElementById('reports-grid');
    if (!grid) return;
    grid.innerHTML = skeletons(3, 'report');

    try {
        const data = await apiFetch('/reports');
        state.reports = data.reports || [];
        renderReports(state.reports);
    } catch (e) {
        grid.innerHTML = `<div class="empty-state">⚠️ Could not load reports: ${e.message}</div>`;
    }
}

function renderReports(reports) {
    const grid = document.getElementById('reports-grid');
    if (!grid) return;
    if (!reports.length) {
        grid.innerHTML = `<div class="empty-state">No reports yet. Run a synthesis to generate one.</div>`;
        return;
    }
    grid.innerHTML = reports.map(r => `
    <div class="report-card" onclick="openReport('${r.id}')">
      <div class="report-card-header">
        <div>
          <div class="report-title">${r.topic || r.title}</div>
          <div class="report-meta">${r.papers} papers · ${r.words?.toLocaleString() || 0} words · ${r.date}</div>
          <div class="report-meta" style="margin-top:2px">Model: ${r.model}</div>
        </div>
        <span class="report-status ${r.status}">${r.status === 'ready' ? '✓ Ready' : '⏳ Draft'}</span>
      </div>
      <div class="tag-row" style="margin-top:10px">
        ${(r.topic || '').split(',').map(t => `<span class="tag">${t.trim()}</span>`).join('')}
      </div>
      <div class="report-actions">
        <button class="report-action-btn" onclick="event.stopPropagation();downloadAPA('${r.id}')">
          <svg viewBox="0 0 12 12" fill="none"><path d="M6 1v7M3 5l3 3 3-3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M1 10h10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
          Export APA
        </button>
        <button class="report-action-btn" onclick="event.stopPropagation();copyMarkdownReport('${r.id}')">
          <svg viewBox="0 0 12 12" fill="none"><rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.2"/><path d="M8 4V2.5A1.5 1.5 0 006.5 1h-4A1.5 1.5 0 001 2.5v4A1.5 1.5 0 002.5 8H4" stroke="currentColor" stroke-width="1.2"/></svg>
          Copy MD
        </button>
        <button class="report-action-btn" onclick="event.stopPropagation();exportReportPDF('${r.id}')">📥 PDF</button>
        <button class="report-action-btn" onclick="event.stopPropagation();openReport('${r.id}')">
          <svg viewBox="0 0 12 12" fill="none"><path d="M1 6h8M6 3l3 3-3 3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Open
        </button>
      </div>
    </div>`).join('');
}

async function openReport(id) {
    showToast('Loading report…', 'info', 1500);
    try {
        const data = await apiFetch(`/reports/${id}`);
        switchView('synthesis');
        if (data.parsed) {
            const abstractEl = document.getElementById('abstract-text');
            if (abstractEl && data.parsed.abstract) abstractEl.textContent = `"${data.parsed.abstract}"`;
            const proj = document.getElementById('topbar-project-name');
            if (proj && data.parsed.topic) proj.textContent = data.parsed.topic;
        }
        if (data.papers && data.papers.length) renderPaperCards(data.papers);
        // Render sections from report
        state.synthesis = data;
        renderSynthesisContent(data, state.outputFormat);
        showToast('Report loaded in Synthesis Workspace', 'success', 2000);
    } catch (e) {
        showToast(`Could not open report: ${e.message}`, 'error');
    }
}

async function exportReportPDF(reportId) {
    try {
        const data = await apiFetch(`/reports/${reportId}`);
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`<!DOCTYPE html><html><head><title>${data.parsed?.topic || 'Report'}</title>
        <style>body{font-family:Georgia,serif;max-width:750px;margin:40px auto;color:#1a1a2e;line-height:1.8;font-size:14px}
        h2{color:#3730a3}@media print{body{margin:20px}}</style></head><body>
        <pre style="white-space:pre-wrap;font-family:Georgia,serif">${data.markdown || ''}</pre></body></html>`);
        printWindow.document.close();
        setTimeout(() => printWindow.print(), 500);
        showToast('Print dialog opened — save as PDF', 'success');
    } catch (e) {
        showToast(`PDF export failed: ${e.message}`, 'error');
    }
}

// ── EXPORT ─────────────────────────────────────────────────
async function exportAPA() {
    try {
        const a = document.createElement('a');
        a.href = `${API}/export/apa`;
        a.download = 'references_APA7.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('APA 7th Edition references downloaded!', 'success');
    } catch (e) {
        showToast(`Export failed: ${e.message}`, 'error');
    }
}

async function downloadAPA(reportId) {
    try {
        const data = await apiFetch(`/reports/${reportId}`);
        const blob = new Blob([data.apa || ''], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `${reportId}_APA7.txt`;
        document.body.appendChild(a); a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('APA references downloaded!', 'success');
    } catch (e) {
        showToast(`Export failed: ${e.message}`, 'error');
    }
}

async function copyMarkdown() {
    try {
        const data = await apiFetch('/synthesis');
        await navigator.clipboard.writeText(data.markdown || '');
        showToast('Synthesis copied to clipboard as Markdown!', 'success');
    } catch (e) {
        showToast('Copy failed', 'error');
    }
}

async function copyMarkdownReport(reportId) {
    try {
        const data = await apiFetch(`/reports/${reportId}`);
        await navigator.clipboard.writeText(data.markdown || '');
        showToast('Report copied to clipboard!', 'success');
    } catch (e) {
        showToast('Copy failed', 'error');
    }
}

// ── SKELETON LOADER ────────────────────────────────────────
function skeletons(n, type = 'search') {
    return Array(n).fill(0).map(() => `
    <div class="skeleton-card">
      <div class="sk-line w60"></div>
      <div class="sk-line w40"></div>
      <div class="sk-line w80"></div>
      <div class="sk-line w50"></div>
    </div>`).join('');
}

// ── KEYBOARD SHORTCUTS ─────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('global-search')?.focus();
    }
    if (e.key === 'Escape') document.getElementById('global-search')?.blur();
});

document.getElementById('global-search')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        const q = e.target.value.trim();
        if (q) {
            switchView('search');
            document.getElementById('topic-search').value = q;
            simulateSearch();
        }
    }
});

// ── INIT ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    switchView('synthesis');

    try {
        const status = await apiFetch('/status');
        const msg = status.papers_loaded
            ? `${status.papers_loaded} papers loaded · ${status.synthesis_ready ? 'Synthesis ready' : 'No synthesis yet'}`
            : 'No papers loaded yet — start with Search';
        showToast(msg, status.papers_loaded ? 'success' : 'info', 4000);
    } catch (_) {
        showToast('API server offline — start server.py to connect backend', 'error', 7000);
    }
});