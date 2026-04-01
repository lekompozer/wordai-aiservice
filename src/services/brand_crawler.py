"""
Brand Crawler Service

Pipeline (HTML → Markdown → LLM-ready text):
  Primary:  Jina Reader API (r.jina.ai) — returns clean Markdown in 1 HTTP call,
            strips nav/scripts/ads automatically, ~80% fewer tokens than raw HTML.
  Fallback: Playwright headless browser — used when Jina fails or for color/logo
            extraction (which Jina strips).

Flow for discover_and_crawl_website():
  1. Playwright on entry URL → extract brand colors, logo URL, nav links
  2. Determine key sub-pages (About / Products / Pricing / Team) from nav links
  3. Jina Reader in parallel for entry URL + up to 2 sub-pages → clean Markdown
  4. Merge: combined_text = Jina markdowns, colors/logo from Playwright
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

CRAWL_TIMEOUT_MS = 15000
JINA_TIMEOUT_S = 15
MAX_BODY_CHARS = 2000  # Playwright fallback cap
MAX_CHARS_PER_PAGE_JINA = 3500  # per-page Jina markdown cap (~875 tokens)
MAX_URLS = 5
MAX_JINA_PAGES = 3  # entry + up to 2 sub-pages via Jina

JINA_BASE = "https://r.jina.ai/"
JINA_HEADERS = {
    "Accept": "text/plain",
    "X-Return-Format": "markdown",
    "X-Timeout": str(JINA_TIMEOUT_S),
}

# Path keywords that identify important brand pages
_IMPORTANT_KEYWORDS = {
    "about",
    "about-us",
    "aboutus",
    "ve-chung-toi",
    "product",
    "products",
    "san-pham",
    "tinh-nang",
    "features",
    "feature",
    "solution",
    "solutions",
    "pricing",
    "price",
    "prices",
    "bang-gia",
    "plans",
    "plan",
    "team",
    "doi-ngu",
    "who-we-are",
    "service",
    "services",
    "dich-vu",
}


# ─────────────────────────────────────────────────────────────────────────────
# Jina Reader helpers
# ─────────────────────────────────────────────────────────────────────────────


async def jina_fetch_markdown(url: str) -> str:
    """
    Fetch clean Markdown for a URL via Jina Reader.
    Returns empty string on failure (non-fatal).
    """
    jina_url = JINA_BASE + url
    try:
        async with httpx.AsyncClient(
            timeout=JINA_TIMEOUT_S + 5, follow_redirects=True
        ) as client:
            resp = await client.get(jina_url, headers=JINA_HEADERS)
            if resp.status_code == 200:
                text = resp.text or ""
                logger.info(f"✅ Jina OK: {url} → {len(text)} chars")
                return text[:MAX_CHARS_PER_PAGE_JINA]
            else:
                logger.warning(f"Jina {resp.status_code} for {url}")
                return ""
    except Exception as e:
        logger.warning(f"Jina fetch failed for {url}: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Sub-page discovery (Playwright, navigation links only)
# ─────────────────────────────────────────────────────────────────────────────


def _score_path(url: str, base_origin: str) -> int:
    """Return importance score 0–10 for a discovered URL."""
    if not url.startswith(base_origin):
        return 0
    path = urlparse(url).path.lower().strip("/")
    segs = [s for s in path.split("/") if s]
    if len(segs) > 1 or "#" in url:
        return 0
    if not segs:
        return 3  # homepage
    seg = segs[0]
    for kw in _IMPORTANT_KEYWORDS:
        if kw in seg or seg in kw:
            return 10
    return 0


async def _playwright_meta(url: str) -> Dict[str, Any]:
    """
    Use Playwright to extract: brand colors, logo URL, nav links.
    Lightweight — does NOT extract body text (Jina handles that).
    """
    from playwright.async_api import async_playwright

    parsed = urlparse(url)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                page = await browser.new_page()
                await page.set_extra_http_headers({"Accept-Language": "en,vi;q=0.9"})
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=CRAWL_TIMEOUT_MS
                )
                await asyncio.sleep(1)

                data = await page.evaluate(
                    """
                (function() {
                    var meta = function(name) {
                        var el = document.querySelector('meta[name="' + name + '"], meta[property="' + name + '"], meta[property="og:' + name + '"]');
                        return el ? el.getAttribute("content") : "";
                    };
                    var primaryColor = "";
                    var themeEl = document.querySelector('meta[name="theme-color"]');
                    if (themeEl) primaryColor = themeEl.getAttribute("content") || "";
                    if (!primaryColor) {
                        var root = getComputedStyle(document.documentElement);
                        primaryColor = (root.getPropertyValue("--primary") ||
                                        root.getPropertyValue("--brand-color") ||
                                        root.getPropertyValue("--color-primary") ||
                                        root.getPropertyValue("--primary-color") || "").trim();
                    }
                    var logoEl = document.querySelector("img.logo, img[alt*='logo' i], header img, nav img, .logo img, a[href='/'] img");
                    var faviconEl = document.querySelector("link[rel='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']");
                    var logoUrl = (logoEl ? (logoEl.src || logoEl.getAttribute("data-src") || "") : "") || (faviconEl ? faviconEl.href : "");
                    var links = Array.from(document.querySelectorAll("a[href]")).map(function(a) { return a.href; });
                    return {
                        primary_color: primaryColor,
                        logo_url: logoUrl,
                        og_image: meta("image") || "",
                        title: document.title || "",
                        meta_description: meta("description") || "",
                        links: links.slice(0, 80)
                    };
                })()
                """
                )
                await browser.close()
            except Exception:
                await browser.close()
                raise

        # Score discovered links
        scored = {}
        for href in data.get("links", []):
            href = href.split("?")[0].split("#")[0].rstrip("/")
            if not href:
                continue
            score = _score_path(href, base_origin)
            if score > 0:
                scored[href] = max(scored.get(href, 0), score)

        sub_urls = sorted(scored, key=lambda u: scored[u], reverse=True)[
            :MAX_JINA_PAGES
        ]

        return {
            "primary_color": data.get("primary_color", "").strip() or "#000000",
            "logo_url": data.get("logo_url", ""),
            "og_image": data.get("og_image", ""),
            "title": data.get("title", ""),
            "meta_description": data.get("meta_description", ""),
            "sub_urls": sub_urls,
            "success": True,
        }

    except Exception as e:
        logger.warning(f"Playwright meta extraction failed for {url}: {e}")
        return {
            "primary_color": "#000000",
            "logo_url": "",
            "og_image": "",
            "title": "",
            "meta_description": "",
            "sub_urls": [],
            "success": False,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Main public function for brand analysis pipeline
# ─────────────────────────────────────────────────────────────────────────────


async def discover_and_crawl_website(entry_url: str) -> Dict[str, Any]:
    """
    Full pipeline: discover sub-pages → Jina Markdown for content → merge.

    Steps:
      1. Playwright on entry_url → colors, logo, nav links (fast, metadata only)
      2. Jina Reader on entry_url + up to 2 best sub-pages → clean Markdown
      3. Merge into combined_text for LLM consumption

    Returns:
      {
        combined_text: str,   # Markdown content from all crawled pages
        primary_color: str,
        logo_url: str,
        discovered_urls: list[str],
        title: str,
        meta_description: str,
      }
    """
    logger.info(f"[Crawler] Starting: {entry_url}")

    # Step 1: Playwright for metadata + nav discovery
    meta = await _playwright_meta(entry_url)
    sub_urls = meta.get("sub_urls", [])

    # Determine pages to fetch via Jina (entry + up to 2 sub-pages, dedup)
    jina_urls = [entry_url]
    for u in sub_urls:
        if u not in jina_urls and u.rstrip("/") != entry_url.rstrip("/"):
            jina_urls.append(u)
        if len(jina_urls) >= MAX_JINA_PAGES:
            break

    logger.info(f"[Crawler] Jina fetching {len(jina_urls)} pages: {jina_urls}")

    # Step 2: Jina in parallel
    markdowns = await asyncio.gather(*[jina_fetch_markdown(u) for u in jina_urls])

    # Step 3: Merge text — label each page section
    text_parts = []
    for url, md in zip(jina_urls, markdowns):
        if md.strip():
            text_parts.append(f"### [{url}]\n{md.strip()}")

    # Fallback: if ALL Jina calls failed, use Playwright body text
    if not any(markdowns):
        logger.warning(
            "[Crawler] All Jina calls failed — falling back to Playwright body text"
        )
        fallback_results = await crawl_brand_urls([entry_url])
        merged = merge_brand_data(fallback_results)
        merged["discovered_urls"] = jina_urls
        merged["primary_color"] = meta.get("primary_color", "#000000")
        merged["logo_url"] = meta.get("logo_url", "")
        return merged

    combined_text = "\n\n---\n\n".join(text_parts)
    logger.info(
        f"[Crawler] ✅ Combined text: {len(combined_text)} chars from {len(text_parts)} pages"
    )

    return {
        "combined_text": combined_text,
        "primary_color": meta.get("primary_color", "#000000"),
        "logo_url": meta.get("logo_url", ""),
        "og_image": meta.get("og_image", ""),
        "title": meta.get("title", ""),
        "meta_description": meta.get("meta_description", ""),
        "discovered_urls": jina_urls,
        "websites": [
            {"url": u, "success": bool(md.strip())}
            for u, md in zip(jina_urls, markdowns)
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Legacy helpers (used by social plan pipeline — unchanged API)
# ─────────────────────────────────────────────────────────────────────────────


async def crawl_brand_url(url: str) -> Dict[str, Any]:
    """
    Crawl a single URL and extract brand data (Playwright).
    Kept for legacy social plan pipeline compatibility.
    For brand analysis, use discover_and_crawl_website() instead.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                page = await browser.new_page()
                await page.set_extra_http_headers({"Accept-Language": "en,vi;q=0.9"})
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=CRAWL_TIMEOUT_MS
                )
                await asyncio.sleep(1)

                data = await page.evaluate(
                    """
                (function() {
                    var meta = function(name) {
                        var el = document.querySelector('meta[name="' + name + '"], meta[property="' + name + '"], meta[property="og:' + name + '"]');
                        return el ? el.getAttribute("content") : "";
                    };
                    var themeEl = document.querySelector('meta[name="theme-color"]');
                    var primary = themeEl ? themeEl.getAttribute("content") || "" : "";
                    if (!primary) {
                        var root = getComputedStyle(document.documentElement);
                        primary = (root.getPropertyValue("--primary") ||
                                   root.getPropertyValue("--brand-color") ||
                                   root.getPropertyValue("--color-primary") ||
                                   root.getPropertyValue("--primary-color") || "").trim();
                    }
                    if (!primary) {
                        var header = document.querySelector("header, nav");
                        if (header) primary = getComputedStyle(header).backgroundColor || "";
                    }
                    var h1 = document.querySelector("h1");
                    var headingFont = h1 ? getComputedStyle(h1).fontFamily : "";
                    var bodyText = (document.body.innerText || document.body.textContent || "").slice(0, 2000);
                    var logoEl = document.querySelector("img.logo, img[alt*='logo' i], header img, nav img, .logo img, a[href='/'] img");
                    var faviconEl = document.querySelector("link[rel='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']");
                    return {
                        title: document.title || "",
                        meta_description: meta("description") || "",
                        og_image: meta("image") || "",
                        h1_texts: Array.from(document.querySelectorAll("h1")).map(function(el) { return el.textContent.trim(); }).filter(Boolean).slice(0, 5),
                        h2_texts: Array.from(document.querySelectorAll("h2")).map(function(el) { return el.textContent.trim(); }).filter(Boolean).slice(0, 10),
                        body_text: bodyText.trim(),
                        primary_color: primary || "",
                        heading_font: headingFont.split(",")[0].replace(/['"]/g, "").trim(),
                        body_font: getComputedStyle(document.body).fontFamily.split(",")[0].replace(/['"]/g, "").trim(),
                        logo_url: (logoEl ? (logoEl.src || logoEl.getAttribute("data-src") || "") : "") || (faviconEl ? faviconEl.href : "")
                    };
                })()
                """
                )

                return {
                    "url": url,
                    "title": data.get("title", ""),
                    "meta_description": data.get("meta_description", ""),
                    "og_image": data.get("og_image", ""),
                    "h1_texts": data.get("h1_texts", []),
                    "h2_texts": data.get("h2_texts", []),
                    "body_text": data.get("body_text", "")[:MAX_BODY_CHARS],
                    "colors": {
                        "primary": data.get("primary_color", "").strip() or "#000000"
                    },
                    "fonts": {
                        "heading": data.get("heading_font", ""),
                        "body": data.get("body_font", ""),
                    },
                    "logo_url": data.get("logo_url", ""),
                    "success": True,
                }
            finally:
                await browser.close()

    except Exception as e:
        logger.warning(f"Failed to crawl {url}: {e}")
        return {
            "url": url,
            "title": "",
            "meta_description": "",
            "og_image": "",
            "h1_texts": [],
            "h2_texts": [],
            "body_text": "",
            "colors": {"primary": "#000000"},
            "fonts": {},
            "logo_url": "",
            "success": False,
            "error": str(e),
        }


