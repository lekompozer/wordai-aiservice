"""
Background Worker: Community Books Cache Updater
Updates community books cache periodically (every 30 minutes)

This worker pre-computes expensive database queries and stores them in Redis:
- Category tree with book counts (33 child categories)
- Top 5 books per parent category (11 caches)
- Trending today (5 books)
- Featured week (3 books)
- Featured authors (10 authors)
- Popular tags (25 tags)
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
    Runs every 30 minutes
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
    Background worker that updates community cache every 30 minutes
    """
    logger.info("🚀 [Community Cache Updater] Worker started (30 min interval)")

    while True:
        try:
            await update_community_cache()

            # Sleep for 30 minutes
            await asyncio.sleep(1800)  # 30 minutes

        except asyncio.CancelledError:
            logger.info("🛑 [Community Cache Updater] Worker stopped")
            break
        except Exception as e:
            logger.error(
                f"❌ [Community Cache Updater] Worker error (retrying in 5 min): {e}"
            )
            await asyncio.sleep(300)  # Retry after 5 minutes
