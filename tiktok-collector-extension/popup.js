'use strict';
// WordAI TikTok Collector — Popup script

// ─── State ────────────────────────────────────────────────────────────────────
let tiktokTabId = null;
let currentUser = null;  // { uid, secUid, uniqueId, nickname }
let activeTab = 'likes';
let downloadedIds = new Set(); // persisted in chrome.storage

const S = {
    likes: {
        items: [], cursor: 0, hasMore: false, loading: false,
        selected: new Set()
    },
    saved: {
        items: [], cursor: 0, hasMore: false, loading: false,
        selected: new Set()
    },
    my: {
        items: [], cursor: 0, hasMore: false, loading: false,
        selected: new Set()
    },
    following: {
        authors: [], maxCursor: 0, minCursor: 0, hasMore: false, loading: false,
        selectedAuthors: new Set(),
        posts: { items: [], loading: false, selected: new Set() }
    }
};

// ─── Storage ──────────────────────────────────────────────────────────────────
async function loadStorage() {
    const r = await chrome.storage.local.get(['downloadedIds']);
    downloadedIds = new Set(r.downloadedIds || []);
}

async function saveDownloaded() {
    await chrome.storage.local.set({ downloadedIds: [...downloadedIds] });
}

// ─── Chrome helpers ───────────────────────────────────────────────────────────
async function findTikTokTab() {
    let tabs = await chrome.tabs.query({ url: 'https://www.tiktok.com/*', active: true, currentWindow: true });
    if (!tabs.length) tabs = await chrome.tabs.query({ url: 'https://www.tiktok.com/*' });
    return tabs.length ? tabs[0] : null;
}

function sendToContent(action, params = {}) {
    return new Promise((resolve, reject) => {
        if (!tiktokTabId) return reject(new Error('No TikTok tab found. Open tiktok.com first.'));
        chrome.tabs.sendMessage(tiktokTabId, { action, ...params }, (resp) => {
            if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
            if (!resp) return reject(new Error('No response from TikTok tab. Try refreshing.'));
            if (resp.error) return reject(new Error(resp.error));
            resolve(resp);
        });
    });
}

// ─── UI helpers ───────────────────────────────────────────────────────────────
function setStatus(msg, type = 'info') {
    const bar = document.getElementById('status-bar');
    const icon = document.getElementById('status-icon');
    const text = document.getElementById('status-text');
    bar.className = type;
    icon.textContent = type === 'ok' ? '✓' : type === 'err' ? '✗' : '⟳';
    text.textContent = msg;
    bar.classList.remove('hidden');
}
function hideStatus() { document.getElementById('status-bar').classList.add('hidden'); }

function fmt(n) {
    if (n == null) return '0';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(n);
}

function fmtDate(iso) {
    if (!iso) return '';
    return iso.split('T')[0];
}

// ─── Post item renderer ───────────────────────────────────────────────────────
function makePostEl(item, tabKey) {
    const isDone = downloadedIds.has(item.id);
    const sel = tabKey === 'followingPosts'
        ? S.following.posts.selected
        : S[tabKey].selected;
    const checked = sel.has(item.id);

    const el = document.createElement('div');
    el.className = 'post-item' + (isDone ? ' downloaded' : '');
    el.dataset.id = item.id;
    el.dataset.tabKey = tabKey;

    const typeLabel = item.media_type === 'image'
        ? `<span class="post-type image">🖼 ${item.image_count || ''}img</span>`
        : '<span class="post-type video">🎬 video</span>';

    const authorHtml = (tabKey === 'followingPosts' && item.author && item.author.username)
        ? `<span class="post-author">${escHtml(item.author.username)}</span>` : '';

    const doneHtml = isDone ? '<span class="post-done">✓ collected</span>' : '';

    el.innerHTML = `
    <input type="checkbox" class="post-cb" ${checked ? 'checked' : ''}>
    <div class="post-body">
      <div class="post-meta">
        <span class="post-date">${fmtDate(item.created_date || item.created_at)}</span>
        ${typeLabel}
        ${authorHtml}
        ${doneHtml}
      </div>
      <div class="post-desc">${escHtml(item.desc || '(No caption)')}</div>
      <div class="post-stats">
        <span>❤️ ${fmt(item.stats.likes)}</span>
        <span>▶️ ${fmt(item.stats.plays)}</span>
        <span>💬 ${fmt(item.stats.comments)}</span>
      </div>
    </div>`;

    el.querySelector('.post-cb').addEventListener('change', function (e) {
        if (e.target.checked) sel.add(item.id);
        else sel.delete(item.id);
        e.stopPropagation();
        updateSelBar(tabKey === 'followingPosts' ? 'followingPosts' : tabKey);
        updateFooter();
    });

    el.addEventListener('click', function (e) {
        if (e.target.tagName === 'INPUT') return;
        const cb = el.querySelector('.post-cb');
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change', { bubbles: true }));
    });

    return el;
}

