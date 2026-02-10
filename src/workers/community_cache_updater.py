"""
Background Worker: Community Books Cache Updater
Updates community books cache periodically (every 8 minutes)

This worker pre-computes expensive database queries and stores them in Redis:
- Category tree with book counts (10 min TTL) → needs refresh every 8 min
- Top 5 books per parent category (30 min TTL, 11 caches)
- Trending today (15 min TTL) → needs refresh every 8 min
- Featured week (30 min TTL)
- Featured authors (30 min TTL)
- Popular tags (30 min TTL)

Worker runs every 8 minutes to ensure cache never expires before refresh.
"""

import asyncio
import logging
from datetime import datetime

from src.cache.cache_warmup import (
    warmup_category_tree,
    warmup_top_books_per_category,
    warmup_trending_today,
    warmup_featured_week,
    warmup_featured_authors,
    warmup_popular_tags,
)

logger = logging.getLogger("chatbot")


async def update_community_cache():
    """
    Update all community books caches
    Runs every 8 minutes (less than shortest TTL of 10 min)
    """
    logger.info("🔄 [Community Cache Updater] Starting cache update...")
    start_time = datetime.now()

    try:
        # Update all caches in parallel for faster execution
        await asyncio.gather(
            warmup_category_tree(),  # 10 min TTL
            warmup_top_books_per_category(),  # 30 min TTL (11 parent categories)
            warmup_trending_today(),  # 15 min TTL
            warmup_featured_week(),  # 30 min TTL
            warmup_featured_authors(),  # 30 min TTL
            warmup_popular_tags(),  # 30 min TTL
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"✅ [Community Cache Updater] All caches updated successfully in {elapsed:.2f}s"
        )

    except Exception as e:
        logger.error(f"❌ [Community Cache Updater] Failed to update cache: {e}")


async def community_cache_updater_worker():
    """
    Background worker that updates community cache every 8 minutes
    Runs more frequently than shortest TTL (10 min) to prevent cache misses
    """
    logger.info("🚀 [Community Cache Updater] Worker started (8 min interval)")

    while True:
        try:
            await update_community_cache()

            # Sleep for 8 minutes (less than shortest TTL of 10 min)
            await asyncio.sleep(480)  # 8 minutes

        except asyncio.CancelledError:
            logger.info("🛑 [Community Cache Updater] Worker stopped")
            break
        except Exception as e:
            logger.error(
                f"❌ [Community Cache Updater] Worker error (retrying in 5 min): {e}"
            )
            await asyncio.sleep(300)  # Retry after 5 minutes


if __name__ == "__main__":
    asyncio.run(community_cache_updater_worker())
