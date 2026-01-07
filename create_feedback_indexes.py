"""
Create indexes for user_feedback collection
Run this script to optimize feedback queries
"""

import asyncio
from src.database.db_manager import DBManager


async def create_feedback_indexes():
    """Create indexes for user_feedback collection"""
    print("🔧 Creating indexes for user_feedback collection...")

    db_manager = DBManager()
    collection = db_manager.db.user_feedback

    # Index for checking user's share status (used frequently)
    await collection.create_index(
        [("user_id", 1), ("shared_at", -1)],
        name="user_share_lookup",
        background=True,
    )

    # Index for share date filtering (one share per day limit)
    await collection.create_index(
        [("user_id", 1), ("share_date", 1)],
        name="user_share_date",
        background=True,
    )

    # Index for analytics - rating distribution
    await collection.create_index(
        [("rating", 1), ("created_at", -1)],
        name="rating_analytics",
        background=True,
    )

    # Index for platform analytics
    await collection.create_index(
        [("shared_platform", 1), ("created_at", -1)],
        name="platform_analytics",
        background=True,
    )

    # TTL index - auto-delete old feedback after 2 years (optional)
    # await collection.create_index(
    #     [("created_at", 1)],
    #     name="feedback_ttl",
    #     expireAfterSeconds=63072000,  # 2 years
    #     background=True,
    # )

    # List all indexes
    indexes = await collection.list_indexes().to_list(length=None)
    print("\n✅ Indexes created successfully:")
    for idx in indexes:
        print(f"  - {idx['name']}: {idx.get('key', {})}")


if __name__ == "__main__":
    asyncio.run(create_feedback_indexes())
