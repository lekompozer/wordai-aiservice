// WordAI TikTok Collector — Background service worker (MV3 required)
chrome.runtime.onInstalled.addListener(() => {
    console.log('WordAI TikTok Collector installed.');
});

// ─── Intercept TikTok's own API requests to capture valid signed headers ─────
// TikTok requires signed headers (X-Secsdk-Csrf-Token, X-Gorgon, etc.) that
// we cannot generate. We capture them from TikTok's own requests and reuse them.
let _captureThrottle = 0;
chrome.webRequest.onSendHeaders.addListener(
    function (details) {
        if (details.method !== 'GET') return;
        if (details.initiator && details.initiator.startsWith('chrome-extension://')) return;

        // Throttle: only update every 5 seconds to avoid storage spam
        const now = Date.now();
        if (now - _captureThrottle < 5000) return;
        _captureThrottle = now;

        const headers = {};
        for (const h of (details.requestHeaders || [])) {
            headers[h.name.toLowerCase()] = h.value;
        }

        let requestMeta = null;
        try {
            const parsed = new URL(details.url);
            const params = {};
            for (const [key, value] of parsed.searchParams.entries()) {
                params[key] = value;
            }
            requestMeta = {
                host: parsed.host,
                path: parsed.pathname,
                url: details.url,
                params,
                capturedAt: now,
            };
        } catch (_) { }

        const nextState = { tiktokCapturedHeaders: headers };
        if (requestMeta) nextState.tiktokCapturedRequest = requestMeta;

        chrome.storage.session.set(nextState)
            .then(() => {
                if (!requestMeta) return null;
                return chrome.storage.session.get(['tiktokCapturedRequestsByPath'])
                    .then((stored) => {
                        const byPath = Object.assign({}, stored.tiktokCapturedRequestsByPath || {});
                        byPath[requestMeta.host + requestMeta.path] = requestMeta;
                        return chrome.storage.session.set({ tiktokCapturedRequestsByPath: byPath });
                    });
            })
            .catch(() => { });
    },
    { urls: ['https://www.tiktok.com/api/*', 'https://m.tiktok.com/api/*'] },
    ['requestHeaders', 'extraHeaders']
);

// Toolbar icon click → toggle sidebar on the current TikTok tab
chrome.action.onClicked.addListener(async (tab) => {
    if (!tab.url || !tab.url.includes('tiktok.com')) {
        chrome.tabs.create({ url: 'https://www.tiktok.com' });
        return;
    }
    try {
        await chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' });
    } catch (_e) {
        // Content script not yet injected — inject it then toggle
        try {
            await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
            await chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' });
        } catch (e2) {
            console.error('[WordAI] Could not toggle sidebar:', e2.message);
        }
    }
});
