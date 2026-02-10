"""
Cache Warmup Script
Rebuilds critical caches on application startup

Run this after Docker container restart to pre-populate cache
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from src.cache.redis_client import get_cache_client
from src.database.db_manager import DBManager
from src.constants.book_categories import (
    PARENT_CATEGORIES,
    CHILD_CATEGORIES,
    get_categories_tree,
)

logger = logging.getLogger("chatbot")


async def warmup_category_tree():
    """
    Warmup: Category tree with book counts (33 child categories)
    Cache key: categories:tree:all
    TTL: 10 minutes
    """
    logger.info("🔥 Warming up: Category tree...")

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get category tree
        tree = get_categories_tree()
        categories = []
        total_books_all = 0

        for parent_id, data in tree.items():
            parent_info = data["info"]
            children_data = data["children"]

            # Count books for each child category
            children_with_counts = []
            parent_total_books = 0

            for child in children_data:
                # Count books in this child category
                count = db.online_books.count_documents(
                    {
                        "community_config.category": child["name"],
                        "community_config.is_public": True,
                        "deleted_at": None,
                    }
                )

                children_with_counts.append(
                    {
                        "name": child["name"],
                        "slug": child["slug"],
                        "parent": child["parent"],
                        "books_count": count,
                    }
                )

                parent_total_books += count

            total_books_all += parent_total_books

            categories.append(
                {
                    "id": parent_info["id"],
                    "name": parent_info["name"],
                    "name_vi": parent_info["name_vi"],
                    "icon": parent_info["icon"],
                    "order": parent_info["order"],
                    "children": children_with_counts,
                    "total_books": parent_total_books,
                }
            )

        # Sort by order
        categories.sort(key=lambda x: x["order"])

        result = {
            "categories": categories,
            "total_parents": len(PARENT_CATEGORIES),
            "total_children": len(CHILD_CATEGORIES),
            "total_books": total_books_all,
        }

        # Cache for 10 minutes
        cache = get_cache_client()
        await cache.set("categories:tree:all", result, ttl=600)

        logger.info(
            f"✅ Category tree cached: {len(categories)} parents, {total_books_all} books"
        )
        return result

    except Exception as e:
        logger.error(f"❌ Failed to warmup category tree: {e}")
        return None


async def warmup_top_books_per_category():
    """
    Warmup: Top 5 books for each parent category (11 caches)
    Cache keys: books:top:category:{parent_id}
    TTL: 30 minutes
    """
    logger.info("🔥 Warming up: Top 5 books per category...")

    try:
        db_manager = DBManager()
        db = db_manager.db
        cache = get_cache_client()

        parent_ids = [cat["id"] for cat in PARENT_CATEGORIES]
        cached_count = 0

        for parent_id in parent_ids:
            try:
                # Get child categories for this parent
                child_categories = [
                    cat["name"]
                    for cat in CHILD_CATEGORIES
                    if cat["parent"] == parent_id
                ]

                if not child_categories:
                    continue

                # Get top 5 books in these child categories
                books_cursor = (
                    db.online_books.find(
                        {
                            "community_config.category": {"$in": child_categories},
                            "community_config.is_public": True,
                            "deleted_at": None,
                        }
                    )
                    .sort("community_config.total_views", -1)
                    .limit(5)
                )

                books = []
                for book in books_cursor:
                    community_config = book.get("community_config", {})
                    access_config = book.get("access_config", {})

                    # Get author names
                    author_ids = book.get("authors", [])
                    author_names = []
                    for author_id in author_ids:
                        author = db.book_authors.find_one(
                            {"author_id": author_id.lower()}
                        )
                        if author:
                            author_names.append(author.get("name", author_id))
                        else:
                            author_names.append(author_id)

                    books.append(
                        {
                            "book_id": book["book_id"],
                            "title": book["title"],
                            "slug": book["slug"],
                            "cover_url": community_config.get("cover_image_url")
                            or book.get("cover_image_url"),
                            "authors": author_ids,
                            "author_names": author_names,
                            "child_category": community_config.get("category"),
                            "parent_category": community_config.get("parent_category"),
                            "total_views": community_config.get("total_views", 0),
                            "average_rating": community_config.get(
                                "average_rating", 0.0
                            ),
                            "access_points": {
                                "one_time": access_config.get(
                                    "one_time_view_points", 0
                                ),
                                "forever": access_config.get("forever_view_points", 0),
                            },
                            "published_at": community_config.get("published_at"),
                        }
                    )

                # Cache for 30 minutes
                cache_key = f"books:top:category:{parent_id}"

                # Get parent category name
                parent = next(
                    (cat for cat in PARENT_CATEGORIES if cat["id"] == parent_id), None
                )

                result = {
                    "books": books,
                    "category_name": parent["name_vi"] if parent else parent_id,
                    "category_type": "parent",
                    "total": len(books),
                    "skip": 0,
                    "limit": 5,
                }

                await cache.set(cache_key, result, ttl=1800)
                cached_count += 1

                logger.info(f"  ✅ {parent_id}: {len(books)} books cached")

            except Exception as e:
                logger.error(f"  ❌ Failed to cache {parent_id}: {e}")
                continue

        logger.info(
            f"✅ Cached top books for {cached_count}/{len(parent_ids)} categories"
        )
        return cached_count

    except Exception as e:
        logger.error(f"❌ Failed to warmup top books per category: {e}")
        return 0


async def warmup_trending_today():
    """
    Warmup: Trending books today (most viewed in last 24 hours)
    Cache key: books:trending:today
    TTL: 15 minutes
    """
    logger.info("🔥 Warming up: Trending books today...")

    try:
        db_manager = DBManager()
        db = db_manager.db

        # Get today's date range
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Aggregate views
        pipeline = [
            {"$match": {"viewed_at": {"$gte": today_start, "$lt": today_end}}},
            {"$group": {"_id": "$book_id", "views_today": {"$sum": 1}}},
            {"$sort": {"views_today": -1}},
            {"$limit": 5},
        ]

        top_today = list(db.book_view_sessions.aggregate(pipeline))

        books = []
        for item in top_today:
            book_id = item["_id"]
            book = db.online_books.find_one(
                {
                    "book_id": book_id,
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            )

            if book:
                community_config = book.get("community_config", {})

                # Get author info
                author_ids = book.get("authors", [])
                author_names = []
                for author_id in author_ids:
                    author = db.book_authors.find_one({"author_id": author_id.lower()})
                    if author:
                        author_names.append(author.get("name", author_id))
                    else:
                        author_names.append(author_id)

                books.append(
                    {
                        "book_id": book["book_id"],
                        "title": book["title"],
                        "slug": book["slug"],
                        "cover_url": community_config.get("cover_image_url")
                        or book.get("cover_image_url"),
                        "authors": author_ids,
                        "author_names": author_names,
                        "child_category": community_config.get("category"),
                        "parent_category": community_config.get("parent_category"),
                        "total_views": community_config.get("total_views", 0),
                        "average_rating": community_config.get("average_rating", 0.0),
                        "views_today": item["views_today"],
                    }
                )

        result = {"books": books, "total": len(books)}

        cache = get_cache_client()
        await cache.set("books:trending:today", result, ttl=900)

        logger.info(f"✅ Trending today cached: {len(books)} books")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to warmup trending today: {e}")
        return None


async def warmup_featured_week():
    """
    Warmup: Featured books of the week (3 books)
    Cache key: books:featured:week
    TTL: 30 minutes
    """
    logger.info("🔥 Warming up: Featured books (week)...")

    try:
        from src.api.community_routes import get_featured_books_week

        result = await get_featured_books_week()
        logger.info(f"✅ Featured week cached: {result.total} books")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to warmup featured week: {e}")
        return None


async def warmup_featured_authors():
    """
    Warmup: Featured authors (10 authors)
    Cache key: authors:featured
    TTL: 30 minutes
    """
    logger.info("🔥 Warming up: Featured authors...")

    try:
        from src.api.community_routes import get_featured_authors

        result = await get_featured_authors()
        logger.info(f"✅ Featured authors cached: {result.total} authors")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to warmup featured authors: {e}")
        return None


async def warmup_popular_tags():
    """
    Warmup: Popular tags (25 tags)
    Cache key: tags:popular
    TTL: 30 minutes
    """
    logger.info("🔥 Warming up: Popular tags...")

    try:
        from src.api.community_routes import get_popular_tags

        result = await get_popular_tags()
        logger.info(f"✅ Popular tags cached: {result.total} tags")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to warmup popular tags: {e}")
        return None


async def run_cache_warmup():
    """
    Run all cache warmup tasks
    Call this on application startup
    """
    logger.info("=" * 80)
    logger.info("🔥 CACHE WARMUP STARTED")
    logger.info("=" * 80)

    cache = get_cache_client()
    await cache.connect()

    # Warmup critical caches
    await warmup_category_tree()
    await warmup_top_books_per_category()
    await warmup_trending_today()
    await warmup_featured_week()
    await warmup_featured_authors()
    await warmup_popular_tags()

    # Show cache info
    info = await cache.get_info()
    logger.info("=" * 80)
    logger.info("📊 CACHE WARMUP COMPLETED")
    logger.info(f"  Memory used: {info.get('used_memory', 'N/A')}")
    logger.info(f"  Total keys: {info.get('total_keys', 'N/A')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    # Run warmup standalone
    asyncio.run(run_cache_warmup())
