import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Query

from src.cache.redis_client import get_cache_client

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/community", tags=["Community Feed"])

D1_WORKER_URL = os.getenv(
    "D1_WORKER_URL", "https://db-wordai-community.hoangnguyen358888.workers.dev"
)

TTL_TRENDING = 300  # 5 minutes
TTL_TOP = 300  # 5 minutes
TTL_HOT = 600  # 10 minutes

cache_client = get_cache_client()


async def _worker_get(path: str, params: dict = {}) -> dict:
    """Proxy GET request to Cloudflare D1 Worker."""
    clean_params = {k: v for k, v in params.items() if v is not None}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{D1_WORKER_URL}{path}", params=clean_params)
        resp.raise_for_status()
        return resp.json()


async def _cached(cache_key: str, ttl: int, fetch_fn) -> dict:
    """Return cached result or fetch + cache on miss. Falls back to direct fetch on Redis error."""
    try:
        cached = await cache_client.get(cache_key)
        if cached is not None:
            return cached
        data = await fetch_fn()
        await cache_client.set(cache_key, data, ttl=ttl)
        return data
    except Exception as e:
        logger.warning(
            "Cache error for %s: %s — falling back to direct fetch", cache_key, e
        )
        return await fetch_fn()


@router.get("/posts/trending")
async def get_trending_posts(
    category: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=50),
    userId: Optional[str] = Query(None),
):
    """Trending posts (7-day window, gravity decay score). Cached 5 min for anonymous requests."""
    scope = category or "all"
    # Only cache anonymous requests (no userId)
    cache_key = f"cf:community:trending:{scope}:v1" if not userId else None
    params = {"limit": limit}
    if category:
        params["category"] = category
    if userId:
        params["userId"] = userId

    async def fetch():
        return await _worker_get("/api/posts/trending", params)

    if cache_key:
        return await _cached(cache_key, TTL_TRENDING, fetch)
    return await fetch()


@router.get("/posts/top")
async def get_top_posts(
    category: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    userId: Optional[str] = Query(None),
):
    """Top posts by total likes (all-time). Cursor pagination. Page 1 cached 5 min."""
    is_page1 = not cursor and not userId
    scope = category or "all"
    cache_key = f"cf:community:top:{scope}:v1" if is_page1 else None
    params = {"limit": limit}
    if category:
        params["category"] = category
    if cursor:
        params["cursor"] = cursor
    if userId:
        params["userId"] = userId

    async def fetch():
        return await _worker_get("/api/posts/top", params)

    if cache_key:
        return await _cached(cache_key, TTL_TOP, fetch)
    return await fetch()


@router.get("/channels/hot")
async def get_hot_channels(
    limit: int = Query(15, ge=1, le=50),
    category: Optional[str] = Query(None),
):
    """Hot channels ranked by aggregate engagement (likes*3 + comments*2 + saves*2). Cached 10 min."""
    scope = category or "all"
    cache_key = f"cf:community:hot_channels:{scope}:v1"
    params = {"limit": limit}
    if category:
        params["category"] = category

    async def fetch():
        return await _worker_get("/api/channels/hot", params)

    return await _cached(cache_key, TTL_HOT, fetch)


@router.get("/channel/{channel_id}/trending")
async def get_channel_trending(
    channel_id: str,
    limit: int = Query(30, ge=1, le=50),
    userId: Optional[str] = Query(None),
):
    """Trending posts for a specific channel (7-day window). Cached 5 min for anonymous requests."""
    cache_key = f"cf:community:channel:{channel_id}:trending:v1" if not userId else None
    params = {"limit": limit}
    if userId:
        params["userId"] = userId

    async def fetch():
        return await _worker_get(f"/api/channel/{channel_id}/trending", params)

    if cache_key:
        return await _cached(cache_key, TTL_TRENDING, fetch)
    return await fetch()


@router.get("/channel/{channel_id}/top")
async def get_channel_top(
    channel_id: str,
    limit: int = Query(30, ge=1, le=50),
    cursor: Optional[str] = Query(None),
    userId: Optional[str] = Query(None),
):
    """Top posts for a specific channel by total likes. Cursor pagination. Page 1 cached 5 min."""
    is_page1 = not cursor and not userId
    cache_key = f"cf:community:channel:{channel_id}:top:v1" if is_page1 else None
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if userId:
        params["userId"] = userId

    async def fetch():
        return await _worker_get(f"/api/channel/{channel_id}/top", params)

    if cache_key:
        return await _cached(cache_key, TTL_TOP, fetch)
    return await fetch()
