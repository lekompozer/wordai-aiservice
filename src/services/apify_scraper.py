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
ACTOR_FACEBOOK = "KoJrdxJCTtpon81KY"
ACTOR_INSTAGRAM = "shu8hvrXbJbY3Eb9W"
ACTOR_TIKTOK = "clockworks~tiktok-scraper"

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
    raise ValueError(
        f"Unsupported social URL: {url}. Must be Facebook, Instagram, or TikTok."
    )


def _extract_text_from_post(item: dict, platform: str) -> Optional[str]:
    """Extract plain text content from an Apify post item (skip images/video metadata)."""
    if platform == "facebook":
        return item.get("text") or item.get("message") or item.get("story")
    if platform == "instagram":
        return item.get("caption") or item.get("text")
    if platform == "tiktok":
        # TikTok text field is directly "text"
        return item.get("text") or item.get("desc") or item.get("description")
    return None


def _extract_tiktok_username(url: str) -> str:
    """Extract @username from a TikTok URL for the profiles input."""
    import re as _re

    m = _re.search(r"tiktok\.com/@([^/?#]+)", url)
    return m.group(1) if m else url


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
    # TikTok — clockworks~tiktok-scraper
    # profiles accepts @username strings, not full URLs
    username = _extract_tiktok_username(url)
    return ACTOR_TIKTOK, {
        "profiles": [username],
        "resultsPerPage": limit,
        "profileScrapeSections": ["videos"],
        "profileSorting": "latest",
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadAvatars": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadMusicCovers": False,
        "scrapeRelatedVideos": False,
        "excludePinnedPosts": False,
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
    page_followers: Optional[int] = None  # extracted from TikTok authorMeta

    for item in raw_items[:limit]:
        text = _extract_text_from_post(item, platform)
        if not text or not text.strip():
            continue
        post: Dict[str, Any] = {"text": text.strip()}

        if platform == "tiktok":
            # TikTok has its own specific field names from clockworks~tiktok-scraper
            post["date"] = item.get("createTimeISO") or str(item.get("createTime", ""))
            post["likes"] = item.get("diggCount")  # likes = diggs on TikTok
            post["comments"] = item.get("commentCount")
            post["shares"] = item.get("shareCount")
            post["views"] = item.get("playCount")
            post["collects"] = item.get("collectCount")  # saves/bookmarks
            post["is_video"] = not bool(item.get("isSlideshow", False))
            post["duration_sec"] = (item.get("videoMeta") or {}).get("duration")
            # Grab followers from authorMeta (same for every post from the same page)
            if page_followers is None:
                page_followers = (item.get("authorMeta") or {}).get("fans")
        else:
            # Human-readable date preferred, fallback to unix timestamp
            for date_key in ("time", "date", "createdAt", "publishedAt", "timestamp"):
                if item.get(date_key):
                    post["date"] = str(item[date_key])
                    break

            # Facebook: topReactionsCount = total reactions
            for likes_key in ("topReactionsCount", "likes", "likesCount", "likeCount"):
                if item.get(likes_key) is not None:
                    post["likes"] = item[likes_key]
                    break

            for comments_key in (
                "comments",
                "commentsCount",
                "commentCount",
                "numComments",
            ):
                if item.get(comments_key) is not None:
                    post["comments"] = item[comments_key]
                    break

            for shares_key in ("shares", "sharesCount", "shareCount", "numShares"):
                if item.get(shares_key) is not None:
                    post["shares"] = item[shares_key]
                    break

            # viewsCount is the exact Facebook field name from Apify
            for views_key in (
                "viewsCount",
                "views",
                "viewCount",
                "videoViewCount",
                "playCount",
            ):
                if item.get(views_key) is not None:
                    post["views"] = item[views_key]
                    break

            post["is_video"] = bool(item.get("isVideo", False))

        posts.append(post)

    logger.info(f"[Apify] Got {len(posts)} text posts from {url}")
    return {
        "platform": platform,
        "url": url,
        "posts": posts,
        "posts_count": len(posts),
        "engagement_metrics": compute_engagement_metrics(posts),
        # For TikTok, followers scraped automatically from authorMeta
        "page_followers": page_followers,
    }


def compute_engagement_metrics(
    posts: List[dict], followers_count: Optional[int] = None
) -> Dict[str, Any]:
    """
    Compute aggregate engagement stats from a list of posts.
    Returns avg likes/comments/shares/views, top post by likes, and engagement rate.
    """
    if not posts:
        return {}

    total_likes = sum(p.get("likes") or 0 for p in posts)
    total_comments = sum(p.get("comments") or 0 for p in posts)
    total_shares = sum(p.get("shares") or 0 for p in posts)
    total_views = sum(p.get("views") or 0 for p in posts)
    n = len(posts)

    metrics: Dict[str, Any] = {
        "posts_analyzed": n,
        "avg_likes": round(total_likes / n, 1),
        "avg_comments": round(total_comments / n, 1),
        "avg_shares": (
            round(total_shares / n, 1)
            if any(p.get("shares") is not None for p in posts)
            else None
        ),
        "avg_views": (
            round(total_views / n, 1)
            if any(p.get("views") is not None for p in posts)
            else None
        ),
        "total_likes": total_likes,
        "total_comments": total_comments,
    }

    # Engagement rate = (likes + comments + shares) / followers × 100
    if followers_count and followers_count > 0:
        total_interactions = total_likes + total_comments + total_shares
        metrics["engagement_rate_pct"] = round(
            total_interactions / n / followers_count * 100, 3
        )
        metrics["followers_count"] = followers_count

    # Top post by likes
    posts_with_likes = [p for p in posts if p.get("likes") is not None]
    if posts_with_likes:
        top = max(posts_with_likes, key=lambda p: p["likes"])
        metrics["top_post_by_likes"] = {
            "text": (top.get("text") or "")[:200],
            "likes": top["likes"],
            "comments": top.get("comments"),
            "shares": top.get("shares"),
            "is_video": top.get("is_video"),
            "date": top.get("date"),
        }

    # Video vs photo breakdown
    video_posts = [p for p in posts if p.get("is_video")]
    metrics["video_post_count"] = len(video_posts)
    metrics["photo_post_count"] = n - len(video_posts)
    if video_posts and (n - len(video_posts)) > 0:
        avg_likes_video = sum(p.get("likes") or 0 for p in video_posts) / len(
            video_posts
        )
        avg_likes_photo = sum(
            p.get("likes") or 0 for p in posts if not p.get("is_video")
        ) / (n - len(video_posts))
        metrics["avg_likes_video"] = round(avg_likes_video, 1)
        metrics["avg_likes_photo"] = round(avg_likes_photo, 1)

    return metrics


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
            result = await fetch_social_posts(
                url, limit=limit_per_url, apify_token=apify_token
            )
            results.append(result)
        except Exception as e:
            logger.error(f"[Apify] Failed for {url}: {e}")
            results.append(
                {
                    "platform": "unknown",
                    "url": url,
                    "posts": [],
                    "posts_count": 0,
                    "_error": str(e),
                }
            )
    return results
