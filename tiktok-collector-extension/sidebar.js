'use strict';
// WordAI TikTok Collector — Sidebar script
// Runs inside sidebar.html (chrome-extension:// page embedded in TikTok via iframe)

// ─── State ────────────────────────────────────────────────────────────────────
let tiktokTabId = null;
let currentUser = null; // { uid, secUid, uniqueId, nickname }
let activeTab = 'likes';
let downloadedIds = new Set();

const S = {
    likes: { items: [], cursor: 0, hasMore: false, loading: false, selected: new Set() },
    saved: { items: [], cursor: 0, hasMore: false, loading: false, selected: new Set() },
    my: { items: [], cursor: 0, hasMore: false, loading: false, selected: new Set() },
    channel: { user: null, items: [], cursor: 0, hasMore: false, loading: false, selected: new Set() },
    following: {
        authors: [], maxCursor: 0, minCursor: 0, hasMore: false, loading: false,
        selectedAuthors: new Set(),
        posts: { items: [], loading: false, selected: new Set() },
    },
};

// ─── Storage ──────────────────────────────────────────────────────────────────
async function loadStorage() {
    const r = await chrome.storage.local.get(['downloadedIds']);
    downloadedIds = new Set(r.downloadedIds || []);
    await adminLoadStorage();
}

async function saveDownloaded() {
    await chrome.storage.local.set({ downloadedIds: [...downloadedIds] });
}

// ─── Chrome helpers ───────────────────────────────────────────────────────────
/** Get the TikTok tab — we are embedded inside it so active=current window */
async function findTikTokTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs.length ? tabs[0] : null;
}