function makeAccountEl(author) {
    const sel = S.following.selectedAuthors;
    const checked = sel.has(author.id);

    const el = document.createElement('div');
    el.className = 'account-item';
    el.dataset.id = author.id;

    el.innerHTML = `
    <input type="checkbox" class="acc-cb" ${checked ? 'checked' : ''}>
    <div class="account-avatar">
      ${author.avatar ? `<img src="${escHtml(author.avatar)}" alt="">` : ''}
    </div>
    <div class="account-details">
      <div class="account-nick">${escHtml(author.nickname || author.username)}</div>
      <div class="account-user">@${escHtml(author.username)}</div>
    </div>
    <div class="account-info">
      <div>${fmt(author.videoCount)} posts</div>
      <div>${fmt(author.followerCount)} followers</div>
    </div>`;

    el.querySelector('.acc-cb').addEventListener('change', function (e) {
        if (e.target.checked) sel.add(author.id);
        else sel.delete(author.id);
        e.stopPropagation();
        updateAccountSelBar();
    });

    el.addEventListener('click', function (e) {
        if (e.target.tagName === 'INPUT') return;
        const cb = el.querySelector('.acc-cb');
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change', { bubbles: true }));
    });

    return el;
}

function escHtml(s) {
    return String(s || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ─── Selection bar updaters ───────────────────────────────────────────────────
function updateSelBar(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    const items = isFP ? S.following.posts.items : S[tabKey].items;

    if (isFP) {
        const countEl = document.getElementById('fp-sel-count');
        const chkAll = document.getElementById('fp-chk-all');
        if (countEl) countEl.textContent = sel.size ? `${sel.size} selected` : '';
        if (chkAll) chkAll.checked = sel.size === items.length && items.length > 0;
        return;
    }

    const countEl = document.getElementById(tabKey + '-sel-count');
    const chkAll = document.getElementById(tabKey + '-chk-all');
    const selBar = document.getElementById(tabKey + '-sel-bar');
    if (selBar && items.length) selBar.classList.remove('hidden');
    if (countEl) countEl.textContent = sel.size ? `${sel.size} selected` : '';
    if (chkAll) chkAll.checked = sel.size === items.length && items.length > 0;
}

function updateAccountSelBar() {
    const sel = S.following.selectedAuthors;
    const n = sel.size;
    const countEl = document.getElementById('acc-sel-count');
    const chkAll = document.getElementById('acc-chk-all');
    const loadBtn = document.getElementById('btn-load-follow-posts');
    const nLabel = document.getElementById('acc-selected-n');
    if (countEl) countEl.textContent = n ? `${n} selected` : '';
    if (chkAll) chkAll.checked = n === S.following.authors.length && n > 0;
    if (nLabel) nLabel.textContent = n;
    if (loadBtn) loadBtn.disabled = n === 0;
}

function updateFooter() {
    const sel = activeTab === 'following'
        ? S.following.posts.selected
        : (S[activeTab] ? S[activeTab].selected : new Set());

    const total = sel.size;
    const newCount = [...sel].filter(id => !downloadedIds.has(id)).length;

    document.getElementById('total-selected-label').textContent =
        total ? `${total} post${total !== 1 ? 's' : ''} selected` : '0 selected';

    const newBadge = document.getElementById('footer-new-label');
    if (newCount > 0 && newCount < total) {
        newBadge.textContent = `${newCount} new`;
        newBadge.classList.remove('hidden');
    } else {
        newBadge.classList.add('hidden');
    }

    const disabled = total === 0;
    document.getElementById('btn-export-json').disabled = disabled;
    document.getElementById('btn-export-txt').disabled = disabled;
}

function updatePaneStats(tabKey) {
    const items = S[tabKey] ? S[tabKey].items : S.following.posts.items;
    const coll = items.filter(i => downloadedIds.has(i.id)).length;
    const newN = items.length - coll;

    const el = document.getElementById(tabKey + '-stats');
    if (!el) return;
    if (!items.length) { el.textContent = ''; return; }
    el.textContent = `${items.length} loaded · ${coll} collected · ${newN} new`;
}

// ─── Loaders ──────────────────────────────────────────────────────────────────
async function loadSimple(tabKey, action, append = false) {
    if (!currentUser) return setStatus('Connect to TikTok first.', 'err');
    const ts = S[tabKey];
    if (ts.loading) return;
    ts.loading = true;
    setStatus(`Loading ${tabKey}…`);

    try {
        const cursor = append ? ts.cursor : 0;
        if (!append) {
            ts.items = [];
            ts.cursor = 0;
            document.getElementById(tabKey + '-list').innerHTML = '';
        }

        const resp = await sendToContent(action, {
            secUid: currentUser.secUid,
            cursor,
        });

        const list = document.getElementById(tabKey + '-list');
        resp.items.forEach(item => {
            ts.items.push(item);
            list.appendChild(makePostEl(item, tabKey));
        });

        ts.cursor = resp.nextCursor;
        ts.hasMore = resp.hasMore;

        document.getElementById(tabKey + '-sel-bar').classList.remove('hidden');
        const moreBar = document.getElementById(tabKey + '-more-bar');
        if (ts.hasMore) moreBar.classList.remove('hidden');
        else moreBar.classList.add('hidden');

        updatePaneStats(tabKey);
        updateSelBar(tabKey);
        updateFooter();

        setStatus(`Loaded ${ts.items.length} posts${ts.hasMore ? ' · more available' : ''}`, 'ok');
    } catch (e) {
        setStatus(e.message, 'err');
    } finally {
        ts.loading = false;
    }
}

async function loadFollowing(append = false) {
    if (!currentUser) return setStatus('Connect to TikTok first.', 'err');
    const fs = S.following;
    if (fs.loading) return;
    fs.loading = true;
    setStatus('Loading following list…');

    try {
        const resp = await sendToContent('fetchFollowing', {
            maxCursor: append ? fs.maxCursor : 0,
            minCursor: append ? fs.minCursor : 0,
        });

        if (!append) { fs.authors = []; document.getElementById('account-list').innerHTML = ''; }

        const list = document.getElementById('account-list');
        resp.authors.forEach(a => {
            fs.authors.push(a);
            list.appendChild(makeAccountEl(a));
        });

        fs.maxCursor = resp.maxCursor;
        fs.minCursor = resp.minCursor;
        fs.hasMore = resp.hasMore;

        document.getElementById('account-section').classList.remove('hidden');
        document.getElementById('following-stats').textContent = `${fs.authors.length} accounts loaded`;

        const moreBar = document.getElementById('acc-more-bar');
        if (fs.hasMore && fs.maxCursor !== -1) moreBar.classList.remove('hidden');
        else moreBar.classList.add('hidden');

        updateAccountSelBar();
        setStatus(`Loaded ${fs.authors.length} followed accounts`, 'ok');
    } catch (e) {
        setStatus(e.message, 'err');
    } finally {
        fs.loading = false;
    }
}

async function loadFollowingPosts() {
    const selected = [...S.following.selectedAuthors];
    if (!selected.length) return;

    const newOnly = document.getElementById('follow-new-only').checked;
    const fp = S.following.posts;
    fp.loading = true;
    fp.items = [];
    fp.selected.clear();
    document.getElementById('follow-posts-list').innerHTML = '';
    document.getElementById('follow-posts-section').classList.remove('hidden');

    let done = 0;
    // Rate-limit: max 20 accounts, 350ms delay between calls
    const batch = selected.slice(0, 20);
    setStatus(`Fetching posts… 0/${batch.length} accounts`);

    for (const authorId of batch) {
        const author = S.following.authors.find(a => a.id === authorId);
        if (!author || !author.secUid) continue;

        try {
            const resp = await sendToContent('fetchUserPosts', { secUid: author.secUid, uniqueId: author.username || '', cursor: 0, autoNavigate: false });
            let items = resp.items;
            if (newOnly) items = items.filter(i => !downloadedIds.has(i.id));

            const list = document.getElementById('follow-posts-list');
            items.forEach(item => {
                fp.items.push(item);
                list.appendChild(makePostEl(item, 'followingPosts'));
            });
        } catch (_e) { /* skip this account */ }

        done++;
        setStatus(`Fetching posts… ${done}/${batch.length} accounts`);
        await new Promise(r => setTimeout(r, 350));
    }

    fp.loading = false;
    document.getElementById('fp-sel-count');
    updateSelBar('followingPosts');
    updateFooter();

    const total = fp.items.length;
    setStatus(`Loaded ${total} posts from ${done} accounts`, 'ok');
    if (selected.length > 20) setStatus(`Note: limited to first 20 accounts (${selected.length - 20} skipped)`, 'info');
}

// ─── Selection helpers ────────────────────────────────────────────────────────
function doSelectAll(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    const items = isFP ? S.following.posts.items : S[tabKey].items;
    items.forEach(i => sel.add(i.id));
    const listId = isFP ? 'follow-posts-list' : tabKey + '-list';
    document.getElementById(listId).querySelectorAll('.post-cb').forEach(cb => { cb.checked = true; });
    updateSelBar(tabKey);
    updateFooter();
}

function doDeselectAll(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    sel.clear();
    const listId = isFP ? 'follow-posts-list' : tabKey + '-list';
    document.getElementById(listId).querySelectorAll('.post-cb').forEach(cb => { cb.checked = false; });
    updateSelBar(tabKey);
    updateFooter();
}

function doSelectNew(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    const items = isFP ? S.following.posts.items : S[tabKey].items;
    sel.clear();
    const listId = isFP ? 'follow-posts-list' : tabKey + '-list';
    const checkboxes = document.getElementById(listId).querySelectorAll('.post-cb');
    items.forEach((item, idx) => {
        const isNew = !downloadedIds.has(item.id);
        if (isNew) sel.add(item.id);
        if (checkboxes[idx]) checkboxes[idx].checked = isNew;
    });
    updateSelBar(tabKey);
    updateFooter();
}

function doAccSelectAll() {
    const sel = S.following.selectedAuthors;
    S.following.authors.forEach(a => sel.add(a.id));
    document.getElementById('account-list').querySelectorAll('.acc-cb').forEach(cb => { cb.checked = true; });
    updateAccountSelBar();
}

function doAccDeselectAll() {
    S.following.selectedAuthors.clear();
    document.getElementById('account-list').querySelectorAll('.acc-cb').forEach(cb => { cb.checked = false; });
    updateAccountSelBar();
}

// ─── Export ───────────────────────────────────────────────────────────────────
function getSelectedItems() {
    const isFP = activeTab === 'following';
    const sel = isFP ? S.following.posts.selected : S[activeTab].selected;
    const items = isFP ? S.following.posts.items : S[activeTab].items;
    return items.filter(i => sel.has(i.id));
}

function buildExportData(selectedItems) {
    const source = activeTab === 'following' ? 'following' : activeTab;
    const dates = selectedItems.map(i => i.created_date).filter(Boolean).sort();
    const videos = selectedItems.filter(i => i.media_type === 'video').length;
    const images = selectedItems.filter(i => i.media_type === 'image').length;

    return {
        version: '1.0',
        exporter: 'WordAI TikTok Collector v1.0',
        exported_at: new Date().toISOString(),
        source,
        profile: currentUser ? {
            username: currentUser.uniqueId,
            nickname: currentUser.nickname,
            uid: currentUser.uid,
        } : null,
        summary: {
            total: selectedItems.length,
            videos,
            images,
            date_range: dates.length ? { earliest: dates[0], latest: dates[dates.length - 1] } : null,
        },
        posts: selectedItems.map(item => ({
            id: item.id,
            desc: item.desc,
            created_at: item.created_at,
            created_date: item.created_date,
            created_timestamp: item.created_timestamp,
            media_type: item.media_type,
            image_count: item.image_count || 0,
            stats: item.stats,
            author: item.author,
            url: item.url,
            source: item.source,
        })),
    };
}

function exportJSON() {
    const items = getSelectedItems();
    if (!items.length) return;
    const data = buildExportData(items);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `tiktok_export_${activeTab}_${dateSuffix()}.json`);
    markDownloaded(items);
}

function exportTXT() {
    const items = getSelectedItems();
    if (!items.length) return;
    const data = buildExportData(items);
    const lines = [];

    lines.push('===== WordAI TikTok Export =====');
    lines.push(`Source: ${data.source}`);
    if (data.profile) lines.push(`Account: @${data.profile.username} (${data.profile.nickname})`);
    lines.push(`Exported: ${new Date(data.exported_at).toLocaleString()}`);
    lines.push(`Total posts: ${data.summary.total} (${data.summary.videos} videos, ${data.summary.images} images)`);
    if (data.summary.date_range) {
        lines.push(`Date range: ${data.summary.date_range.earliest} → ${data.summary.date_range.latest}`);
    }
    lines.push('');

    data.posts.forEach(post => {
        lines.push('---');
        lines.push(`DATE: ${post.created_date}  |  TYPE: ${post.media_type.toUpperCase()}  |  ❤️ ${fmt(post.stats.likes)}  |  ▶️ ${fmt(post.stats.plays)}  |  💬 ${fmt(post.stats.comments)}`);
        if (post.author && post.author.username) lines.push(`ACCOUNT: @${post.author.username} (${post.author.nickname})`);
        lines.push(`DESC: ${post.desc || '(No caption)'}`);
        lines.push(`URL: ${post.url}`);
        lines.push('');
    });

    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, `tiktok_export_${activeTab}_${dateSuffix()}.txt`);
    markDownloaded(items);
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
}

