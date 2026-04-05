'use strict';
// WordAI TikTok Collector — Content Script (isolated world)
// Injected on tiktok.com. Handles all TikTok API calls.

let _appContext = null; // Cached once from SIGI_STATE

// ─── Page State Reader ────────────────────────────────────────────────────────
const LOG = (...a) => console.log('[WordAI]', ...a);

function readScriptTag(id) {
    try {
        const el = document.getElementById(id);
        if (!el) return null;
        const text = el.textContent;
        return text ? JSON.parse(text) : null;
    } catch (e) {
        LOG('readScriptTag error', id, e.message);
        return null;
    }
}

// Scan all inline <script> tags for a JSON blob containing known TikTok keys
function scanAllScriptTags() {
    const scripts = document.querySelectorAll('script:not([src])');
    LOG('Scanning', scripts.length, 'inline script tags...');
    for (const el of scripts) {
        const t = el.textContent.trim();
        if (!t.startsWith('{') && !t.startsWith('window.')) continue;
        // Try JSON-in-script: window.__VARNAME__ = {...}
        const m = t.match(/^window\.(\w+)\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
        if (m) LOG('  Found window var script:', m[1], '— len:', m[2].length);
        // Try bare JSON
        if (t.startsWith('{')) {
            try {
                const data = JSON.parse(t);
                if (data && (data['webapp.app-context'] || data.AppContext || data.appContext)) {
                    LOG('  Found bare JSON blob with TikTok keys, id=', el.id);
                    return data;
                }
            } catch (e) { }
        }
    }
    return null;
}

function readPageState() {
    return new Promise((resolve) => {
        function attempt(tryNum) {
            LOG(`attempt #${tryNum} — readingDOM script tags`);

            // Method 1: __UNIVERSAL_DATA_FOR_REHYDRATION__ (TikTok 2025+)
            // Structure: { "__DEFAULT_SCOPE__": { "webapp.app-context": { appContext: {...} } } }
            const universal = readScriptTag('__UNIVERSAL_DATA_FOR_REHYDRATION__');
            LOG('  UNIVERSAL tag:', universal ? 'FOUND, keys=' + Object.keys(universal).join(',') : 'null');
            if (universal) {
                const scope = universal['__DEFAULT_SCOPE__'] || universal;
                const ac = scope['webapp.app-context'];
                LOG('  webapp.app-context:', ac ? Object.keys(ac).join(',') : 'null');
                if (ac) {
                    const ctx = ac.appContext || ac;
                    LOG('  ctx keys:', Object.keys(ctx).join(','));
                    if (ctx.wid || ctx.$wid || ctx.region) {
                        LOG('  ✅ Got ctx from UNIVERSAL');
                        return ctx;
                    }
                }
            }

            // Method 2: SIGI_STATE (legacy)
            const sigi = readScriptTag('SIGI_STATE');
            LOG('  SIGI_STATE tag:', sigi ? 'FOUND, keys=' + Object.keys(sigi).join(',') : 'null');
            if (sigi && sigi.AppContext && sigi.AppContext.appContext) {
                LOG('  ✅ Got ctx from SIGI_STATE');
                return sigi.AppContext.appContext;
            }

            // Method 3: scan all script tags for embedded JSON
            const scanned = scanAllScriptTags();
            if (scanned) {
                const ctx = scanned['webapp.app-context']?.appContext
                    || scanned['webapp.app-context']
                    || scanned.AppContext?.appContext
                    || scanned.appContext;
                if (ctx && (ctx.wid || ctx.$wid || ctx.region)) {
                    LOG('  ✅ Got ctx from script tag scan');
                    return ctx;
                }
            }

            return null;
        }

        let tries = 0;
        function tryNow() {
            const result = attempt(tries + 1);
            if (result) return resolve(result);
            if (++tries >= 8) {
                // Last resort: read window.* directly — content scripts share the same window
                // properties with the page, so no injection needed.
                LOG('All DOM attempts failed — trying direct window.* read');
                let ctx = null;
                try {
                    const s = window.SIGI_STATE;
                    if (s && s.AppContext && s.AppContext.appContext) ctx = s.AppContext.appContext;
                } catch (_) { }
                try {
                    if (!ctx) {
                        const u = window.__$UNIVERSAL_DATA$__;
                        if (u && u.__DEFAULT_SCOPE__) {
                            const ac = u.__DEFAULT_SCOPE__['webapp.app-context'];
                            if (ac) ctx = ac.appContext || ac;
                        }
                    }
                } catch (_) { }
                try {
                    if (!ctx) {
                        const u2 = window.__UNIVERSAL_DATA_FOR_REHYDRATION__;
                        if (u2) {
                            const scope = u2['__DEFAULT_SCOPE__'] || {};
                            const ac = scope['webapp.app-context'];
                            if (ac) ctx = ac.appContext || ac;
                        }
                    }
                } catch (_) { }
                LOG('Direct window read:', ctx ? 'GOT ctx, keys=' + Object.keys(ctx).join(',') : 'null');
                resolve(ctx);
                return;
            }
            setTimeout(tryNow, 500);
        }
        tryNow();
    });
}

// ─── TikTok API Parameter Builder ────────────────────────────────────────────
function _readCookie(name) {
    const m = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : '';
}

function buildParams(extra = {}) {
    const ctx = _appContext;
    const vfp = _readCookie('s_v_web_id');
    const msToken = _readCookie('msToken');

    const base = {
        aid: '1988',
        app_name: 'tiktok_web',
        channel: 'tiktok_web',
        device_platform: 'web_pc',
        referer: '',
        cookie_enabled: String(navigator.cookieEnabled),
        screen_width: String(screen.width),
        screen_height: String(screen.height),
        browser_language: navigator.language,
        browser_platform: navigator.platform,
        browser_name: navigator.appCodeName,
        browser_version: String(navigator.appVersion).slice(0, 120),
        browser_online: String(navigator.onLine),
        verifyFp: vfp,
        is_page_visible: 'true',
        focus_state: 'true',
        is_fullscreen: 'false',
        history_len: String(window.history.length),
        battery_info: '1',
        tz_name: Intl.DateTimeFormat().resolvedOptions().timeZone,
        data_collection_enabled: 'true',
    };

    if (msToken) base.msToken = msToken;

    if (ctx) {
        // wid / device_id
        if (ctx.$wid) base.device_id = ctx.$wid;
        else if (ctx.wid) base.device_id = ctx.wid;

        // region
        if (ctx.$region) base.region = ctx.$region;
        else if (ctx.region) base.region = ctx.region;

        // odinId (required by TikTok for /api/post/item_list/)
        if (ctx.odinId) base.odinId = ctx.odinId;

        // WebIdLastTime (= webIdCreatedTime in context)
        if (ctx.webIdCreatedTime) base.WebIdLastTime = ctx.webIdCreatedTime;

        // user info
        const user = ctx.$user || ctx.user || ctx.userInfo || {};
        if (user.region) base.priority_region = user.region;
        // user_is_login flag
        const uid = user.uid || user.id || user.userId;
        if (uid) base.user_is_login = 'true';

        if (ctx.$os) base.os = ctx.$os;
        else if (ctx.os) base.os = ctx.os;

        const lang = ctx.$language || ctx.language || ctx.appLanguage;
        if (lang) {
            base.app_language = lang;
            base.webcast_language = lang;
        }
    }

    return Object.assign(base, extra);
}

function toQS(params) {
    return Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(String(v)))
        .join('&');
}