function sendToContent(action, params = {}) {
    return new Promise((resolve, reject) => {
        if (!tiktokTabId) return reject(new Error('No TikTok tab found. Open tiktok.com first.'));
        chrome.tabs.sendMessage(tiktokTabId, { action, ...params }, (resp) => {
            if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
            if (!resp) return reject(new Error('No response from content script. Try refreshing the page.'));
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

function fmtDate(iso) { return iso ? iso.split('T')[0] : ''; }

function escHtml(s) {
    return String(s || '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
        : '<span class="post-type video">🎬</span>';

    const authorHtml = (tabKey === 'followingPosts' && item.author && item.author.username)
        ? `<span class="post-author">${escHtml(item.author.username)}</span>` : '';

    el.innerHTML = `
    <input type="checkbox" class="post-cb" ${checked ? 'checked' : ''}>
    <div class="post-body">
      <div class="post-meta">
        <span class="post-date">${fmtDate(item.created_date || item.created_at)}</span>
        ${typeLabel}${authorHtml}
        ${isDone ? '<span class="post-done">✓</span>' : ''}
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
      ${author.avatar ? `<img src="${escHtml(author.avatar)}" alt="" loading="lazy">` : ''}
    </div>
    <div class="account-details">
      <div class="account-nick">${escHtml(author.nickname || author.username)}</div>
      <div class="account-user">@${escHtml(author.username)}</div>
    </div>
    <div class="account-info">
      <div>${fmt(author.videoCount)} vids</div>
      <div>${fmt(author.followerCount)} flw</div>
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

// ─── Selection bar updaters ───────────────────────────────────────────────────
function updateSelBar(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    const items = isFP ? S.following.posts.items : S[tabKey].items;

    if (isFP) {
        const cnt = document.getElementById('fp-sel-count');
        const chk = document.getElementById('fp-chk-all');
        if (cnt) cnt.textContent = sel.size ? `${sel.size} selected` : '';
        if (chk) chk.checked = sel.size === items.length && items.length > 0;
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
    const isFP = activeTab === 'following';
    const sel = isFP ? S.following.posts.selected : (S[activeTab] ? S[activeTab].selected : new Set());
    const items = isFP ? S.following.posts.items : (S[activeTab] ? S[activeTab].items : []);

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

    // MP4 button: only enable if any selected video has a videoUrl
    const hasVideos = [...sel].some(id => {
        const item = items.find(i => i.id === id);
        return item && item.media_type === 'video';
    });
    document.getElementById('btn-export-mp4').disabled = !hasVideos;
}

function updatePaneStats(tabKey) {
    const items = tabKey === 'followingPosts'
        ? S.following.posts.items
        : (S[tabKey] ? S[tabKey].items : []);
    const el = document.getElementById(tabKey === 'followingPosts' ? 'fp-sel-count' : tabKey + '-stats');
    if (!el || !items.length) {
        if (el) el.textContent = '';
        return;
    }
    const coll = items.filter(i => downloadedIds.has(i.id)).length;
    const newN = items.length - coll;
    el.textContent = `${items.length} · ${coll} saved · ${newN} new`;
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
            uniqueId: currentUser.uniqueId || '',
            cursor,
            autoNavigate: true,
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
        resp.authors.forEach(a => { fs.authors.push(a); list.appendChild(makeAccountEl(a)); });

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
    const batch = selected.slice(0, 20);
    setStatus('Fetching posts… 0/' + batch.length + ' accounts');

    for (const authorId of batch) {
        const author = S.following.authors.find(a => a.id === authorId);
        if (!author || !author.secUid) continue;

        try {
            // Paginate through ALL pages for this author
            let cursor = 0;
            let hasMore = true;
            let pageNum = 0;
            while (hasMore) {
                pageNum++;
                const resp = await sendToContent('fetchUserPosts', { secUid: author.secUid, uniqueId: author.username || '', cursor, autoNavigate: false });
                let items = resp.items;
                if (newOnly) items = items.filter(i => !downloadedIds.has(i.id));
                const list = document.getElementById('follow-posts-list');
                items.forEach(item => { fp.items.push(item); list.appendChild(makePostEl(item, 'followingPosts')); });
                cursor = resp.nextCursor;
                hasMore = resp.hasMore;
                // If newOnly and we hit already-downloaded items, stop early
                if (newOnly && items.length === 0 && resp.items.length > 0) hasMore = false;
                if (hasMore) await new Promise(r => setTimeout(r, 300));
            }
        } catch (_e) { /* skip failed accounts */ }

        done++;
        setStatus('Fetching posts… ' + done + '/' + batch.length + ' accounts (' + fp.items.length + ' posts so far)');
        await new Promise(r => setTimeout(r, 350));
    }

    fp.loading = false;
    updateSelBar('followingPosts');
    updateFooter();
    setStatus('Loaded ' + fp.items.length + ' posts from ' + done + ' accounts', 'ok');
    if (selected.length > 20) setStatus('Note: limited to first 20 accounts', 'info');
}

// ─── Channel loader ───────────────────────────────────────────────────────────
async function loadChannel(append = false) {
    const rawInput = document.getElementById('channel-url-input').value.trim();
    if (!rawInput) return setStatus('Enter a channel URL or @username', 'err');

    // Parse username from URL or @handle
    let username = rawInput;
    const m = rawInput.match(/tiktok\.com\/@([^/?#\s]+)/);
    if (m) username = m[1];
    username = username.replace(/^@/, '').trim();
    if (!username) return setStatus('Invalid channel URL', 'err');

    const cs = S.channel;
    if (cs.loading) return;

    if (!append) {
        // Resolve user first
        setStatus(`Looking up @${username}…`);
        try {
            const resp = await sendToContent('resolveUser', { username });
            cs.user = resp.user;
        } catch (e) {
            return setStatus(e.message, 'err');
        }

        // Show channel info card
        const info = document.getElementById('channel-info');
        const avatarEl = document.getElementById('channel-avatar');
        document.getElementById('channel-nickname').textContent = cs.user.nickname || cs.user.username;
        document.getElementById('channel-username').textContent = '@' + cs.user.username;
        document.getElementById('channel-stats-text').innerHTML =
            `${fmt(cs.user.videoCount)} videos<br>${fmt(cs.user.followerCount)} followers`;
        avatarEl.innerHTML = cs.user.avatar
            ? `<img src="${escHtml(cs.user.avatar)}" alt="" loading="lazy">` : '';
        info.classList.remove('hidden');

        cs.items = [];
        cs.cursor = 0;
        cs.selected.clear();
        document.getElementById('channel-list').innerHTML = '';
        document.getElementById('channel-sel-bar').classList.add('hidden');
    }

    if (!cs.user) return setStatus('Load a channel first', 'err');

    cs.loading = true;
    setStatus(`Loading videos from @${cs.user.username}…`);

    try {
        const resp = await sendToContent('fetchUserPosts', {
            secUid: cs.user.secUid,
            uniqueId: cs.user.username || '',
            cursor: append ? cs.cursor : 0,
            autoNavigate: true,
        });

        const list = document.getElementById('channel-list');
        resp.items.forEach(item => {
            cs.items.push(item);
            list.appendChild(makePostEl(item, 'channel'));
        });

        cs.cursor = resp.nextCursor;
        cs.hasMore = resp.hasMore;

        const moreBar = document.getElementById('channel-more-bar');
        if (cs.hasMore) moreBar.classList.remove('hidden');
        else moreBar.classList.add('hidden');

        document.getElementById('channel-sel-bar').classList.remove('hidden');
        updatePaneStats('channel');
        updateSelBar('channel');
        updateFooter();
        setStatus(`Loaded ${cs.items.length} posts from @${cs.user.username}${cs.hasMore ? ' · more available' : ''}`, 'ok');
    } catch (e) {
        setStatus(e.message, 'err');
    } finally {
        cs.loading = false;
    }
}

// ─── Selection helpers ────────────────────────────────────────────────────────
function doSelectAll(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    const items = isFP ? S.following.posts.items : S[tabKey].items;
    items.forEach(i => sel.add(i.id));
    const listId = isFP ? 'follow-posts-list' : tabKey + '-list';
    document.getElementById(listId).querySelectorAll('.post-cb').forEach(cb => { cb.checked = true; });
    updateSelBar(tabKey === 'followingPosts' ? 'followingPosts' : tabKey);
    updateFooter();
}

function doDeselectAll(tabKey) {
    const isFP = tabKey === 'followingPosts';
    const sel = isFP ? S.following.posts.selected : S[tabKey].selected;
    sel.clear();
    const listId = isFP ? 'follow-posts-list' : tabKey + '-list';
    document.getElementById(listId).querySelectorAll('.post-cb').forEach(cb => { cb.checked = false; });
    updateSelBar(tabKey === 'followingPosts' ? 'followingPosts' : tabKey);
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
    updateSelBar(tabKey === 'followingPosts' ? 'followingPosts' : tabKey);
    updateFooter();
}

function doAccSelectAll() {
    S.following.authors.forEach(a => S.following.selectedAuthors.add(a.id));
    document.getElementById('account-list').querySelectorAll('.acc-cb').forEach(cb => { cb.checked = true; });
    updateAccountSelBar();
}

function doAccDeselectAll() {
    S.following.selectedAuthors.clear();
    document.getElementById('account-list').querySelectorAll('.acc-cb').forEach(cb => { cb.checked = false; });
    updateAccountSelBar();
}

// ─── Export helpers ───────────────────────────────────────────────────────────
function getSelectedItems() {
    if (activeTab === 'following') {
        const sel = S.following.posts.selected;
        return S.following.posts.items.filter(i => sel.has(i.id));
    }
    if (!S[activeTab]) return [];
    return S[activeTab].items.filter(i => S[activeTab].selected.has(i.id));
}

function buildExportData(selectedItems) {
    const source = activeTab === 'following' ? 'following' : activeTab;
    const dates = selectedItems.map(i => i.created_date).filter(Boolean).sort();
    const videos = selectedItems.filter(i => i.media_type === 'video').length;
    const images = selectedItems.filter(i => i.media_type === 'image').length;
    const channelUser = activeTab === 'channel' ? S.channel.user : null;

    return {
        version: '2.0',
        exporter: 'WordAI TikTok Collector v2.0',
        exported_at: new Date().toISOString(),
        source,
        profile: currentUser ? {
            username: currentUser.uniqueId,
            nickname: currentUser.nickname,
            uid: currentUser.uid,
        } : null,
        channel: channelUser ? {
            username: channelUser.username,
            nickname: channelUser.nickname,
            followerCount: channelUser.followerCount,
            videoCount: channelUser.videoCount,
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
            videoUrl: item.videoUrl || '',
            source: item.source,
        })),
    };
}

function exportJSON() {
    const items = getSelectedItems();
    if (!items.length) return;
    const data = buildExportData(items);
    const sourceTag = activeTab === 'channel' && S.channel.user
        ? S.channel.user.username : activeTab;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `tiktok_${sourceTag}_${dateSuffix()}.json`);
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
    if (data.channel) lines.push(`Channel: @${data.channel.username} (${data.channel.nickname})`);
    lines.push(`Exported: ${new Date(data.exported_at).toLocaleString()}`);
    lines.push(`Total: ${data.summary.total} (${data.summary.videos} videos, ${data.summary.images} images)`);
    if (data.summary.date_range)
        lines.push(`Date range: ${data.summary.date_range.earliest} → ${data.summary.date_range.latest}`);
    lines.push('');

    data.posts.forEach(post => {
        lines.push('---');
        lines.push(`DATE: ${post.created_date}  TYPE: ${post.media_type.toUpperCase()}  ❤️ ${fmt(post.stats.likes)}  ▶️ ${fmt(post.stats.plays)}  💬 ${fmt(post.stats.comments)}`);
        if (post.author && post.author.username) lines.push(`AUTHOR: @${post.author.username} (${post.author.nickname})`);
        lines.push(`DESC: ${post.desc || '(No caption)'}`);
        lines.push(`URL: ${post.url}`);
        if (post.videoUrl) lines.push(`VIDEO_URL: ${post.videoUrl}`);
        lines.push('');
    });

    const sourceTag = activeTab === 'channel' && S.channel.user
        ? S.channel.user.username : activeTab;
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, `tiktok_${sourceTag}_${dateSuffix()}.txt`);
    markDownloaded(items);
}

// ─── Per-channel download manifest ───────────────────────────────────────────
async function loadChannelManifest(channelTag) {
    const r = await chrome.storage.local.get(['dlManifest_' + channelTag]);
    return r['dlManifest_' + channelTag] || {};
}

async function saveChannelManifest(channelTag, manifest) {
    await chrome.storage.local.set({ ['dlManifest_' + channelTag]: manifest });
}

async function writeManifestFile(channelTag, manifest) {
    const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    try {
        await chrome.downloads.download({
            url,
            filename: 'TikTok/' + channelTag + '/wordai_manifest.json',
            conflictAction: 'overwrite',
        });
    } finally {
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
}

function base64ToBytes(base64) {
    const binaryStr = atob(base64);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i);
    return bytes;
}

async function exportMP4() {
    const items = getSelectedItems().filter(i => i.media_type === 'video');
    if (!items.length) return setStatus('No video posts selected.', 'err');

    const withUrl = items.filter(i => i.videoUrl);
    if (!withUrl.length)
        return setStatus('No download URLs found — reload the list first.', 'err');

    const noUrl = items.length - withUrl.length;
    if (noUrl > 0) setStatus(noUrl + ' video(s) have no URL and will be skipped.', 'info');

    const channelTag = (activeTab === 'channel' && S.channel.user)
        ? S.channel.user.username : activeTab;

    // Load existing manifest to skip already-downloaded videos
    const manifest = await loadChannelManifest(channelTag);
    const toDownload = withUrl.filter(i => !manifest[i.id]);

    if (!toDownload.length)
        return setStatus('All selected videos already downloaded for @' + channelTag + '.', 'ok');
    if (toDownload.length < withUrl.length)
        setStatus((withUrl.length - toDownload.length) + ' already downloaded — skipping.', 'info');

    const total = toDownload.length;
    let done = 0, failed = 0;

    for (const item of toDownload) {
        const videoFilename = 'TikTok/' + channelTag + '/videos/' + item.id + '.mp4';
        const coverFilename = 'TikTok/' + channelTag + '/covers/' + item.id + '.jpg';
        setStatus('[' + (done + failed + 1) + '/' + total + '] Fetching ' + item.id + '…');

        try {
            // ── Video ──
            const { base64 } = await sendToContent('fetchVideoBytes', { videoUrl: item.videoUrl });
            const vUrl = URL.createObjectURL(new Blob([base64ToBytes(base64)], { type: 'video/mp4' }));
            await chrome.downloads.download({ url: vUrl, filename: videoFilename, conflictAction: 'uniquify' });
            setTimeout(() => URL.revokeObjectURL(vUrl), 10000);

            // ── Cover image (best-effort) ──
            let coverSaved = false;
            if (item.coverUrl) {
                try {
                    const { base64: cb } = await sendToContent('fetchVideoBytes', { videoUrl: item.coverUrl });
                    const cUrl = URL.createObjectURL(new Blob([base64ToBytes(cb)], { type: 'image/jpeg' }));
                    await chrome.downloads.download({ url: cUrl, filename: coverFilename, conflictAction: 'uniquify' });
                    setTimeout(() => URL.revokeObjectURL(cUrl), 10000);
                    coverSaved = true;
                } catch (_) { /* cover is optional */ }
            }

            // ── Record in manifest ──
            manifest[item.id] = {
                video: videoFilename,
                cover: coverSaved ? coverFilename : null,
                desc: item.desc,
                url: item.url,
                downloaded_at: new Date().toISOString(),
            };
            downloadedIds.add(item.id);
            await saveDownloaded();

            done++;
            setStatus('[' + done + '/' + total + '] ✓ ' + item.id, 'ok');
        } catch (e) {
            failed++;
            console.warn('[WordAI] Download failed', item.id, e.message);
            setStatus('✗ ' + item.id.slice(-6) + ' — ' + e.message, 'err');
        }

        if (done + failed < total) await new Promise(r => setTimeout(r, 800));
    }

    // Persist manifest to storage + write JSON file into the channel folder
    await saveChannelManifest(channelTag, manifest);
    await writeManifestFile(channelTag, manifest);

    if (failed)
        setStatus('Done: ' + done + ' downloaded, ' + failed + ' failed → Downloads/TikTok/' + channelTag, done ? 'ok' : 'err');
    else
        setStatus('✓ ' + done + ' video' + (done !== 1 ? 's' : '') + ' → Downloads/TikTok/' + channelTag, 'ok');

    markDownloaded(toDownload.slice(0, done));
}
function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
}

async function markDownloaded(items) {
    items.forEach(i => downloadedIds.add(i.id));
    await saveDownloaded();

    const isFP = activeTab === 'following';
    const listId = isFP ? 'follow-posts-list' : activeTab + '-list';
    document.getElementById(listId).querySelectorAll('.post-item').forEach(el => {
        if (downloadedIds.has(el.dataset.id)) {
            el.classList.add('downloaded');
            if (!el.querySelector('.post-done')) {
                const meta = el.querySelector('.post-meta');
                if (meta) meta.insertAdjacentHTML('beforeend', '<span class="post-done">✓</span>');
            }
        }
    });
    updatePaneStats(isFP ? 'followingPosts' : activeTab);
}

function dateSuffix() { return new Date().toISOString().split('T')[0]; }

// ─── Connect ──────────────────────────────────────────────────────────────────
async function connect() {
    setStatus('Connecting to TikTok…');
    const tab = await findTikTokTab();
    if (!tab) {
        setStatus('Could not find TikTok tab. Open tiktok.com first.', 'err');
        return;
    }
    tiktokTabId = tab.id;

    try {
        const resp = await sendToContent('getContext');
        currentUser = resp.user;
        document.getElementById('user-name').textContent = `@${currentUser.uniqueId}`;
        document.getElementById('btn-connect').textContent = '✓';
        document.getElementById('btn-connect').disabled = true;
        setStatus(`Connected as @${currentUser.uniqueId}`, 'ok');
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
    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Connect
    document.getElementById('btn-connect').addEventListener('click', connect);

    // Likes
    document.getElementById('btn-load-likes').addEventListener('click', () => loadSimple('likes', 'fetchLikes'));
    document.getElementById('btn-likes-more').addEventListener('click', () => loadSimple('likes', 'fetchLikes', true));
    document.getElementById('likes-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('likes') : doDeselectAll('likes'));
    document.getElementById('likes-btn-new').addEventListener('click', () => doSelectNew('likes'));
    document.getElementById('likes-btn-none').addEventListener('click', () => doDeselectAll('likes'));

    // Saved
    document.getElementById('btn-load-saved').addEventListener('click', () => loadSimple('saved', 'fetchSaved'));
    document.getElementById('btn-saved-more').addEventListener('click', () => loadSimple('saved', 'fetchSaved', true));
    document.getElementById('saved-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('saved') : doDeselectAll('saved'));
    document.getElementById('saved-btn-new').addEventListener('click', () => doSelectNew('saved'));
    document.getElementById('saved-btn-none').addEventListener('click', () => doDeselectAll('saved'));

    // My Posts
    document.getElementById('btn-load-my').addEventListener('click', () => loadSimple('my', 'fetchMyPosts'));
    document.getElementById('btn-my-more').addEventListener('click', () => loadSimple('my', 'fetchMyPosts', true));
    document.getElementById('my-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('my') : doDeselectAll('my'));
    document.getElementById('my-btn-new').addEventListener('click', () => doSelectNew('my'));
    document.getElementById('my-btn-none').addEventListener('click', () => doDeselectAll('my'));

    // Following accounts
    document.getElementById('btn-load-following').addEventListener('click', () => loadFollowing());
    document.getElementById('btn-acc-more').addEventListener('click', () => loadFollowing(true));
    document.getElementById('acc-chk-all').addEventListener('change', e => e.target.checked ? doAccSelectAll() : doAccDeselectAll());
    document.getElementById('acc-btn-none').addEventListener('click', doAccDeselectAll);
    document.getElementById('btn-load-follow-posts').addEventListener('click', loadFollowingPosts);

    // Following posts
    document.getElementById('fp-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('followingPosts') : doDeselectAll('followingPosts'));
    document.getElementById('fp-btn-new').addEventListener('click', () => doSelectNew('followingPosts'));
    document.getElementById('fp-btn-none').addEventListener('click', () => doDeselectAll('followingPosts'));

    // Channel
    document.getElementById('btn-load-channel').addEventListener('click', () => loadChannel());
    document.getElementById('btn-channel-more').addEventListener('click', () => loadChannel(true));
    document.getElementById('channel-url-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') loadChannel();
    });
    document.getElementById('channel-chk-all').addEventListener('change', e => e.target.checked ? doSelectAll('channel') : doDeselectAll('channel'));
    document.getElementById('channel-btn-new').addEventListener('click', () => doSelectNew('channel'));
    document.getElementById('channel-btn-none').addEventListener('click', () => doDeselectAll('channel'));

    // Export
    document.getElementById('btn-export-json').addEventListener('click', exportJSON);
    document.getElementById('btn-export-txt').addEventListener('click', exportTXT);
    document.getElementById('btn-export-mp4').addEventListener('click', exportMP4);

    // Infinite scroll — auto-load more when reaching bottom of each post list
    bindInfiniteScroll('likes-list', () => S.likes.hasMore && !S.likes.loading, () => loadSimple('likes', 'fetchLikes', true));
    bindInfiniteScroll('saved-list', () => S.saved.hasMore && !S.saved.loading, () => loadSimple('saved', 'fetchSaved', true));
    bindInfiniteScroll('my-list', () => S.my.hasMore && !S.my.loading, () => loadSimple('my', 'fetchMyPosts', true));
    bindInfiniteScroll('channel-list', () => S.channel.hasMore && !S.channel.loading, () => loadChannel(true));
    bindInfiniteScroll('account-list', () => S.following.hasMore && !S.following.loading, () => loadFollowing(true));

    bindAdmin();
}

function bindInfiniteScroll(listId, canLoad, doLoad) {
    const el = document.getElementById(listId);
    if (!el) return;
    el.addEventListener('scroll', () => {
        if (!canLoad()) return;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
            doLoad();
        }
    });
}

// ─── DB1 API ──────────────────────────────────────────────────────────────────
const DB1_URL = 'https://db-wordai-community.hoangnguyen358888.workers.dev';
const ADMIN_UID = '17BeaeikPBQYk8OWeDUkqm0Ov8e2';
const HOT_VIDEOS_HANDLE = '@hot.videos';

let db1Secret = null;

async function db1Query(sql, params = []) {
    const r = await fetch(DB1_URL + '/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + db1Secret },
        body: JSON.stringify({ query: sql, params }),
    });
    if (!r.ok) throw new Error('DB1 query error: ' + r.status);
    return r.json();
}

async function db1Insert(table, data) {
    const r = await fetch(DB1_URL + '/rest/' + table, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + db1Secret },
        body: JSON.stringify(data),
    });
    if (!r.ok) throw new Error('DB1 insert ' + table + ' error: ' + r.status + ' — ' + await r.text());
}

// ─── Admin State ──────────────────────────────────────────────────────────────
const Admin = {
    channels: [],
    syncTimes: {},
    channelLinks: {},   // channelId → saved TikTok URL string
    running: false,
};

async function adminLoadStorage() {
    const r = await chrome.storage.local.get(['db1Secret', 'db1SyncTimes', 'adminChannelLinks']);
    db1Secret = r.db1Secret || null;
    Admin.syncTimes = r.db1SyncTimes || {};
    Admin.channelLinks = r.adminChannelLinks || {};
    const keyStatus = document.getElementById('admin-key-status');
    if (keyStatus) keyStatus.textContent = db1Secret ? '✓ Key saved' : 'No key set';
}

async function adminSaveChannelLink(channelId, url) {
    Admin.channelLinks[channelId] = url;
    await chrome.storage.local.set({ adminChannelLinks: Admin.channelLinks });
}

async function adminSaveSecret(secret) {
    db1Secret = secret;
    await chrome.storage.local.set({ db1Secret: secret });
    const keyStatus = document.getElementById('admin-key-status');
    if (keyStatus) keyStatus.textContent = '✓ Key saved';
}

// ─── Admin: Load channels from DB1 ───────────────────────────────────────────
async function adminLoadChannels() {
    if (!db1Secret) return setStatus('Set DB1 API key first', 'err');
    const loadBtn = document.getElementById('btn-admin-load-channels');
    if (loadBtn) loadBtn.disabled = true;
    setStatus('Loading channels from DB1…');
    try {
        const result = await db1Query('SELECT * FROM channels ORDER BY name ASC');
        Admin.channels = result.results || [];
        renderAdminChannels();
        const syncAllBtn = document.getElementById('btn-admin-sync-all');
        if (syncAllBtn) syncAllBtn.disabled = false;
        setStatus('Loaded ' + Admin.channels.length + ' channels from DB1', 'ok');
    } catch (e) {
        setStatus(e.message, 'err');
    } finally {
        if (loadBtn) loadBtn.disabled = false;
    }
}

// ─── Admin: Render channel list ───────────────────────────────────────────────
function renderAdminChannels() {
    const list = document.getElementById('admin-channels-list');
    if (!list) return;
    list.innerHTML = '';
    if (!Admin.channels.length) {
        list.innerHTML = '<div class="empty-msg">No channels found</div>';
        return;
    }
    Admin.channels.forEach(ch => {
        const isHot = ch.handle === HOT_VIDEOS_HANDLE;
        const lastSync = Admin.syncTimes[ch.id];
        const savedLink = Admin.channelLinks[ch.id] || '';
        const el = document.createElement('div');
        el.className = 'admin-channel-item';
        el.dataset.channelId = ch.id;
        el.innerHTML = `
          <div class="admin-channel-info">
            <div class="admin-channel-name">
              ${escHtml(ch.name)}
              <button class="admin-ch-link-btn${savedLink ? ' has-link' : ''}" id="admin-ch-link-${ch.id}" title="${savedLink ? 'TikTok: ' + savedLink : 'Set TikTok link'}">🔗</button>
            </div>
            <div class="admin-ch-link-row hidden" id="admin-ch-link-row-${ch.id}">
              <input type="text" id="admin-ch-link-input-${ch.id}" class="admin-ch-link-input"
                placeholder="https://www.tiktok.com/@username" value="${escHtml(savedLink)}">
              <button class="btn btn-sm btn-primary admin-ch-link-save" id="admin-ch-link-save-${ch.id}">Save</button>
            </div>
            <div class="admin-channel-meta">
              <span>${escHtml(ch.handle)}</span>
              <span class="posts-count" id="admin-ch-count-${ch.id}">loading…</span>
              ${isHot ? '<span class="special-tag">🔖 Saved source</span>' : ''}
              <span class="${lastSync ? 'sync-badge' : 'sync-pending'}" id="admin-ch-sync-${ch.id}">
                ${lastSync ? '✓ ' + lastSync.split('T')[0] : 'never synced'}
              </span>
            </div>
          </div>
          <button class="admin-channel-sync-btn" id="admin-ch-btn-${ch.id}" data-channel-id="${ch.id}">▶ Sync</button>
        `;
        list.appendChild(el);

        // Toggle link-edit row
        el.querySelector('#admin-ch-link-' + ch.id).addEventListener('click', () => {
            const row = document.getElementById('admin-ch-link-row-' + ch.id);
            row.classList.toggle('hidden');
            if (!row.classList.contains('hidden')) {
                document.getElementById('admin-ch-link-input-' + ch.id).focus();
            }
        });

        // Save link on button click or Enter
        const doSaveLink = async () => {
            const url = document.getElementById('admin-ch-link-input-' + ch.id).value.trim();
            await adminSaveChannelLink(ch.id, url);
            const linkBtn = document.getElementById('admin-ch-link-' + ch.id);
            linkBtn.title = url ? 'TikTok: ' + url : 'Set TikTok link';
            linkBtn.classList.toggle('has-link', !!url);
            document.getElementById('admin-ch-link-row-' + ch.id).classList.add('hidden');
            setStatus('Link saved for ' + ch.name, 'ok');
        };
        el.querySelector('#admin-ch-link-save-' + ch.id).addEventListener('click', doSaveLink);
        el.querySelector('#admin-ch-link-input-' + ch.id).addEventListener('keydown', e => { if (e.key === 'Enter') doSaveLink(); });

        // Async: load post count
        db1Query("SELECT COUNT(*) as c FROM posts WHERE channel_id = ? AND status = 'published'", [ch.id])
            .then(r => {
                const countEl = document.getElementById('admin-ch-count-' + ch.id);
                if (countEl) countEl.textContent = (r.results?.[0]?.c ?? 0) + ' posts';
            }).catch(() => { });
        el.querySelector('.admin-channel-sync-btn').addEventListener('click', () => syncChannel(ch));
    });
}

// ─── Admin: Sync one channel ──────────────────────────────────────────────────
async function syncChannel(channel) {
    if (!db1Secret) return setStatus('Set DB1 API key first', 'err');
    if (!currentUser) return setStatus('Connect to TikTok first', 'err');

    const btn = document.getElementById('admin-ch-btn-' + channel.id);
    if (btn) { btn.disabled = true; btn.textContent = '⟳'; btn.className = 'admin-channel-sync-btn syncing'; }

    const isHot = channel.handle === HOT_VIDEOS_HANDLE;
    const savedLink = Admin.channelLinks[channel.id] || '';
    // Extract username from saved link, e.g. https://www.tiktok.com/@1987vibesvn → 1987vibesvn
    const linkUsername = savedLink ? (savedLink.match(/@([^/?#]+)/) || [])[1] || '' : '';

    adminLog('[' + channel.name + '] Starting sync (' + (isHot ? 'saved-source' : channel.handle) + (linkUsername ? ', link: @' + linkUsername : '') + ')…', 'info');

    try {
        // 1. Get existing TikTok IDs from DB1
        const result = await db1Query(
            "SELECT video_url FROM posts WHERE channel_id = ? AND type='video_link' AND status='published'",
            [channel.id]
        );
        const existingIds = new Set();
        (result.results || []).forEach(row => {
            const m = (row.video_url || '').match(/\/video\/(\d+)/);
            if (m) existingIds.add(m[1]);
        });
        adminLog('[' + channel.name + '] ' + existingIds.size + ' existing videos in DB1 — will stop when hitting known IDs', 'info');

        // 2. Resolve TikTok secUid
        let secUid, resolvedUsername;
        if (isHot) {
            secUid = currentUser.secUid;
            resolvedUsername = currentUser.uniqueId || '';
            adminLog('[' + channel.name + '] Using current TikTok user (saved source)', 'info');
        } else {
            resolvedUsername = linkUsername || channel.handle.replace(/^@/, '');
            const resp = await sendToContent('resolveUser', { username: resolvedUsername });
            secUid = resp.user.secUid;
        }

        // 3. Fetch posts — use scroll+autoNavigate if we have a saved link username
        const newItems = [];
        let cursor = 0;
        let hasMore = true;
        let pageNum = 0;

        while (hasMore) {
            pageNum++;
            const action = isHot ? 'fetchSaved' : 'fetchUserPosts';
            const fetchParams = isHot
                ? { secUid, cursor }
                : { secUid, uniqueId: resolvedUsername, cursor, autoNavigate: linkUsername ? true : false };
            const resp = await sendToContent(action, fetchParams);
            let hitExisting = false;

            for (const item of resp.items) {
                if (existingIds.has(item.id)) { hitExisting = true; break; }
                if (item.media_type === 'video') newItems.push(item);
            }

            cursor = resp.nextCursor;
            hasMore = resp.hasMore && !hitExisting;
            adminLog('[' + channel.name + '] Page ' + pageNum + ': ' + resp.items.length + ' fetched, ' + newItems.length + ' new, ' + (hitExisting ? '⛔ hit known ID — stopping' : (hasMore ? 'more…' : 'end of feed')), 'info');
            await new Promise(r => setTimeout(r, 400));
        }

        adminLog('[' + channel.name + '] ' + newItems.length + ' new videos to push', newItems.length ? 'warn' : 'ok');

        // 4. Insert new posts into DB1 (reverse order: oldest first)
        let inserted = 0;
        for (const item of [...newItems].reverse()) {
            const postId = crypto.randomUUID();
            await db1Insert('posts', {
                id: postId,
                channel_id: channel.id,
                owner_id: ADMIN_UID,
                type: 'video_link',
                content: item.desc || '',
                video_url: item.url,
                video_source: 'tiktok',
                category: channel.category || null,
                country: 'vn',
                status: 'published',
                created_at: item.created_at || new Date().toISOString(),
            });
            await db1Insert('post_stats', {
                post_id: postId,
                total_likes: item.stats?.likes || 0,
                total_saved: 0,
                total_comments: item.stats?.comments || 0,
                total_views: item.stats?.plays || 0,
            });
            inserted++;
            await new Promise(r => setTimeout(r, 120));
        }

        // 5. Update sync time
        const now = new Date();
        Admin.syncTimes[channel.id] = now.toISOString();
        await chrome.storage.local.set({ db1SyncTimes: Admin.syncTimes });

        const syncEl = document.getElementById('admin-ch-sync-' + channel.id);
        if (syncEl) { syncEl.className = 'sync-badge'; syncEl.textContent = '✓ ' + now.toISOString().split('T')[0]; }

        const countEl = document.getElementById('admin-ch-count-' + channel.id);
        if (countEl) {
            db1Query("SELECT COUNT(*) as c FROM posts WHERE channel_id = ? AND status='published'", [channel.id])
                .then(r => { if (countEl) countEl.textContent = (r.results?.[0]?.c ?? 0) + ' posts'; }).catch(() => { });
        }

        // 6. Write JSON update file to Downloads/TikTok/Update[channel_name]/
        const safeChannelName = (channel.name || channel.handle).replace(/[^a-zA-Z0-9_\-\u00C0-\u024F]/g, '_');
        const dateStr = now.toISOString().split('T')[0];
        const updateRecord = {
            channel_id: channel.id,
            channel_name: channel.name,
            channel_handle: channel.handle,
            tiktok_link: savedLink || ('https://www.tiktok.com/' + channel.handle),
            sync_date: now.toISOString(),
            existing_in_db1: existingIds.size,
            new_videos_inserted: inserted,
            new_videos: newItems.map(v => ({
                id: v.id,
                url: v.url,
                desc: v.desc,
                created_at: v.created_at,
                stats: v.stats,
            })),
        };
        const jsonBlob = new Blob([JSON.stringify(updateRecord, null, 2)], { type: 'application/json' });
        const jsonUrl = URL.createObjectURL(jsonBlob);
        try {
            await chrome.downloads.download({
                url: jsonUrl,
                filename: 'TikTok/Update' + safeChannelName + '/sync_' + dateStr + '_' + now.getTime() + '.json',
                saveAs: false,
                conflictAction: 'uniquify',
            });
        } catch (_) { /* downloads may not be available, non-fatal */ }
        URL.revokeObjectURL(jsonUrl);

        adminLog('[' + channel.name + '] ✅ Inserted ' + inserted + ' new videos → Downloads/TikTok/Update' + safeChannelName + '/', 'ok');
        if (btn) { btn.textContent = '✓ Done'; btn.className = 'admin-channel-sync-btn done'; }
    } catch (e) {
        adminLog('[' + channel.name + '] ❌ Error: ' + e.message, 'err');
        if (btn) { btn.textContent = '▶ Retry'; btn.className = 'admin-channel-sync-btn'; }
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ─── Admin: Sync All ──────────────────────────────────────────────────────────
async function syncAllChannels() {
    if (Admin.running) return;
    if (!Admin.channels.length) return setStatus('Load channels first', 'err');
    Admin.running = true;
    const btn = document.getElementById('btn-admin-sync-all');
    if (btn) { btn.disabled = true; btn.textContent = '⟳ Syncing…'; }
    setStatus('Syncing ' + Admin.channels.length + ' channels…');
    for (const ch of Admin.channels) {
        await syncChannel(ch);
        await new Promise(r => setTimeout(r, 600));
    }
    Admin.running = false;
    if (btn) { btn.disabled = false; btn.textContent = '▶ Sync All'; }
    setStatus('All channels synced!', 'ok');
}

// ─── Admin: Log ───────────────────────────────────────────────────────────────
function adminLog(msg, type = 'info') {
    const log = document.getElementById('admin-log');
    if (!log) return;
    const section = document.getElementById('admin-log-section');
    if (section) section.classList.remove('hidden');
    const line = document.createElement('div');
    line.className = 'log-line ' + type;
    line.textContent = new Date().toTimeString().slice(0, 8) + ' ' + msg;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
}

// ─── Admin event bindings ─────────────────────────────────────────────────────
function bindAdmin() {
    const keyToggleBtn = document.getElementById('btn-admin-key-toggle');
    if (!keyToggleBtn) return; // admin pane not present

    keyToggleBtn.addEventListener('click', () => {
        const row = document.getElementById('admin-key-row');
        const isHidden = row.classList.contains('hidden');
        row.classList.toggle('hidden', !isHidden);
        keyToggleBtn.textContent = isHidden ? 'hide' : 'show';
        if (isHidden && db1Secret) {
            document.getElementById('admin-api-key-input').value = db1Secret;
        }
    });

    document.getElementById('btn-admin-key-save').addEventListener('click', async () => {
        const val = document.getElementById('admin-api-key-input').value.trim();
        if (!val) return;
        await adminSaveSecret(val);
        document.getElementById('admin-key-row').classList.add('hidden');
        keyToggleBtn.textContent = 'show';
        setStatus('DB1 API key saved', 'ok');
    });

    document.getElementById('btn-admin-load-channels').addEventListener('click', adminLoadChannels);
    document.getElementById('btn-admin-sync-all').addEventListener('click', syncAllChannels);
    document.getElementById('btn-admin-log-clear').addEventListener('click', () => {
        const log = document.getElementById('admin-log');
        if (log) log.innerHTML = '';
    });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await loadStorage();
    bind();

    // Auto-connect to the current TikTok tab
    const tab = await findTikTokTab();
    if (tab) {
        tiktokTabId = tab.id;
        try {
            await sendToContent('ping');
            await connect();
        } catch (_) {
            setStatus('Click Connect to start.', 'info');
        }
    } else {
        setStatus('Open https://www.tiktok.com, then click Connect.', 'info');
    }

    updateFooter();
});
