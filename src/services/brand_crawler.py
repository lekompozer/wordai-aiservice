"""
Brand Crawler Service
Uses Playwright to crawl brand websites and extract brand data.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

CRAWL_TIMEOUT_MS = 15000
MAX_BODY_CHARS = 2000
MAX_URLS = 5


async def crawl_brand_url(url: str) -> Dict[str, Any]:
    """
    Crawl a single URL and extract brand data.

    Args:
        url: Website URL to crawl

    Returns:
        Dict with title, meta_description, h1_texts, h2_texts, body_text, colors, fonts, logo_url, og_image
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

                # Extract all data in parallel via JS evaluation
                data = await page.evaluate(
                    """
                () => {
                    const meta = (name) => {
                        const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"], meta[property="og:${name}"]`);
                        return el ? el.getAttribute("content") : "";
                    };

                    // Colors from various sources
                    const themeColor = document.querySelector('meta[name="theme-color"]');
                    let primary = themeColor ? themeColor.getAttribute("content") : "";

                    // Try CSS custom properties
                    if (!primary) {
                        const root = getComputedStyle(document.documentElement);
                        primary = root.getPropertyValue("--primary") ||
                                  root.getPropertyValue("--brand-color") ||
                                  root.getPropertyValue("--color-primary") ||
                                  root.getPropertyValue("--primary-color") || "";
                        primary = primary.trim();
                    }

                    // Try header/nav background
                    if (!primary) {
                        const header = document.querySelector("header, nav");
                        if (header) {
                            primary = getComputedStyle(header).backgroundColor || "";
                        }
                    }

                    // Fonts
                    let headingFont = "";
                    let bodyFont = "";
                    const h1 = document.querySelector("h1");
                    if (h1) headingFont = getComputedStyle(h1).fontFamily;
                    bodyFont = getComputedStyle(document.body).fontFamily;

                    // Body text
                    const bodyEl = document.body;
                    const bodyText = (bodyEl.innerText || bodyEl.textContent || "").slice(0, 2000);

                    // Logo
                    const logoEl = document.querySelector("img.logo, img[alt*='logo' i], header img, nav img, .logo img, .navbar-brand img, a[href='/'] img");
                    const logoUrl = logoEl ? (logoEl.src || logoEl.getAttribute("data-src") || "") : "";

                    // Favicon as fallback for logo
                    const faviconEl = document.querySelector("link[rel='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']");
                    const faviconUrl = faviconEl ? faviconEl.href : "";

                    return {
                        title: document.title || "",
                        meta_description: meta("description") || "",
                        og_image: meta("image") || "",
                        h1_texts: Array.from(document.querySelectorAll("h1")).map(el => el.textContent.trim()).filter(Boolean).slice(0, 5),
                        h2_texts: Array.from(document.querySelectorAll("h2")).map(el => el.textContent.trim()).filter(Boolean).slice(0, 10),
                        body_text: bodyText.trim(),
                        primary_color: primary || "",
                        heading_font: headingFont.split(",")[0].replace(/['"]/g, "").trim(),
                        body_font: bodyFont.split(",")[0].replace(/['"]/g, "").trim(),
                        logo_url: logoUrl || faviconUrl || "",
                        canonical_url: document.querySelector("link[rel='canonical']")?.href || ""
                    };
                }
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
                        "primary": data.get("primary_color", "").strip() or "#000000",
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
            "fonts": {"heading": "", "body": ""},
            "logo_url": "",
            "success": False,
            "error": str(e),
        }


async def crawl_brand_urls(urls: List[str]) -> List[Dict[str, Any]]:
    """
    Crawl multiple URLs in parallel (max 5).

    Args:
        urls: List of website URLs

    Returns:
        List of brand data dicts
    """
    if not urls:
        return []

    # Limit to MAX_URLS
    urls = urls[:MAX_URLS]
    logger.info(f"🌐 Crawling {len(urls)} URLs in parallel...")

    tasks = [crawl_brand_url(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

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
    """
    Merge multiple crawl results into a single brand data summary.

    Args:
        crawl_results: List of individual crawl results

    Returns:
        Merged brand data dict
    """
    successful = [r for r in crawl_results if r.get("success")]
    if not successful:
        return {
            "websites": crawl_results,
            "combined_text": "",
            "primary_color": "#000000",
            "logo_url": "",
        }

    # Take primary color from first successful result
    primary_color = ""
    logo_url = ""
    for r in successful:
        if not primary_color and r.get("colors", {}).get("primary"):
            primary_color = r["colors"]["primary"]
        if not logo_url and r.get("logo_url"):
            logo_url = r["logo_url"]

    # Combine text content for analysis
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
