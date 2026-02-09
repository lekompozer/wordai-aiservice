"""
Redis Cache Client for Community Books
Handles caching for book categories, trending books, featured authors, etc.
"""

import json
import logging
import os
from typing import Optional, Any, Dict, List
import redis.asyncio as redis
from redis.asyncio import Redis

logger = logging.getLogger("chatbot")


class RedisCacheClient:
    """
    Async Redis client for community books caching

    Usage:
        cache = RedisCacheClient()
        await cache.connect()

        # Set cache
        await cache.set("books:trending:today", data, ttl=900)

        # Get cache
        data = await cache.get("books:trending:today")

        # Delete cache
        await cache.delete("books:newest:all")
    """

    def __init__(self):
        self.client: Optional[Redis] = None
        self._connected = False

        # Get Redis URL from environment
        self.redis_url = os.getenv(
            "REDIS_CACHE_URL", "redis://redis-community-book:6379/0"
        )

        logger.info(f"🔧 Redis Cache URL: {self.redis_url}")

    async def connect(self):
        """Connect to Redis cache server"""
        if self._connected and self.client:
            return

        try:
            self.client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

            # Test connection
            await self.client.ping()
            self._connected = True
            logger.info("✅ Redis cache client connected successfully")

        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis cache: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("🔌 Redis cache client disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Parsed JSON data or None if not found
        """
        if not self._connected:
            await self.connect()

        try:
            value = await self.client.get(key)
            if value:
                logger.debug(f"✅ Cache HIT: {key}")
                return json.loads(value)
            else:
                logger.debug(f"❌ Cache MISS: {key}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 600) -> bool:
        """
        Set value in cache with TTL

        Args:
            key: Cache key
            value: Data to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 10 minutes)

        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            json_value = json.dumps(value, default=str)  # default=str handles datetime
            await self.client.setex(key, ttl, json_value)
            logger.debug(f"💾 Cache SET: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key to delete

        Returns:
            True if deleted, False otherwise
        """
        if not self._connected:
            await self.connect()

        try:
            result = await self.client.delete(key)
            if result:
                logger.debug(f"🗑️ Cache DELETE: {key}")
            return bool(result)

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern

        Args:
            pattern: Redis pattern (e.g. "books:search:*")

        Returns:
            Number of keys deleted
        """
        if not self._connected:
            await self.connect()

        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f"🗑️ Deleted {deleted} keys matching: {pattern}")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Error deleting pattern {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self._connected:
            await self.connect()

        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking key existence {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key (in seconds)"""
        if not self._connected:
            await self.connect()

        try:
            return await self.client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for {key}: {e}")
            return -2  # Key doesn't exist

    async def get_info(self) -> Dict[str, Any]:
        """Get Redis server info (memory usage, keys count, etc.)"""
        if not self._connected:
            await self.connect()

        try:
            info = await self.client.info()
            return {
                "used_memory": info.get("used_memory_human"),
                "used_memory_peak": info.get("used_memory_peak_human"),
                "total_keys": await self.client.dbsize(),
                "connected_clients": info.get("connected_clients"),
                "uptime_days": info.get("uptime_in_days"),
            }
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            return {}

    async def flush_all(self):
        """⚠️ DANGER: Clear ALL cache keys. Use only for debugging!"""
        if not self._connected:
            await self.connect()

        try:
            await self.client.flushdb()
            logger.warning("⚠️ ALL CACHE CLEARED!")
        except Exception as e:
            logger.error(f"Error flushing cache: {e}")


# Global cache client instance
_cache_client: Optional[RedisCacheClient] = None


def get_cache_client() -> RedisCacheClient:
    """
    Get or create global cache client instance

    Usage:
        cache = get_cache_client()
        await cache.connect()
        data = await cache.get("key")
    """
    global _cache_client
    if _cache_client is None:
        _cache_client = RedisCacheClient()
    return _cache_client
