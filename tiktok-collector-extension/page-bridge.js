// page-bridge.js — runs in MAIN world (via manifest content_scripts world:MAIN)
// 1. Intercepts TikTok's own fetch() calls to cache signed API responses.
// 2. Proxies explicit fetch() requests from the isolated content script via postMessage.
// postMessage is the standard cross-world communication channel in MV3.
(function () {
    if (window.__wordaiPageBridgeInstalled) return;
    window.__wordaiPageBridgeInstalled = true;

    // ── Caches for intercepted TikTok API responses ───────────────────────────
    if (!window._wordaiPostsCache) window._wordaiPostsCache = {};     // secUid:cursor → {text,url,ts}
    if (!window._wordaiApiCache) window._wordaiApiCache = {};     // 'following:maxCursor' → {text,url,ts}

    // Save original fetch before TikTok's JS can touch it
    var _nativeFetch = window.fetch;

    // Wrap window.fetch to intercept TikTok API responses
    window.fetch = function (resource, options) {
        var url = typeof resource === 'string' ? resource
            : (resource && typeof resource.url === 'string' ? resource.url : String(resource));
        var promise = _nativeFetch.apply(this, arguments);

        var isPostList = url && url.indexOf('/api/post/item_list/') !== -1;
        var isUserList = url && url.indexOf('/api/user/list/') !== -1;
        var isNextData = url && url.indexOf('/_next/data/') !== -1 && url.indexOf('.json') !== -1;

        if (isPostList || isUserList || isNextData) {
            promise.then(function (response) {
                try {
                    var clone = response.clone();
                    clone.text().then(function (text) {
                        if (!text) return;
                        var params;
                        try {
                            var u = url.indexOf('://') !== -1 ? url : window.location.origin + (url.charAt(0) === '/' ? '' : '/') + url;
                            params = new URL(u).searchParams;
                        } catch (_) { return; }
                        if (isPostList) {
                            var secUid = params.get('secUid') || params.get('sec_uid') || '';
                            var cursor = params.get('cursor') || '0';
                            if (!secUid) return;
                            window._wordaiPostsCache[secUid + ':' + cursor] = { text: text, url: url, ts: Date.now() };
                            console.log('[WordAI Bridge] Intercepted post stream: secUid=' + secUid + ' cursor=' + cursor);
                        } else if (isUserList) {
                            var maxCursor = params.get('maxCursor') || '0';
                            window._wordaiApiCache['following:' + maxCursor] = { text: text, url: url, ts: Date.now() };
                            console.log('[WordAI Bridge] Intercepted user list: maxCursor=' + maxCursor);
                        } else if (isNextData) {
                            try {
                                var parsed = JSON.parse(text);
                                // The initial itemList is usually inside pageProps -> userInfo -> ... or something similar
                                var items = null;
                                if (parsed && parsed.pageProps && parsed.pageProps.userInfo && parsed.pageProps.userInfo.itemList) {
                                    items = parsed.pageProps.userInfo.itemList;
                                } else if (parsed && parsed.pageProps && parsed.pageProps.itemInfo && parsed.pageProps.itemInfo.itemStruct) {
                                    items = [parsed.pageProps.itemInfo.itemStruct];
                                }

                                if (items && items.length > 0) {
                                    var secUid = items[0].author ? items[0].author.secUid : '';
                                    if (secUid) {
                                        window._wordaiPostsCache[secUid + ':_next_data_' + Date.now()] = { text: JSON.stringify({ itemList: items }), url: url, ts: Date.now() };
                                        console.log('[WordAI Bridge] Intercepted _next/data for user: secUid=' + secUid + ' items=' + items.length);
                                    }
                                }
                            } catch (_) { }
                        }
                    }).catch(function () { });
                } catch (_) { }
            }).catch(function () { });
        }
        return promise;
    };

    // ── Message handler ───────────────────────────────────────────────────────
    window.addEventListener('message', async function (ev) {
        if (!ev.data || typeof ev.data._wordai_type !== 'string') return;
        var type = ev.data._wordai_type;
        var reqWid = ev.data._wid;

        // ── Cached following list lookup ──────────────────────────────────────
        if (type === 'get-cached-following') {
            var maxCursor = String(ev.data.maxCursor != null ? ev.data.maxCursor : '0');

            // Try to harvest from DOM if not in cache (especially for cursor 0)
            if (maxCursor === '0' && (!window._wordaiApiCache || !window._wordaiApiCache['following:0'])) {
                try {
                    let foundUserList = null;
                    let foundHasMore = false;
                    let foundMaxCursor = 0;
                    let foundMinCursor = 0;

                    function recursivelyFindUserList(obj, depth) {
                        if (!obj || depth > 8 || foundUserList) return;
                        if (Array.isArray(obj)) {
                            for (var i = 0; i < obj.length; i++) recursivelyFindUserList(obj[i], depth + 1);
                        } else if (typeof obj === 'object') {
                            if (Array.isArray(obj.userList) && obj.userList.length > 0 && obj.userList[0].secUid && obj.userList[0].uniqueId) {
                                foundUserList = obj.userList;
                                foundHasMore = obj.hasMore;
                                foundMaxCursor = obj.maxCursor;
                                foundMinCursor = obj.minCursor;
                                return;
                            }
                            for (var k in obj) {
                                if (Object.prototype.hasOwnProperty.call(obj, k)) recursivelyFindUserList(obj[k], depth + 1);
                            }
                        }
                    }

                    if (window.__UNIVERSAL_DATA_FOR_REHYDRATION__) recursivelyFindUserList(window.__UNIVERSAL_DATA_FOR_REHYDRATION__, 0);
                    if (!foundUserList && window.SIGI_STATE) recursivelyFindUserList(window.SIGI_STATE, 0);

                    if (foundUserList) {
                        window._wordaiApiCache['following:0'] = {
                            text: JSON.stringify({
                                userList: foundUserList,
                                maxCursor: foundMaxCursor || 0,
                                minCursor: foundMinCursor || 0,
                                hasMore: foundHasMore || false
                            }),
                            ts: Date.now()
                        };
                        console.log('[WordAI Bridge] Harvested user list from DOM, found ' + foundUserList.length + ' users');
                    }
                } catch (_) { }
            }

            var cached = (window._wordaiApiCache && window._wordaiApiCache['following:' + maxCursor]) || null;
            window.postMessage({ _wordai_type: 'cached-following-res', _wid: reqWid, cached: cached }, '*');
            return;
        }

        // ── Auto-scroll Following Modal & Harvest All ─────────────────────────
        if (type === 'scroll-following-collect') {
            var sfWid = reqWid;
            (async function () {
                try {
                    var scrollableModal = null;
                    var dialogs = document.querySelectorAll('div[role="dialog"], [class*="Modal"], [class*="dialog"]');
                    for (var i = 0; i < dialogs.length; i++) {
                        var childDivs = dialogs[i].querySelectorAll('div');
                        for (var j = 0; j < childDivs.length; j++) {
                            var child = childDivs[j];
                            if (child.scrollHeight > child.clientHeight + 50 && child.clientHeight > 200) {
                                scrollableModal = child;
                                break;
                            }
                        }
                        if (scrollableModal) break;
                    }

                    if (scrollableModal) {
                        console.log('[WordAI Bridge] Found following modal, auto-scrolling...');
                        var scrollStalls = 0, lastH = 0;
                        while (scrollStalls < 4) {
                            scrollableModal.scrollTop = scrollableModal.scrollHeight;
                            await new Promise(function (r) { setTimeout(r, 1200); });
                            if (scrollableModal.scrollHeight <= lastH + 30) {
                                scrollStalls++;
                            } else {
                                scrollStalls = 0;
                                lastH = scrollableModal.scrollHeight;
                            }
                        }
                    }

                    var allAuthorsMap = {};
                    var addAuthors = function (users) {
                        if (!Array.isArray(users)) return;
                        for (var i = 0; i < users.length; i++) {
                            var u = users[i];
                            var target = u.user || u.author || u;
                            if (target && target.secUid) {
                                allAuthorsMap[target.secUid] = u;
                            }
                        }
                    };

                    var foundUniversal = false;
                    function recursivelyFindUniversalUsers(obj, depth) {
                        if (!obj || depth > 8) return;
                        if (Array.isArray(obj)) {
                            for (var i = 0; i < obj.length; i++) recursivelyFindUniversalUsers(obj[i], depth + 1);
                        } else if (typeof obj === 'object') {
                            if (Array.isArray(obj.userList) && obj.userList.length > 0 && obj.userList[0].secUid) {
                                addAuthors(obj.userList);
                                foundUniversal = true;
                            }
                            for (var k in obj) {
                                if (Object.prototype.hasOwnProperty.call(obj, k)) recursivelyFindUniversalUsers(obj[k], depth + 1);
                            }
                        }
                    }
                    if (window.__UNIVERSAL_DATA_FOR_REHYDRATION__) recursivelyFindUniversalUsers(window.__UNIVERSAL_DATA_FOR_REHYDRATION__, 0);
                    if (!foundUniversal && window.SIGI_STATE) recursivelyFindUniversalUsers(window.SIGI_STATE, 0);

                    var cacheEntries = Object.entries(window._wordaiApiCache || {});
                    cacheEntries.forEach(function (kv) {
                        if (kv[0].startsWith('following:')) {
                            try {
                                var d = JSON.parse(kv[1].text);
                                addAuthors(d.userList);
                            } catch (_) { }
                        }
                    });

                    var finalAuthors = [];
                    for (var k in allAuthorsMap) finalAuthors.push(allAuthorsMap[k]);

                    window.postMessage({ _wordai_type: 'scroll-following-res', _wid: sfWid, authors: finalAuthors, scrolled: !!scrollableModal }, '*');
                } catch (e) {
                    window.postMessage({ _wordai_type: 'scroll-following-res', _wid: sfWid, authors: [], error: String(e) }, '*');
                }
            })();
            return;
        }

        // ── Cached posts page lookup ──────────────────────────────────────────
        if (type === 'get-cached-posts') {
            var cpSecUid = ev.data.secUid || '';
            var cpCursor = String(ev.data.cursor != null ? ev.data.cursor : '0');
            var cpCached = (window._wordaiPostsCache && window._wordaiPostsCache[cpSecUid + ':' + cpCursor]) || null;
            window.postMessage({ _wordai_type: 'cached-posts-res', _wid: reqWid, cached: cpCached }, '*');
            return;
        }

        // ── Auto-scroll profile and collect all posts ─────────────────────────
        if (type === 'scroll-collect') {
            var scWid = reqWid;
            var sc_secUid = ev.data.secUid || '';
            var sc_uid = (ev.data.uniqueId || '').toLowerCase();
            var sc_uidOrig = ev.data.uniqueId || '';
            var sc_autoNav = !!ev.data.autoNavigate;

            (async function () {
                var onTargetProfile = false;
                try {
                    if (sc_uid) {
                        var curPath = window.location.pathname.toLowerCase().split('?')[0];
                        var target = '/@' + sc_uid;
                        onTargetProfile = curPath === target || curPath.startsWith(target + '/');

                        if (!onTargetProfile && sc_autoNav) {
                            var navigated = false;

                            // Method 1: Next.js Pages Router with routeChangeComplete event
                            try {
                                if (window.next && window.next.router &&
                                    typeof window.next.router.push === 'function') {
                                    await new Promise(function (resolve) {
                                        var done = false;
                                        function finish() {
                                            if (done) return; done = true;
                                            try { window.next.router.events.off('routeChangeComplete', finish); } catch (_) { }
                                            resolve();
                                        }
                                        try { window.next.router.events.on('routeChangeComplete', finish); } catch (_) { }
                                        try { window.next.router.push('/@' + sc_uidOrig); } catch (_) { finish(); }
                                        setTimeout(finish, 6000);
                                    });
                                    curPath = window.location.pathname.toLowerCase().split('?')[0];
                                    onTargetProfile = curPath === target || curPath.startsWith(target + '/');
                                    if (onTargetProfile) navigated = true;
                                }
                            } catch (_) { }

                            // Method 2: history.pushState + popstate (triggers SPA routing)
                            if (!navigated) {
                                try {
                                    window.history.pushState({}, '', '/@' + sc_uidOrig);
                                    window.dispatchEvent(new PopStateEvent('popstate', { state: {} }));
                                    await new Promise(function (r) { setTimeout(r, 4000); });
                                    curPath = window.location.pathname.toLowerCase().split('?')[0];
                                    onTargetProfile = curPath === target || curPath.startsWith(target + '/');
                                } catch (_) { }
                            }
                        }
                    } else {
                        onTargetProfile = true; // no target given — scroll current page
                    }

                    // ── Scroll to trigger TikTok's lazy loading ───────────────
                    if (onTargetProfile) {
                        // Wait for TikTok's first API call after navigation
                        await new Promise(function (r) { setTimeout(r, 1500); });
                        var scrollStalls = 0, lastH = 0;
                        while (scrollStalls < 4) {
                            window.scrollTo(0, document.body.scrollHeight);
                            await new Promise(function (r) { setTimeout(r, 1500); });
                            var newH = document.body.scrollHeight;
                            if (newH <= lastH + 50) { scrollStalls++; } else { scrollStalls = 0; lastH = newH; }
                        }
                    }
                } catch (_) { }

                // ── Harvest all cached pages for this secUid ──────────────────
                var allItemsMap = {}; // deduplicate by item id
                var addItems = function (arr) {
                    if (!Array.isArray(arr)) return;
                    for (var i = 0; i < arr.length; i++) {
                        if (arr[i] && arr[i].id) allItemsMap[arr[i].id] = arr[i];
                    }
                };

                // 1. Harvest from window.__UNIVERSAL_DATA_FOR_REHYDRATION__ and window.SIGI_STATE via generic scanner
                try {
                    function recursivelyFindItems(obj, depth) {
                        if (!obj || depth > 10) return;
                        if (Array.isArray(obj)) {
                            for (var i = 0; i < obj.length; i++) recursivelyFindItems(obj[i], depth + 1);
                        } else if (typeof obj === 'object') {
                            // Is this an item struct?
                            if (obj.id && obj.desc !== undefined && obj.createTime && obj.author && obj.author.secUid && obj.video) {
                                addItems([obj]);
                            }
                            for (var k in obj) {
                                if (Object.prototype.hasOwnProperty.call(obj, k)) recursivelyFindItems(obj[k], depth + 1);
                            }
                        }
                    }
                    if (window.__UNIVERSAL_DATA_FOR_REHYDRATION__) recursivelyFindItems(window.__UNIVERSAL_DATA_FOR_REHYDRATION__, 0);
                    if (window.SIGI_STATE) recursivelyFindItems(window.SIGI_STATE, 0);
                } catch (_) { }

                // 3. Harvest intercepted API and _next/data payloads
                var cacheEntries = Object.entries(window._wordaiPostsCache || {});
                cacheEntries
                    .filter(function (kv) { return kv[0].startsWith(sc_secUid + ':'); })
                    .sort(function (a, b) {
                        return (parseInt(a[0].split(':')[1]) || 0) - (parseInt(b[0].split(':')[1]) || 0);
                    })
                    .forEach(function (kv) {
                        try {
                            var d = JSON.parse(kv[1].text);
                            if (Array.isArray(d.itemList)) {
                                addItems(d.itemList);
                            }
                        } catch (_) { }
                    });

                var allItems = [];
                for (var id in allItemsMap) {
                    if (!sc_secUid || (allItemsMap[id].author && allItemsMap[id].author.secUid === sc_secUid)) {
                        allItems.push(allItemsMap[id]);
                    }
                }

                window.postMessage({
                    _wordai_type: 'scroll-collect-res',
                    _wid: scWid,
                    items: allItems,
                    onProfile: onTargetProfile,
                }, '*');
            })();
            return;
        }

        // ── Proxied fetch (for endpoints like user/detail, favorites, etc.) ───
        if (type !== 'fetch-req') return;
        const { _wid, url, headers } = ev.data;
        if (!_wid || !url) return;

        try {
            const resp = await _nativeFetch.call(window, url, {
                method: 'GET',
                credentials: 'include',
                headers: headers || {},
            });
            const text = await resp.text();
            window.postMessage({
                _wordai_type: 'fetch-res',
                _wid: _wid,
                ok: resp.ok,
                status: resp.status,
                contentType: resp.headers.get('content-type') || '',
                text: text,
            }, '*');
        } catch (err) {
            window.postMessage({
                _wordai_type: 'fetch-res',
                _wid: _wid,
                error: err && err.message ? err.message : String(err),
            }, '*');
        }
    });
})();