async function markDownloaded(items) {
    items.forEach(i => downloadedIds.add(i.id));
    await saveDownloaded();
    // Update UI: mark items as downloaded in current list
    const isFP = activeTab === 'following';
    const listId = isFP ? 'follow-posts-list' : activeTab + '-list';
    document.getElementById(listId).querySelectorAll('.post-item').forEach(el => {
        if (downloadedIds.has(el.dataset.id)) {
            el.classList.add('downloaded');
            const doneSpan = el.querySelector('.post-done');
            if (!doneSpan) {
                const meta = el.querySelector('.post-meta');
                if (meta) meta.insertAdjacentHTML('beforeend', '<span class="post-done">✓ collected</span>');
            }
        }
    });
    updatePaneStats(activeTab === 'following' ? 'followingPosts' : activeTab);
    setStatus(`Exported & marked ${items.length} posts as collected`, 'ok');
}

function dateSuffix() {
    return new Date().toISOString().split('T')[0];
}

// ─── Connect ──────────────────────────────────────────────────────────────────
async function connect() {
    setStatus('Connecting to TikTok…');
    const tab = await findTikTokTab();
    if (!tab) {
        setStatus('Please open https://www.tiktok.com in a tab first.', 'err');
        return;
    }
    tiktokTabId = tab.id;

    try {
        const resp = await sendToContent('getContext');
        currentUser = resp.user;
        document.getElementById('user-name').textContent = `@${currentUser.uniqueId}`;
        document.getElementById('btn-connect').textContent = '✓ Connected';
        document.getElementById('btn-connect').disabled = true;
        setStatus(`Connected as @${currentUser.uniqueId} — ${currentUser.nickname}`, 'ok');
    } catch (e) {
        setStatus(e.message, 'err');
        tiktokTabId = null;
    }
}

