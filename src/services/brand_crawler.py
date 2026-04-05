"""
Brand Crawler Service

Pipeline (pure Jina — no Playwright):
  1. Jina Reader API (r.jina.ai) on entry URL → clean Markdown with embedded nav links
  2. Parse links from Jina markdown → discover important sub-pages (About/Products/Pricing…)
  3. Jina in parallel for up to 2 best sub-pages
  4. Merge all Markdown into combined_text for LLM consumption

No Playwright. No headless browser. Fast, low-memory, reliable.
User provides logo/images directly in the UI — no need to extract them from the site.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import httpx

logger = logging.getLogger(__name__)

JINA_TIMEOUT_S = 20
MAX_CHARS_PER_PAGE_JINA = 4000  # per-page Jina markdown cap
MAX_JINA_PAGES = 3  # entry + up to 2 sub-pages

JINA_BASE = "https://r.jina.ai/"
JINA_HEADERS = {
    "Accept": "text/plain",
    "X-Return-Format": "markdown",
    "X-Timeout": str(JINA_TIMEOUT_S),
}

# Path segments that identify important brand pages
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
# Sub-page discovery from Jina markdown (no Playwright)
# ─────────────────────────────────────────────────────────────────────────────


def _score_path(path: str) -> int:
    """Return importance score 0–10 for a URL path segment."""
    segs = [s for s in path.lower().strip("/").split("/") if s]
    if len(segs) > 1:
        return 0
    if not segs:
        return 3  # homepage
    seg = segs[0]
    for kw in _IMPORTANT_KEYWORDS:
        if kw in seg or seg in kw:
            return 10
    return 0


def _extract_subpages(markdown: str, base_url: str) -> List[str]:
    """
    Parse markdown links from Jina output to discover internal sub-pages.
    Returns up to (MAX_JINA_PAGES - 1) best sub-page URLs, scored by importance.
    """
    parsed = urlparse(base_url)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    entry_path = base_url.rstrip("/")

    scored: Dict[str, int] = {}

    # Match markdown links: [text](url) and bare URLs
    patterns = [
        r"\[(?:[^\]]*)\]\((https?://[^\s\)]+)\)",  # [text](https://...)
        r"\[(?:[^\]]*)\]\((/[^\s\)]*)\)",  # [text](/relative)
        r'https?://[^\s\)\]"\'<>]+',  # bare absolute URL
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, markdown):
            href = match.group(1) if "(" in pattern else match.group(0)
            # Resolve relative URLs
            if href.startswith("/"):
                href = base_origin + href
            # Strip query/fragment
            href = href.split("?")[0].split("#")[0].rstrip("/")
            if not href.startswith(base_origin):
                continue
            if href == entry_path:
                continue
            path = urlparse(href).path
            score = _score_path(path)
            if score > 0:
                scored[href] = max(scored.get(href, 0), score)

    return sorted(scored, key=lambda u: scored[u], reverse=True)[: MAX_JINA_PAGES - 1]


# ─────────────────────────────────────────────────────────────────────────────
# Main public function for brand analysis pipeline
# ─────────────────────────────────────────────────────────────────────────────


async def discover_and_crawl_website(entry_url: str) -> Dict[str, Any]:
    """
    Pure-Jina pipeline: fetch entry URL → discover sub-pages from markdown links
    → fetch best sub-pages in parallel → merge.

    No Playwright. No headless browser.
    User-provided logo/images are handled by the UI — not extracted here.

    Returns:
      {
        combined_text: str,       # Merged Markdown from all crawled pages
        primary_color: str,       # Empty — user provides logo/branding directly
        logo_url: str,            # Empty — user provides logo directly
        discovered_urls: list,
        title: str,               # From first Jina response header
        meta_description: str,
        websites: list,
      }
    """
    logger.info(f"[Crawler] Starting (Jina-only): {entry_url}")

    # Step 1: Fetch entry URL via Jina
    entry_md = await jina_fetch_markdown(entry_url)

    # Step 2: Discover sub-pages from markdown links
    sub_urls: List[str] = []
    if entry_md:
        sub_urls = _extract_subpages(entry_md, entry_url)
        logger.info(f"[Crawler] Discovered sub-pages: {sub_urls}")

    # Step 3: Build page list and fetch sub-pages in parallel
    jina_urls = [entry_url] + sub_urls
    if len(jina_urls) > 1:
        sub_markdowns = await asyncio.gather(
            *[jina_fetch_markdown(u) for u in sub_urls]
        )
    else:
        sub_markdowns = []

    all_markdowns = [entry_md] + list(sub_markdowns)

    # Step 4: Merge — label each section by source URL
    text_parts = []
    for url, md in zip(jina_urls, all_markdowns):
        if md and md.strip():
            text_parts.append(f"### [{url}]\n{md.strip()}")

    combined_text = "\n\n---\n\n".join(text_parts)
    logger.info(
        f"[Crawler] ✅ Combined: {len(combined_text)} chars from {len(text_parts)} pages"
    )

    # Extract title from first line of Jina markdown (format: "Title: XYZ")
    title = ""
    meta_description = ""
    for line in entry_md.splitlines():
        line = line.strip()
        if line.startswith("Title:"):
            title = line[len("Title:") :].strip()
        elif line.startswith("Description:"):
            meta_description = line[len("Description:") :].strip()
        if title and meta_description:
            break

    return {
        "combined_text": combined_text,
        "primary_color": "",  # User provides branding via UI
        "logo_url": "",  # User provides logo via UI
        "og_image": "",
        "title": title,
        "meta_description": meta_description,
        "discovered_urls": jina_urls,
        "websites": [
            {"url": u, "success": bool(md and md.strip())}
            for u, md in zip(jina_urls, all_markdowns)
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Legacy stubs — kept for import compatibility, no longer use Playwright
# ─────────────────────────────────────────────────────────────────────────────


async def crawl_brand_url(url: str) -> Dict[str, Any]:
    """Legacy stub — delegates to Jina."""
    md = await jina_fetch_markdown(url)
    return {
        "url": url,
        "title": "",
        "meta_description": "",
        "og_image": "",
        "h1_texts": [],
        "h2_texts": [],
        "body_text": md[:2000] if md else "",
        "colors": {"primary": "#000000"},
        "fonts": {},
        "logo_url": "",
        "success": bool(md),
    }


async def crawl_brand_urls(urls: List[str]) -> List[Dict[str, Any]]:
    """Legacy stub — crawls via Jina (no Playwright)."""
    if not urls:
        return []
    urls = urls[:5]
    logger.info(f"🌐 Crawling {len(urls)} URLs via Jina (no Playwright)...")
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
    """Merge multiple crawl results into combined_text."""
    successful = [r for r in crawl_results if r.get("success")]
    if not successful:
        return {
            "websites": crawl_results,
            "combined_text": "",
            "primary_color": "#000000",
            "logo_url": "",
        }

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
        "primary_color": "#000000",
        "logo_url": "",
        "fonts": {},
    }
