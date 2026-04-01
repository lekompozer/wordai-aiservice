'use strict';
// WordAI TikTok Collector — Content Script (isolated world)
// Injected on tiktok.com. Handles all TikTok API calls.

let _appContext = null; // Cached once from SIGI_STATE

// ─── Page State Reader ────────────────────────────────────────────────────────
// Inject inline script to read page-level window variables
function readPageState() {
    return new Promise((resolve, reject) => {
        const msgId = '__wordai_' + Date.now() + '_' + Math.random().toString(36).slice(2);

        const timer = setTimeout(() => {
            window.removeEventListener('message', onMsg);
            reject(new Error('Timeout reading TikTok page state. Try refreshing the page.'));
        }, 4000);

        function onMsg(ev) {
            if (ev.source !== window || !ev.data || ev.data.type !== msgId) return;
            clearTimeout(timer);
            window.removeEventListener('message', onMsg);
            resolve(ev.data.payload);
        }
        window.addEventListener('message', onMsg);

        const script = document.createElement('script');
        script.textContent = `(function(){
      var s = window.SIGI_STATE, n = window.__NEXT_DATA__, ctx = null;
      if(s && s.AppContext && s.AppContext.appContext) ctx = s.AppContext.appContext;
      else if(n && n.props && n.props.initialProps) ctx = n.props.initialProps;
      window.postMessage({type:'${msgId}', payload: ctx}, '*');
    })();`;
        document.documentElement.appendChild(script);
        script.remove();
    });
}

// ─── TikTok API Parameter Builder ────────────────────────────────────────────
function buildParams(extra = {}) {
    const ctx = _appContext;
    const vfp = (document.cookie.match(/s_v_web_id=([\w-]+)/) || [])[1] || '';

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
    };

    if (ctx) {
        if (ctx.$wid) base.device_id = ctx.$wid;
        if (ctx.$region) base.region = ctx.$region;
        if (ctx.$user && ctx.$user.region) base.priority_region = ctx.$user.region;
        if (ctx.$os) base.os = ctx.$os;
        if (ctx.$language) {
            base.app_language = ctx.$language;
            base.webcast_language = ctx.$language;
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

async function ttFetch(path, extraParams) {
    const url = 'https://m.tiktok.com' + path + '?' + toQS(buildParams(extraParams));
    const resp = await fetch(url, { credentials: 'include' });
    if (!resp.ok) throw new Error('API HTTP ' + resp.status);
    const data = await resp.json();
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
    dispatch(req)
        .then(sendResponse)
        .catch(function (err) { sendResponse({ error: err.message }); });
    return true; // async
});

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
            const u = ctx.$user;
            if (!u || !u.uid) throw new Error('Not logged in to TikTok. Please log in first.');
            return {
                user: {
                    uid: u.uid,
                    secUid: u.secUid || '',
                    uniqueId: u.uniqueId || '',
                    nickname: u.nickName || u.nickname || u.uniqueId || '',
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
            const data = await ttFetch('/api/post/item_list/', {
                secUid: req.secUid,
                cursor: req.cursor || 0,
                count: 35,
                from_page: 'user',
                language: lang,
            });
            return {
                items: (data.itemList || []).map(function (i) { return normalizeItem(i, 'my_posts'); }),
                hasMore: !!data.hasMore,
                nextCursor: data.cursor || 0,
            };
        }

        // ── Posts from a specific account (for following tab) ────────────────────
        case 'fetchUserPosts': {
            const data = await ttFetch('/api/post/item_list/', {
                secUid: req.secUid,
                cursor: req.cursor || 0,
                count: 35,
                from_page: 'user',
                language: lang,
            });
            return {
                items: (data.itemList || []).map(function (i) { return normalizeItem(i, 'following'); }),
                hasMore: !!data.hasMore,
                nextCursor: data.cursor || 0,
            };
        }

        // ── Following accounts list ──────────────────────────────────────────────
        case 'fetchFollowing': {
            const data = await ttFetch('/api/user/list/', {
                scene: 21,
                from_page: 'fyp',
                maxCursor: req.maxCursor || 0,
                minCursor: req.minCursor || 0,
                count: 20,
            });
            return {
                authors: (data.userList || []).map(normalizeAuthor),
                hasMore: !!data.hasMore,
                maxCursor: data.maxCursor != null ? data.maxCursor : -1,
                minCursor: data.minCursor != null ? data.minCursor : -1,
            };
        }

        default:
            throw new Error('Unknown action: ' + req.action);
    }
}
