"""
Marketplace Cache Service
Handles cached statistics for marketplace performance optimization
"""

import os
import json
import logging
import redis
from datetime import datetime
from typing import Dict, Optional
from src.services.online_test_utils import get_mongodb_service

logger = logging.getLogger(__name__)

# Redis client for caching
_redis_client = None


def get_redis_client():
    """Get Redis client for caching"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
        )
    return _redis_client


class MarketplaceCacheService:
    """Service for managing marketplace statistics cache"""

    CACHE_KEY = "marketplace:stats"
    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    async def get_stats(force_refresh: bool = False) -> Dict:
        """
        Get marketplace statistics (cached)

        Args:
            force_refresh: Force recompute from DB

        Returns:
            Dict with marketplace statistics
        """
        redis_client = get_redis_client()

        # Try cache first (unless force refresh)
        if not force_refresh:
            try:
                cached = redis_client.get(MarketplaceCacheService.CACHE_KEY)
                if cached:
                    logger.info("📊 Cache hit - returning cached marketplace stats")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        # Cache miss or force refresh - compute from DB
        logger.info("🔄 Cache miss - computing marketplace stats from DB")
        stats = await MarketplaceCacheService._compute_stats()

        # Cache the result
        try:
            redis_client.setex(
                MarketplaceCacheService.CACHE_KEY,
                MarketplaceCacheService.CACHE_TTL,
                json.dumps(stats, default=str),
            )
            logger.info("✅ Cached marketplace stats for 5 minutes")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

        return stats

    @staticmethod
    async def _compute_stats() -> Dict:
        """
        Compute marketplace statistics from database

        Returns:
            Dict with comprehensive marketplace statistics
        """
        mongo_service = get_mongodb_service()
        db = mongo_service.db

        # Use aggregation pipeline for efficient statistics
        stats_pipeline = [
            # Match only public tests
            {"$match": {"marketplace_config.is_public": True, "is_active": True}},
            # Facet to compute multiple stats in parallel
            {
                "$facet": {
                    # Total count
                    "total": [{"$count": "count"}],
                    # Count by category
                    "by_category": [
                        {
                            "$group": {
                                "_id": "$marketplace_config.category",
                                "count": {"$sum": 1},
                            }
                        },
                        {"$sort": {"count": -1}},
                    ],
                    # Count by language
                    "by_language": [
                        {
                            "$group": {
                                "_id": "$test_language",
                                "count": {"$sum": 1},
                            }
                        },
                        {"$sort": {"count": -1}},
                    ],
                    # Price statistics
                    "price_stats": [
                        {
                            "$group": {
                                "_id": None,
                                "avg_price": {
                                    "$avg": "$marketplace_config.price_points"
                                },
                                "min_price": {
                                    "$min": "$marketplace_config.price_points"
                                },
                                "max_price": {
                                    "$max": "$marketplace_config.price_points"
                                },
                                "total_revenue": {
                                    "$sum": "$marketplace_config.total_revenue"
                                },
                            }
                        },
                        {"$project": {"_id": 0}},
                    ],
                    # Popular tests (top 5 by purchases)
                    "popular_tests": [
                        {"$sort": {"marketplace_config.total_purchases": -1}},
                        {"$limit": 5},
                        {
                            "$project": {
                                "_id": 0,
                                "test_id": {"$toString": "$_id"},
                                "title": 1,
                                "total_purchases": "$marketplace_config.total_purchases",
                                "price_points": "$marketplace_config.price_points",
                            }
                        },
                    ],
                    # Top rated tests (top 5 by rating)
                    "top_rated": [
                        {"$match": {"marketplace_config.rating_count": {"$gte": 3}}},
                        {"$sort": {"marketplace_config.avg_rating": -1}},
                        {"$limit": 5},
                        {
                            "$project": {
                                "_id": 0,
                                "test_id": {"$toString": "$_id"},
                                "title": 1,
                                "avg_rating": "$marketplace_config.avg_rating",
                                "rating_count": "$marketplace_config.rating_count",
                                "price_points": "$marketplace_config.price_points",
                            }
                        },
                    ],
                }
            },
        ]

        try:
            result = list(db.online_tests.aggregate(stats_pipeline))

            if not result:
                return MarketplaceCacheService._empty_stats()

            data = result[0]

            # Format response
            stats = {
                "total_public_tests": (
                    data["total"][0]["count"] if data["total"] else 0
                ),
                "by_category": data.get("by_category", []),
                "by_language": data.get("by_language", []),
                "price_stats": (
                    data["price_stats"][0] if data.get("price_stats") else {}
                ),
                "popular_tests": data.get("popular_tests", []),
                "top_rated": data.get("top_rated", []),
                "cached_at": datetime.utcnow().isoformat(),
                "cache_ttl_seconds": MarketplaceCacheService.CACHE_TTL,
            }

            logger.info(
                f"📊 Computed stats: {stats['total_public_tests']} public tests"
            )
            return stats

        except Exception as e:
            logger.error(f"Error computing marketplace stats: {e}", exc_info=True)
            return MarketplaceCacheService._empty_stats()

    @staticmethod
    def _empty_stats() -> Dict:
        """Return empty stats structure"""
        return {
            "total_public_tests": 0,
            "by_category": [],
            "by_language": [],
            "price_stats": {},
            "popular_tests": [],
            "top_rated": [],
            "cached_at": datetime.utcnow().isoformat(),
            "cache_ttl_seconds": MarketplaceCacheService.CACHE_TTL,
        }

    @staticmethod
    def invalidate_cache():
        """
        Invalidate marketplace statistics cache
        Call this when test is published/unpublished/deleted
        """
        redis_client = get_redis_client()
        try:
            redis_client.delete(MarketplaceCacheService.CACHE_KEY)
            logger.info("🗑️ Invalidated marketplace stats cache")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

    @staticmethod
    async def initialize_cache():
        """
        Initialize cache with current database state
        Call this once after deployment to warm up cache
        """
        logger.info("🔥 Initializing marketplace cache with current DB state...")
        stats = await MarketplaceCacheService.get_stats(force_refresh=True)
        logger.info(f"✅ Cache initialized: {stats['total_public_tests']} public tests")
        return stats