// ─── Get captured signed headers from background.js ─────────────────────────
async function getCapturedHeaders() {
    try {
        const r = await chrome.storage.session.get(['tiktokCapturedHeaders']);
        return r.tiktokCapturedHeaders || null;
    } catch (_) { return null; }
}

async function getCapturedRequest() {
    try {
        const r = await chrome.storage.session.get(['tiktokCapturedRequest']);
        return r.tiktokCapturedRequest || null;
    } catch (_) { return null; }
}

async function getCapturedRequestByPath(domain, path) {
    try {
        const host = domain.replace(/^https?:\/\//, '');
        const key = host + path;
        const r = await chrome.storage.session.get(['tiktokCapturedRequestsByPath', 'tiktokCapturedRequest']);
        return (r.tiktokCapturedRequestsByPath && r.tiktokCapturedRequestsByPath[key]) || r.tiktokCapturedRequest || null;
    } catch (_) { return null; }
}

function mergeCapturedParams(baseParams, capturedRequest, domain, path, extraParams) {
    const capturedHost = capturedRequest && capturedRequest.host;
    const capturedPath = capturedRequest && capturedRequest.path;
    const host = domain.replace(/^https?:\/\//, '');
    const sameEndpoint = capturedHost === host && capturedPath === path;
    const capturedParams = sameEndpoint && capturedRequest && capturedRequest.params
        ? capturedRequest.params
        : {};
    return Object.assign({}, baseParams, capturedParams, extraParams);
}

// pageFetchText: runs the actual fetch in main world via page-bridge.js (loaded
// automatically via manifest content_script world:MAIN) then returns the result.
// Uses window.postMessage which reliably crosses the isolated↔main world boundary.
async function pageFetchText(url, headers) {
    return new Promise((resolve, reject) => {
        const _wid = '__wf_' + Date.now() + '_' + Math.random().toString(36).slice(2);
        const timeoutId = setTimeout(() => {
            window.removeEventListener('message', onMsg);
            reject(new Error('Page fetch timed out — make sure you are on a TikTok page'));
        }, 15000);

        function onMsg(ev) {
            if (!ev.data || ev.data._wordai_type !== 'fetch-res' || ev.data._wid !== _wid) return;
            clearTimeout(timeoutId);
            window.removeEventListener('message', onMsg);
            if (ev.data.error) { reject(new Error(ev.data.error)); return; }
            resolve(ev.data);
        }

        window.addEventListener('message', onMsg);
        window.postMessage({
            _wordai_type: 'fetch-req',
            _wid: _wid,
            url: url,
            headers: headers || {},
        }, '*');
    });
}

// ttFetch: primary domain is m.tiktok.com (works for likes/saved/following).
// Pass host='www' to use www.tiktok.com (needed for /api/post/item_list/).

// getCachedPostsPage: asks page-bridge.js (MAIN world) for a response that
// TikTok loaded natively. Returns {text, url, ts} or null.
async function getCachedPostsPage(secUid, cursor) {
    return new Promise((resolve) => {
        const _wid = '__cp_' + Date.now() + '_' + Math.random().toString(36).slice(2);
        const tid = setTimeout(() => {
            window.removeEventListener('message', onMsg);
            resolve(null);
        }, 2000);
        function onMsg(ev) {
            if (!ev.data || ev.data._wordai_type !== 'cached-posts-res' || ev.data._wid !== _wid) return;
            clearTimeout(tid);
            window.removeEventListener('message', onMsg);
            resolve(ev.data.cached || null);
        }
        window.addEventListener('message', onMsg);
        window.postMessage({
            _wordai_type: 'get-cached-posts',
            _wid: _wid,
            secUid: secUid,
            cursor: String(cursor != null ? cursor : '0'),
        }, '*');
    });
}

// scrollCollect: asks page-bridge.js (MAIN world) to auto-scroll the target
// profile — TikTok's own JS fires paginated API calls, which the bridge
// intercepts and caches. Works exactly like myfaveTT's auto-scroll mechanism.
// Resolves with { items: rawTikTokItem[], onProfile: bool }.
function scrollCollect(secUid, uniqueId, autoNavigate, timeoutMs) {
    if (timeoutMs === undefined) timeoutMs = 90000;
    return new Promise(function (resolve, reject) {
        var _wid = '__sc_' + Date.now() + '_' + Math.random().toString(36).slice(2);
        var tid = setTimeout(function () {
            window.removeEventListener('message', onMsg);
            resolve({ items: [], onProfile: false });
        }, timeoutMs);
        function onMsg(ev) {
            if (!ev.data || ev.data._wordai_type !== 'scroll-collect-res' || ev.data._wid !== _wid) return;
            clearTimeout(tid);
            window.removeEventListener('message', onMsg);
            if (ev.data.error) { reject(new Error(ev.data.error)); return; }
            resolve({ items: ev.data.items || [], onProfile: !!ev.data.onProfile });
        }
        window.addEventListener('message', onMsg);
        window.postMessage({
            _wordai_type: 'scroll-collect',
            _wid: _wid,
            secUid: secUid,
            uniqueId: uniqueId || '',
            autoNavigate: !!autoNavigate,
        }, '*');
    });
}

// getCachedFollowing: asks page-bridge.js for a natively-intercepted /api/user/list/ response.
async function getCachedFollowing(maxCursor) {
    return new Promise(function (resolve) {
        var _wid = '__gf_' + Date.now() + '_' + Math.random().toString(36).slice(2);
        var tid = setTimeout(function () { window.removeEventListener('message', onMsg); resolve(null); }, 2000);
        function onMsg(ev) {
            if (!ev.data || ev.data._wordai_type !== 'cached-following-res' || ev.data._wid !== _wid) return;
            clearTimeout(tid); window.removeEventListener('message', onMsg);
            resolve(ev.data.cached || null);
        }
        window.addEventListener('message', onMsg);
        window.postMessage({ _wordai_type: 'get-cached-following', _wid: _wid, maxCursor: String(maxCursor || '0') }, '*');
    });
}

async function ttFetch(path, extraParams, host) {
    const domain = host === 'www' ? 'https://www.tiktok.com' : 'https://m.tiktok.com';

    // ── Try page-bridge cache first for /api/post/item_list/ ─────────────────
    // TikTok signs every request with per-request tokens we cannot generate.
    // The most reliable source is TikTok's own native fetch, which page-bridge.js
    // intercepts and stores keyed by secUid:cursor.
    if (path === '/api/post/item_list/' && extraParams && extraParams.secUid != null) {
        const cached = await getCachedPostsPage(extraParams.secUid, extraParams.cursor || 0);
        if (cached && cached.text) {
            try {
                const data = JSON.parse(cached.text);
                if (data && (data.itemList !== undefined || data.statusCode === 0)) {
                    LOG('ttFetch: served from page-bridge cache', {
                        secUid: String(extraParams.secUid).slice(0, 20),
                        cursor: extraParams.cursor || 0,
                        items: (data.itemList || []).length,
                    });
                    return data;
                }
            } catch (_) { }
        }
        // Cache miss: TikTok hasn't loaded this page yet.
        // The direct API call below will likely fail (no X-Bogus), so tell the user
        // to open the profile page first so TikTok loads the data natively.
        LOG('ttFetch: cache miss for item_list', {
            secUid: String(extraParams.secUid).slice(0, 20),
            cursor: extraParams.cursor || 0,
        });
    }

    const capturedRequest = await getCapturedRequestByPath(domain, path);
    const params = mergeCapturedParams(buildParams(extraParams), capturedRequest, domain, path, extraParams);
    const qs = toQS(params);
    const url = domain + path + '?' + qs;

    // Build headers: use captured signed headers from real TikTok API requests
    const capturedHeaders = await getCapturedHeaders();
    const reqHeaders = {};
    if (capturedHeaders) {
        const forward = ['x-secsdk-csrf-token', 'tt-csrf-token', 'x-tt-params',
            'x-gorgon', 'x-khronos', 'x-argus', 'x-ladon', 'x-tt-logid',
            'x-ttweb-token', 'x-web-id'];
        for (const h of forward) {
            if (capturedHeaders[h]) reqHeaders[h] = capturedHeaders[h];
        }
    }

    let resp, text;
    try {
        const pageResp = await pageFetchText(url, reqHeaders);
        resp = pageResp;
        if (!pageResp.ok) throw new Error('API HTTP ' + pageResp.status);
        text = pageResp.text;
    } catch (e) {
        throw new Error('Network error: ' + e.message);
    }

    // Diagnose what TikTok returned
    if (!text || !text.includes('"statusCode"') && !text.includes('"itemList"') && !text.includes('"userList"') && !text.includes('"userInfo"')) {
        LOG('ttFetch non-JSON response', {
            url,
            status: resp && resp.status,
            contentType: resp && resp.contentType,
            headersPresent: Object.keys(reqHeaders),
            capturedRequest: capturedRequest ? {
                host: capturedRequest.host,
                path: capturedRequest.path,
                keys: Object.keys(capturedRequest.params || {}),
            } : null,
            preview: text.slice(0, 400),
        });
        throw new Error(
            path === '/api/post/item_list/'
                ? 'Could not load posts. Please open the TikTok profile page for this account, wait for it to finish loading, then try again.'
                : 'TikTok returned a non-JSON response. If this keeps happening, please open any TikTok page and scroll the feed, then try again.'
        );
    }

    let data;
    try { data = JSON.parse(text); }
    catch (_) { throw new Error('TikTok response parse error: ' + text.slice(0, 100)); }

    // statusCode 0 = OK; some endpoints omit it
    if (data.statusCode !== undefined && data.statusCode !== 0) {
        if (data.statusCode === 10000) throw new Error('TikTok needs captcha verification. Please solve it on the page first.');
        throw new Error('TikTok API error: ' + data.statusCode + ' — ' + (data.message || JSON.stringify(data).slice(0, 80)));
    }
    return data;
}

// ─── Item Normalizer ──────────────────────────────────────────────────────────
function normalizeItem(item, source) {
    const isImage = !!(item.imagePost);
    const ts = item.createTime ? item.createTime * 1000 : 0;
    const author = item.author || {};

    return {
        id: String(item.id || ''),
        desc: item.desc || '',
        created_at: ts ? new Date(ts).toISOString() : '',
        created_date: ts ? new Date(ts).toISOString().split('T')[0] : '',
        created_timestamp: item.createTime || 0,
        media_type: isImage ? 'image' : 'video',
        image_count: isImage ? ((item.imagePost.images || []).length) : 0,
        stats: {
            likes: (item.stats && item.stats.diggCount) || 0,
            comments: (item.stats && item.stats.commentCount) || 0,
            shares: (item.stats && item.stats.shareCount) || 0,
            plays: (item.stats && item.stats.playCount) || 0,
        },
        author: {
            id: String(author.id || ''),
            username: author.uniqueId || '',
            nickname: author.nickname || '',
        },
        videoUrl: !isImage ? (
            (item.video && (item.video.playAddr || item.video.downloadAddr)) || ''
        ) : '',
        coverUrl: !isImage ? (
            (item.video && (item.video.originCover || item.video.cover || item.video.dynamicCover)) || ''
        ) : '',
        url: author.uniqueId
            ? 'https://www.tiktok.com/@' + author.uniqueId + '/video/' + item.id
            : 'https://www.tiktok.com/video/' + item.id,
        source,
    };
}

function normalizeAuthor(u) {
    return {
        id: String(u.user.id),
        secUid: u.user.secUid || '',
        username: u.user.uniqueId || '',
        nickname: u.user.nickname || '',
        avatar: u.user.avatarThumb || '',
        followerCount: (u.stats && u.stats.followerCount) || 0,
        videoCount: (u.stats && u.stats.videoCount) || 0,
    };
}

// ─── Message Dispatcher ───────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener(function (req, _sender, sendResponse) {
    if (req.action === 'toggleSidebar') {
        toggleSidebarVisibility();
        sendResponse({ ok: true });
        return;
    }
    dispatch(req)
        .then(sendResponse)
        .catch(function (err) { sendResponse({ error: err.message }); });
    return true; // async
});