// ─── Tab switching ────────────────────────────────────────────────────────────
function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.pane').forEach(p => p.classList.toggle('active', p.id === 'pane-' + tab));
    updateFooter();
}

// ─── Event binding ────────────────────────────────────────────────────────────
function bind() {
    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Connect
    document.getElementById('btn-connect').addEventListener('click', connect);

    // ── Likes ──
    document.getElementById('btn-load-likes').addEventListener('click', () => loadSimple('likes', 'fetchLikes'));
    document.getElementById('btn-likes-more').addEventListener('click', () => loadSimple('likes', 'fetchLikes', true));
    document.getElementById('likes-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('likes') : doDeselectAll('likes'));
    document.getElementById('likes-btn-new').addEventListener('click', () => doSelectNew('likes'));
    document.getElementById('likes-btn-none').addEventListener('click', () => doDeselectAll('likes'));

    // ── Saved ──
    document.getElementById('btn-load-saved').addEventListener('click', () => loadSimple('saved', 'fetchSaved'));
    document.getElementById('btn-saved-more').addEventListener('click', () => loadSimple('saved', 'fetchSaved', true));
    document.getElementById('saved-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('saved') : doDeselectAll('saved'));
    document.getElementById('saved-btn-new').addEventListener('click', () => doSelectNew('saved'));
    document.getElementById('saved-btn-none').addEventListener('click', () => doDeselectAll('saved'));

    // ── My Posts ──
    document.getElementById('btn-load-my').addEventListener('click', () => loadSimple('my', 'fetchMyPosts'));
    document.getElementById('btn-my-more').addEventListener('click', () => loadSimple('my', 'fetchMyPosts', true));
    document.getElementById('my-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('my') : doDeselectAll('my'));
    document.getElementById('my-btn-new').addEventListener('click', () => doSelectNew('my'));
    document.getElementById('my-btn-none').addEventListener('click', () => doDeselectAll('my'));

    // ── Following accounts ──
    document.getElementById('btn-load-following').addEventListener('click', () => loadFollowing());
    document.getElementById('btn-acc-more').addEventListener('click', () => loadFollowing(true));
    document.getElementById('acc-chk-all').addEventListener('change', e => e.target.checked ? doAccSelectAll() : doAccDeselectAll());
    document.getElementById('acc-btn-none').addEventListener('click', doAccDeselectAll);
    document.getElementById('btn-load-follow-posts').addEventListener('click', loadFollowingPosts);

    // ── Following posts ──
    document.getElementById('fp-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('followingPosts') : doDeselectAll('followingPosts'));
    document.getElementById('fp-btn-new').addEventListener('click', () => doSelectNew('followingPosts'));
    document.getElementById('fp-btn-none').addEventListener('click', () => doDeselectAll('followingPosts'));

    // ── Export ──
    document.getElementById('btn-export-json').addEventListener('click', exportJSON);
    document.getElementById('btn-export-txt').addEventListener('click', exportTXT);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await loadStorage();
    bind();

    // Auto-connect if TikTok tab found
    const tab = await findTikTokTab();
    if (tab) {
        tiktokTabId = tab.id;
        // Ping first to check if content script is alive
        try {
            await sendToContent('ping');
            await connect();
        } catch (_) {
            setStatus('Open tiktok.com and make sure the page is loaded, then click Connect.', 'info');
        }
    } else {
        setStatus('Open https://www.tiktok.com in a tab, then click Connect.', 'info');
    }

    updateFooter();
});
