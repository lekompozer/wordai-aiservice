"""
Rate Limiter Middleware for AI Endpoints
Protects expensive API calls (Claude, Gemini, AI Image generation)
"""

import time
from typing import Optional, Union
from datetime import datetime, timedelta
from fastapi import HTTPException
from redis import Redis
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter for API endpoints"""

    def __init__(self, redis_client: Union[Redis, aioredis.Redis]):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        user_id: str,
        action: str,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        """
        Check if user has exceeded rate limit

        Args:
            user_id: User ID
            action: Action type (e.g., 'subtitle_generation', 'translation')
            max_requests: Maximum allowed requests in window
            window_seconds: Time window in seconds

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        key = f"rate_limit:{action}:{user_id}"
        current_time = int(time.time())
        window_start = current_time - window_seconds

        try:
            # Remove old entries outside time window
            self.redis.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            request_count = self.redis.zcard(key)

            if request_count >= max_requests:
                # Get oldest request time to calculate wait time
                oldest = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_timestamp = oldest[0][1]
                    wait_seconds = int(oldest_timestamp + window_seconds - current_time)

                    logger.warning(
                        f"⚠️ Rate limit exceeded for {user_id} on {action}: "
                        f"{request_count}/{max_requests} requests in {window_seconds}s"
                    )

                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "Rate limit exceeded",
                            "action": action,
                            "limit": f"{max_requests} requests per {window_seconds} seconds",
                            "current_usage": request_count,
                            "retry_after": wait_seconds,
                            "message": f"Please wait {wait_seconds} seconds before trying again",
                        },
                    )

            # Add current request
            self.redis.zadd(key, {str(current_time): current_time})

            # Set expiry on the key
            self.redis.expire(key, window_seconds)

            logger.info(
                f"✅ Rate limit OK for {user_id} on {action}: "
                f"{request_count + 1}/{max_requests} requests"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Rate limiter error: {e}")
            # Fail open - allow request if Redis is down
            logger.warning("⚠️ Rate limiter bypassed due to error")


# Rate limit configurations for different actions
RATE_LIMITS = {
    # AI Generation (Expensive)
    "subtitle_generation": {"max_requests": 20, "window_seconds": 3600},  # 20/hour
    "audio_generation": {"max_requests": 15, "window_seconds": 3600},  # 15/hour
    "test_generation": {"max_requests": 10, "window_seconds": 3600},  # 10/hour
    "ai_image_generation": {"max_requests": 30, "window_seconds": 3600},  # 30/hour
    "quote_generation": {"max_requests": 50, "window_seconds": 3600},  # 50/hour
    # AI Editing/Formatting (Moderate cost)
    "ai_edit": {"max_requests": 30, "window_seconds": 3600},  # 30/hour
    "ai_format": {"max_requests": 30, "window_seconds": 3600},  # 30/hour
    "chapter_translation": {"max_requests": 20, "window_seconds": 3600},  # 20/hour
    "test_translation": {"max_requests": 10, "window_seconds": 3600},  # 10/hour
    # Document operations
    "document_export": {"max_requests": 20, "window_seconds": 1800},  # 20/30min
    "video_export": {
        "max_requests": 5,
        "window_seconds": 180,
    },  # 5/3min (already exists)
    # Slide AI generation
    "slide_ai_batch": {"max_requests": 10, "window_seconds": 3600},  # 10/hour
    "slide_ai_single": {"max_requests": 50, "window_seconds": 3600},  # 50/hour
    # Lyria Music Generation (Expensive - Vertex AI)
    "lyria_music_generation": {"max_requests": 10, "window_seconds": 60},  # 10/min
}


async def check_ai_rate_limit(
    user_id: str,
    action: str,
) -> None:
    """
    Helper function to check rate limit for AI actions

    Args:
        user_id: User ID
        action: Action key from RATE_LIMITS
    """
    if action not in RATE_LIMITS:
        logger.warning(f"⚠️ Unknown rate limit action: {action}")
        return

    config = RATE_LIMITS[action]

    # Create standalone Redis connection
    from config.config import REDIS_URL

    redis_client = await aioredis.from_url(REDIS_URL, decode_responses=True)

    try:
        limiter = RateLimiter(redis_client)
        await limiter.check_rate_limit(
            user_id=user_id,
            action=action,
            max_requests=config["max_requests"],
            window_seconds=config["window_seconds"],
        )
    finally:
        # Close connection
        await redis_client.close()