async def crawl_brand_urls(urls: List[str]) -> List[Dict[str, Any]]:
    """Crawl multiple URLs in parallel (max 5). Legacy helper."""
    if not urls:
        return []
    urls = urls[:MAX_URLS]
    logger.info(f"🌐 Crawling {len(urls)} URLs in parallel (Playwright)...")
    results = await asyncio.gather(
        *[crawl_brand_url(u) for u in urls], return_exceptions=True
    )
    output = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Crawl failed for {urls[i]}: {result}")
            output.append(
                {
                    "url": urls[i],
                    "success": False,
                    "error": str(result),
                    "title": "",
                    "body_text": "",
                    "h1_texts": [],
                    "h2_texts": [],
                    "colors": {"primary": "#000000"},
                    "fonts": {},
                    "logo_url": "",
                }
            )
        else:
            output.append(result)
    successful = sum(1 for r in output if r.get("success"))
    logger.info(f"✅ Crawled {successful}/{len(urls)} URLs successfully")
    return output


def merge_brand_data(crawl_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple Playwright crawl results. Legacy helper."""
    successful = [r for r in crawl_results if r.get("success")]
    if not successful:
        return {
            "websites": crawl_results,
            "combined_text": "",
            "primary_color": "#000000",
            "logo_url": "",
        }

    primary_color = ""
    logo_url = ""
    for r in successful:
        if not primary_color and r.get("colors", {}).get("primary"):
            primary_color = r["colors"]["primary"]
        if not logo_url and r.get("logo_url"):
            logo_url = r["logo_url"]

    text_parts = []
    for r in successful:
        parts = []
        if r.get("title"):
            parts.append(f"Title: {r['title']}")
        if r.get("meta_description"):
            parts.append(f"Description: {r['meta_description']}")
        if r.get("h1_texts"):
            parts.append("Headlines: " + " | ".join(r["h1_texts"]))
        if r.get("body_text"):
            parts.append(r["body_text"][:1000])
        if parts:
            text_parts.append(f"[{r['url']}]\n" + "\n".join(parts))

    return {
        "websites": crawl_results,
        "combined_text": "\n\n---\n\n".join(text_parts),
        "primary_color": primary_color or "#000000",
        "logo_url": logo_url,
        "fonts": successful[0].get("fonts", {}) if successful else {},
    }