// ─── Sidebar Injection ────────────────────────────────────────────────────────
let _sidebarVisible = false;

function injectSidebar() {
    if (document.getElementById('wordai-sidebar-wrap')) return;

    // Main sidebar frame
    const wrap = document.createElement('div');
    wrap.id = 'wordai-sidebar-wrap';
    Object.assign(wrap.style, {
        position: 'fixed',
        left: '0',
        top: '0',
        width: '380px',
        height: '100vh',
        zIndex: '2147483647',
        boxShadow: '4px 0 24px rgba(0,0,0,.55)',
        transform: 'translateX(-100%)',
        transition: 'transform 0.25s cubic-bezier(.4,0,.2,1)',
        willChange: 'transform',
    });

    const iframe = document.createElement('iframe');
    iframe.id = 'wordai-sidebar-iframe';
    iframe.setAttribute('src', chrome.runtime.getURL('sidebar.html'));
    Object.assign(iframe.style, {
        width: '100%',
        height: '100%',
        border: 'none',
        display: 'block',
    });
    wrap.appendChild(iframe);
    document.documentElement.appendChild(wrap);

    // Floating tab handle on left edge when sidebar is closed
    const tab = document.createElement('div');
    tab.id = 'wordai-sidebar-tab';
    Object.assign(tab.style, {
        position: 'fixed',
        left: '0',
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: '2147483646',
        background: '#fe2c55',
        color: '#fff',
        padding: '10px 5px',
        borderRadius: '0 8px 8px 0',
        cursor: 'pointer',
        fontSize: '10px',
        fontWeight: '700',
        writingMode: 'vertical-rl',
        textOrientation: 'mixed',
        letterSpacing: '1.5px',
        textTransform: 'uppercase',
        boxShadow: '2px 0 10px rgba(254,44,85,.4)',
        userSelect: 'none',
        fontFamily: 'system-ui, sans-serif',
        transition: 'left 0.25s cubic-bezier(.4,0,.2,1)',
    });
    tab.textContent = 'WordAI';
    tab.title = 'Toggle WordAI Collector';
    tab.addEventListener('click', toggleSidebarVisibility);
    document.documentElement.appendChild(tab);
}

