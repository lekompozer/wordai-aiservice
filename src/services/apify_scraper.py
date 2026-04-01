"""
Apify Social Media Scraper

Fetches recent posts (text only) from Facebook, Instagram, or TikTok pages
using the Apify platform.

Actors used:
  Facebook  : apify~facebook-posts-scraper  (KoJrdxJCTtpon81KY)
  Instagram : apify~instagram-scraper       (shu8hvrXbJbY3Eb9W)
  TikTok    : clockworks~tiktok-scraper

Pricing: ~$5.00 per 1,000 posts
  - Demo  : 10  posts / 1 URL  → ~$0.05
  - Full  : 15 posts × 3 URLs  → ~$0.225

Requires: APIFY_API_TOKEN env var
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"

# Actor IDs
ACTOR_FACEBOOK  = "KoJrdxJCTtpon81KY"
ACTOR_INSTAGRAM = "shu8hvrXbJbY3Eb9W"
ACTOR_TIKTOK    = "clockworks~tiktok-scraper"

# Timeout: Apify jobs can take 30–120 s
APIFY_TIMEOUT = 180  # seconds


def _detect_platform(url: str) -> str:
    """Detect social platform from URL. Returns 'facebook' | 'instagram' | 'tiktok'."""
    url = url.lower()
    if "facebook.com" in url or "fb.com" in url:
        return "facebook"
    if "instagram.com" in url:
        return "instagram"
    if "tiktok.com" in url:
        return "tiktok"
    raise ValueError(f"Unsupported social URL: {url}. Must be Facebook, Instagram, or TikTok.")


def _extract_text_from_post(item: dict, platform: str) -> Optional[str]:
    """Extract plain text content from an Apify post item (skip images/video metadata)."""
    if platform == "facebook":
        return item.get("text") or item.get("message") or item.get("story")
    if platform == "instagram":
        return item.get("caption") or item.get("text")
    if platform == "tiktok":
        return item.get("text") or item.get("desc") or item.get("description")
    return None


def _build_run_input(url: str, platform: str, limit: int) -> tuple[str, dict]:
    """Returns (actor_id, run_input) for the given platform."""
    if platform == "facebook":
        return ACTOR_FACEBOOK, {
            "startUrls": [{"url": url}],
            "resultsLimit": limit,
            "captionText": True,
        }
    if platform == "instagram":
        return ACTOR_INSTAGRAM, {
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": limit,
            "addParentData": False,
        }
    # tiktok
    return ACTOR_TIKTOK, {
        "profiles": [url],
        "resultsPerPage": limit,
        "scrapeLastNDays": 90,
    }


async def _run_apify_actor(actor_id: str, run_input: dict, token: str) -> List[dict]:
    """
    Start an Apify actor, wait for it to finish, return dataset items.
    Uses the synchronous run-sync-get-dataset-items endpoint.
    """
    endpoint = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
    params = {"token": token, "format": "json", "clean": "true"}

    async with httpx.AsyncClient(timeout=APIFY_TIMEOUT) as client:
        resp = await client.post(endpoint, json=run_input, params=params)
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else []


async def fetch_social_posts(
    url: str,
    limit: int = 15,
    apify_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch recent posts from a Facebook / Instagram / TikTok URL.

    Returns:
        {
            "platform": "facebook" | "instagram" | "tiktok",
            "url": <original url>,
            "posts": [{"text": "...", "date": "...", "likes": ...}, ...],
            "posts_count": N,
        }
    """
    token = apify_token or os.getenv("APIFY_API_TOKEN")
    if not token:
        raise ValueError("APIFY_API_TOKEN not configured")

    platform = _detect_platform(url)
    actor_id, run_input = _build_run_input(url, platform, limit)

    logger.info(f"[Apify] Scraping {limit} posts from {platform}: {url}")
    raw_items = await _run_apify_actor(actor_id, run_input, token)

    posts = []
    for item in raw_items[:limit]:
        text = _extract_text_from_post(item, platform)
        if not text or not text.strip():
            continue
        post: Dict[str, Any] = {"text": text.strip()}
        # Attach lightweight metadata (no media URLs to keep costs low)
        for date_key in ("date", "timestamp", "time", "createdAt", "publishedAt"):
            if item.get(date_key):
                post["date"] = str(item[date_key])
                break
        for likes_key in ("likes", "likesCount", "likeCount"):
            if item.get(likes_key) is not None:
                post["likes"] = item[likes_key]
                break
        posts.append(post)

    logger.info(f"[Apify] Got {len(posts)} text posts from {url}")
    return {
        "platform": platform,
        "url": url,
        "posts": posts,
        "posts_count": len(posts),
    }


async def fetch_multiple_competitors(
    urls: List[str],
    limit_per_url: int = 15,
    apify_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch posts for multiple competitor URLs (up to 3).
    Runs sequentially to avoid Apify rate limits.
    """
    import asyncio

    results = []
    for url in urls[:3]:
        try:
            result = await fetch_social_posts(url, limit=limit_per_url, apify_token=apify_token)
            results.append(result)
        except Exception as e:
            logger.error(f"[Apify] Failed for {url}: {e}")
            results.append({
                "platform": "unknown",
                "url": url,
                "posts": [],
                "posts_count": 0,
                "_error": str(e),
            })
    return results