function toggleSidebarVisibility() {
    injectSidebar();
    _sidebarVisible = !_sidebarVisible;
    const wrap = document.getElementById('wordai-sidebar-wrap');
    const tab = document.getElementById('wordai-sidebar-tab');
    const SIDEBAR_W = '380px';
    if (_sidebarVisible) {
        wrap.style.transform = 'translateX(0)';
        if (tab) tab.style.left = SIDEBAR_W;
        // Push page content right instead of overlaying
        document.body.style.transition = 'margin-left 0.25s cubic-bezier(.4,0,.2,1)';
        document.body.style.marginLeft = SIDEBAR_W;
    } else {
        wrap.style.transform = 'translateX(-100%)';
        if (tab) tab.style.left = '0';
        document.body.style.marginLeft = '';
    }
}

// Inject tab handle immediately so user can open sidebar at any time
injectSidebar();

async function dispatch(req) {
    const lang = (_appContext && _appContext.$language) || 'en';

    switch (req.action) {

        case 'ping':
            return { ok: true };

        // ── Init: Read page context and cache app state ──────────────────────────
        case 'getContext': {
            const ctx = await readPageState();
            if (!ctx) throw new Error('Could not read TikTok page state. Make sure the page is fully loaded.');
            _appContext = ctx;

            // Extract user from various possible structures
            let u = ctx.$user;

            // __UNIVERSAL_DATA_FOR_REHYDRATION__ structure: user may be at ctx.user or ctx.userInfo
            if (!u || !u.uid) {
                const alt = ctx.user || ctx.userInfo || ctx.loginUser;
                if (alt && (alt.uid || alt.id)) {
                    u = {
                        uid: alt.uid || alt.id,
                        secUid: alt.secUid || alt.sec_uid || '',
                        uniqueId: alt.uniqueId || alt.unique_id || alt.username || '',
                        nickName: alt.nickName || alt.nickname || alt.displayName || '',
                    };
                }
            }

            if (!u || (!u.uid && !u.id)) throw new Error('Not logged in to TikTok. Please log in first.');
            return {
                user: {
                    uid: u.uid || u.id,
                    secUid: u.secUid || u.sec_uid || '',
                    uniqueId: u.uniqueId || u.unique_id || u.username || '',
                    nickname: u.nickName || u.nickname || u.displayName || u.uniqueId || '',
                }
            };
        }

        // ── Liked posts ──────────────────────────────────────────────────────────
        case 'fetchLikes': {
            const data = await ttFetch('/api/favorite/item_list/', {
                secUid: req.secUid,
                cursor: req.cursor || 0,
                count: 30,
                from_page: 'user',
                language: lang,
            });
            return {
                items: (data.itemList || []).map(function (i) { return normalizeItem(i, 'likes'); }),
                hasMore: !!data.hasMore,
                nextCursor: data.cursor || 0,
            };
        }

        // ── Saved / Collected posts ───────────────────────────────────────────────
        case 'fetchSaved': {
            let data;
            try {
                data = await ttFetch('/api/user/collect/item_list/', {
                    secUid: req.secUid,
                    cursor: req.cursor || 0,
                    count: 30,
                    from_page: 'user',
                });
            } catch (_e) {
                // Fallback endpoint
                data = await ttFetch('/api/collect/item_list/', {
                    cursor: req.cursor || 0,
                    count: 30,
                });
            }
            return {
                items: (data.itemList || []).map(function (i) { return normalizeItem(i, 'saved'); }),
                hasMore: !!data.hasMore,
                nextCursor: data.cursor || 0,
            };
        }

        // ── Own profile posts ────────────────────────────────────────────────────
        case 'fetchMyPosts': {
            if ((req.cursor || 0) !== 0) return { items: [], hasMore: false, nextCursor: 0 };
            const myResult = await scrollCollect(req.secUid, req.uniqueId || '', true /*autoNavigate*/);
            if (myResult.items.length === 0) {
                if (!myResult.onProfile) {
                    throw new Error('Please open your TikTok profile page (tiktok.com/@you), let it finish loading, then try again.');
                }
                throw new Error('No posts found on your profile, or TikTok is still loading. Try scrolling your profile page first.');
            }
            return {
                items: myResult.items.map(function (i) { return normalizeItem(i, 'my_posts'); }),
                hasMore: false,
                nextCursor: 0,
            };
        }

        // ── Posts from a specific account (for following tab / channel tab) ────────
        case 'fetchUserPosts': {
            if ((req.cursor || 0) !== 0) return { items: [], hasMore: false, nextCursor: 0 };
            const userResult = await scrollCollect(
                req.secUid,
                req.uniqueId || '',
                req.autoNavigate || false
            );
            LOG('fetchUserPosts scrollCollect result', {
                uniqueId: req.uniqueId,
                count: userResult.items.length,
                onProfile: userResult.onProfile,
            });
            if (userResult.items.length === 0 && !userResult.onProfile) {
                const handle = req.uniqueId ? '@' + req.uniqueId : 'this account';
                throw new Error(
                    'To load posts for ' + handle + ', open their profile on TikTok (tiktok.com/' + (req.uniqueId ? '@' + req.uniqueId : '') + '), let the videos load, then try again.'
                );
            }
            return {
                items: userResult.items.map(function (i) { return normalizeItem(i, 'following'); }),
                hasMore: false,
                nextCursor: 0,
            };
        }

        // ── Following accounts list ──────────────────────────────────────────────
        case 'fetchFollowing': {
            if ((req.maxCursor || 0) === 0) {
                // Request page-bridge to auto-scroll the following modal and harvest everything!
                const result = await new Promise(resolve => {
                    const _wid = '__sf_' + Date.now();
                    const tid = setTimeout(() => resolve(null), 45000); // Wait up to 45 seconds for full scroll
                    const onMsg = (ev) => {
                        if (ev.data && ev.data._wordai_type === 'scroll-following-res' && ev.data._wid === _wid) {
                            clearTimeout(tid);
                            window.removeEventListener('message', onMsg);
                            resolve(ev.data);
                        }
                    };
                    window.addEventListener('message', onMsg);
                    window.postMessage({ _wordai_type: 'scroll-following-collect', _wid }, '*');
                });

                if (result && result.authors && result.authors.length > 0) {
                    LOG('Auto-scrolled and collected ' + result.authors.length + ' following accounts.');
                    if (!result.scrolled) {
                        // Modal wasn't open, just got the DOM dehydrated ones (31 accounts).
                        // Return them but set hasMore to true so they see "Load More"
                        // When they click "Load More", we will show them how to get the rest.
                        return {
                            authors: result.authors.map(normalizeAuthor),
                            hasMore: true,
                            maxCursor: 1, // Fake positive cursor to trigger "Load More" flow
                            minCursor: 0
                        };
                    }

                    // Modal WAS open, we scrolled and got EVERYTHING!
                    return {
                        authors: result.authors.map(normalizeAuthor),
                        hasMore: false, // We fetched all possible so no "Load More" needed!
                        maxCursor: -1,
                        minCursor: -1
                    };
                }
            }

            // Normal fallback (should rarely be hit now)
            const cachedF = await getCachedFollowing(req.maxCursor || 0);
            if (cachedF && cachedF.text) {
                try {
                    const fData = JSON.parse(cachedF.text);
                    if (fData && fData.userList !== undefined) {
                        return {
                            authors: (fData.userList || []).map(normalizeAuthor),
                            hasMore: !!fData.hasMore,
                            maxCursor: fData.maxCursor != null ? fData.maxCursor : -1,
                            minCursor: fData.minCursor != null ? fData.minCursor : -1,
                        };
                    }
                } catch (_) { }
            }

            throw new Error('WordAI cần giúp đỡ để lấy tiếp danh sách!\n\n1. Mở trang Profile TikTok của bạn.\n2. Click vào số "Đang theo dõi" để bật danh sách lên.\n3. Bấm lại nút "Load Following" ở trên cùng (KHÔNG bấm Load Mores).\nWordAI sẽ tự động cuộn trang ⚡cấp tốc⚡ và lấy TẤT CẢ following!');
        }

        // ── Resolve username → secUid (for Channel tab) ──────────────────────────
        case 'resolveUser': {
            const username = (req.username || '').replace(/^@/, '').trim();
            if (!username) throw new Error('Username is empty');

            // First try: www.tiktok.com/api/user/detail/
            let data = null;
            {
                const capturedRequest = await getCapturedRequestByPath('https://www.tiktok.com', '/api/user/detail/');
                const detailParams = mergeCapturedParams(
                    buildParams({ uniqueId: username, from_page: 'user' }),
                    capturedRequest,
                    'https://www.tiktok.com',
                    '/api/user/detail/',
                    { uniqueId: username, from_page: 'user' }
                );
                const qs = toQS(detailParams);
                const url = 'https://www.tiktok.com/api/user/detail/?' + qs;
                const capturedHeaders = await getCapturedHeaders();
                const reqHeaders = {};
                if (capturedHeaders) {
                    const forward = ['x-secsdk-csrf-token', 'tt-csrf-token', 'x-tt-params',
                        'x-gorgon', 'x-khronos', 'x-argus', 'x-ladon', 'x-tt-logid',
                        'x-ttweb-token', 'x-web-id'];
                    for (const h of forward) {
                        if (capturedHeaders[h]) reqHeaders[h] = capturedHeaders[h];
                    }
                }
                const resp = await pageFetchText(url, reqHeaders);
                const text = resp.text || '';
                if (resp.ok && text && text.trimStart().startsWith('{')) {
                    try { data = JSON.parse(text); } catch (_) { data = null; }
                }
            }

            // Fallback: scrape the user profile page
            if (!data || !data.userInfo) {
                const profileUrl = 'https://www.tiktok.com/@' + encodeURIComponent(username);
                const pageResp = await fetch(profileUrl, { credentials: 'include' });
                const html = await pageResp.text();
                console.log('[WordAI] resolveUser profile page status=' + pageResp.status +
                    ' hasUNIVERSAL=' + html.includes('__UNIVERSAL_DATA_FOR_REHYDRATION__') +
                    ' hasSIGI=' + html.includes('SIGI_STATE') +
                    ' hasWebappUserDetail=' + html.includes('webapp.user-detail'));
                // Try 2a: __UNIVERSAL_DATA_FOR_REHYDRATION__ (new TikTok format)
                const mUniv = html.match(/<script[^>]+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([\s\S]*?)<\/script>/);
                if (mUniv) {
                    try {
                        const univData = JSON.parse(mUniv[1]);
                        const scope = univData['__DEFAULT_SCOPE__'] || {};
                        const userDetail = scope['webapp.user-detail'] || {};
                        if (userDetail.userInfo) {
                            data = userDetail;
                        }
                    } catch (_) { /* ignore */ }
                }

                // Try 2b: window.__UNIVERSAL_DATA_FOR_REHYDRATION__ inline assignment
                if (!data || !data.userInfo) {
                    const mWin = html.match(/window\.__UNIVERSAL_DATA_FOR_REHYDRATION__\s*=\s*(\{[\s\S]*?\});\s*<\/script>/);
                    if (mWin) {
                        try {
                            const univData = JSON.parse(mWin[1]);
                            const scope = univData['__DEFAULT_SCOPE__'] || {};
                            const userDetail = scope['webapp.user-detail'] || {};
                            if (userDetail.userInfo) {
                                data = userDetail;
                            }
                        } catch (_) { /* ignore */ }
                    }
                }

                // Try 2c: legacy SIGI_STATE
                if (!data || !data.userInfo) {
                    const mSigi = html.match(/<script[^>]+id="SIGI_STATE"[^>]*>([\s\S]*?)<\/script>/);
                    if (mSigi) {
                        try {
                            const sigi = JSON.parse(mSigi[1]);
                            const userModule = sigi.UserModule || sigi.userModule;
                            if (userModule) {
                                const users = userModule.users || {};
                                const statsMap = userModule.stats || {};
                                const u = users[username] || Object.values(users)[0];
                                if (u) {
                                    const stats = statsMap[u.uniqueId] || statsMap[username] || {};
                                    data = { userInfo: { user: u, stats } };
                                }
                            }
                        } catch (_) { /* ignore */ }
                    }
                }

                // Try 2d: brace-scan for "webapp.user-detail" anywhere in the page (last resort)
                if (!data || !data.userInfo) {
                    const startIdx = html.indexOf('"webapp.user-detail"');
                    if (startIdx !== -1) {
                        const colonIdx = html.indexOf(':', startIdx);
                        let depth = 0, objStart = -1, objEnd = -1;
                        for (let ci = colonIdx; ci < html.length; ci++) {
                            if (html[ci] === '{') { if (depth === 0) objStart = ci; depth++; }
                            else if (html[ci] === '}') { depth--; if (depth === 0) { objEnd = ci; break; } }
                        }
                        if (objStart !== -1 && objEnd !== -1) {
                            try {
                                const blob = JSON.parse(html.slice(objStart, objEnd + 1));
                                if (blob.userInfo) data = blob;
                            } catch (_) { /* ignore */ }
                        }
                    }
                }
            }

            if (!data || !data.userInfo || !data.userInfo.user) {
                // Debug: log what markers exist in the page HTML to diagnose which fallback is needed
                console.warn('[WordAI] resolveUser failed for @' + username + '. data=', JSON.stringify(data).slice(0, 200));
                throw new Error('User @' + username + ' not found. Make sure you are on tiktok.com and logged in.');
            }

            if (data.statusCode && data.statusCode !== 0)
                throw new Error('User @' + username + ' not found (code ' + data.statusCode + ')');

            const u = data.userInfo.user;
            const stats = data.userInfo.stats || {};
            return {
                user: {
                    id: String(u.id || ''),
                    secUid: u.secUid || '',
                    username: u.uniqueId || username,
                    nickname: u.nickname || '',
                    avatar: u.avatarThumb || '',
                    followerCount: stats.followerCount || 0,
                    videoCount: stats.videoCount || 0,
                }
            };
        }

        // ── Fetch video bytes with TikTok session cookies ─────────────────────────
        case 'fetchVideoBytes': {
            const { videoUrl } = req;
            if (!videoUrl) throw new Error('No video URL provided');

            const resp = await fetch(videoUrl, { credentials: 'include' });
            if (!resp.ok) throw new Error('HTTP ' + resp.status + ' — cannot fetch video');

            const arrayBuffer = await resp.arrayBuffer();
            const bytes = new Uint8Array(arrayBuffer);
            const size = bytes.byteLength;

            if (size > 150 * 1024 * 1024)
                throw new Error('Video too large (' + (size / 1024 / 1024).toFixed(0) + ' MB). TikTok may have returned an error page.');

            // Encode to base64 in 8 KB chunks to avoid call-stack overflow
            let binary = '';
            const CHUNK = 8192;
            for (let i = 0; i < bytes.length; i += CHUNK) {
                binary += String.fromCharCode(...bytes.subarray(i, Math.min(i + CHUNK, bytes.length)));
            }
            return { base64: btoa(binary), size };
        }

        default:
            throw new Error('Unknown action: ' + req.action);
    }
}
