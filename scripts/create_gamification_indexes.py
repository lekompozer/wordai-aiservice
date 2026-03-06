#!/usr/bin/env python3
"""
Create indexes for gamification system collections:
- user_learning_xp
- user_learning_achievements

Production Usage:
    python create_gamification_indexes.py

Database: ai_service_db
Collections:
- user_learning_xp: Stores user XP, level, and XP history
- user_learning_achievements: Stores user earned achievements

Index Strategy:
- user_learning_xp: Query by user_id (most common), rank by total_xp/level
- user_learning_achievements: Query by user_id, sort by earned_at
"""

from src.database.db_manager import DBManager
from pymongo import ASCENDING, DESCENDING


def create_indexes():
    """Create indexes for gamification collections."""

    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("Creating indexes for gamification system collections...")
    print("=" * 80)

    # ========================================================================
    # Collection: user_learning_xp
    # ========================================================================
    print("\n[1/2] Creating indexes for 'user_learning_xp' collection...")

    xp_col = db["user_learning_xp"]

    # Index 1: user_id (unique) - Most common query
    print("  - Creating index: user_id (unique)")
    xp_col.create_index([("user_id", ASCENDING)], name="idx_user_id", unique=True)

    # Index 2: level - For leaderboard queries
    print("  - Creating index: level")
    xp_col.create_index([("level", DESCENDING)], name="idx_level")

    # Index 3: total_xp - For leaderboard rankings
    print("  - Creating index: total_xp")
    xp_col.create_index([("total_xp", DESCENDING)], name="idx_total_xp")

    # Index 4: Compound - level + total_xp (leaderboard within level)
    print("  - Creating index: level + total_xp")
    xp_col.create_index(
        [("level", DESCENDING), ("total_xp", DESCENDING)], name="idx_level_total_xp"
    )

    # Index 5: last_updated - For recent activity queries
    print("  - Creating index: last_updated")
    xp_col.create_index([("last_updated", DESCENDING)], name="idx_last_updated")

    print(f"✅ Created {5} indexes for 'user_learning_xp'")

    # ========================================================================
    # Collection: user_learning_achievements
    # ========================================================================
    print("\n[2/2] Creating indexes for 'user_learning_achievements' collection...")

    achievements_col = db["user_learning_achievements"]

    # Index 1: user_id - Most common query
    print("  - Creating index: user_id")
    achievements_col.create_index([("user_id", ASCENDING)], name="idx_user_id")

    # Index 2: Compound - user_id + earned_at (user's achievements sorted by time)
    print("  - Creating index: user_id + earned_at")
    achievements_col.create_index(
        [("user_id", ASCENDING), ("earned_at", DESCENDING)],
        name="idx_user_id_earned_at",
    )

    # Index 3: achievement_id - For checking if specific achievement earned
    print("  - Creating index: achievement_id")
    achievements_col.create_index(
        [("achievement_id", ASCENDING)], name="idx_achievement_id"
    )

    # Index 4: Compound - user_id + achievement_id (unique constraint)
    print("  - Creating index: user_id + achievement_id (unique)")
    achievements_col.create_index(
        [("user_id", ASCENDING), ("achievement_id", ASCENDING)],
        name="idx_user_achievement_unique",
        unique=True,
    )

    # Index 5: achievement_type - For querying by type
    print("  - Creating index: achievement_type")
    achievements_col.create_index(
        [("achievement_type", ASCENDING)], name="idx_achievement_type"
    )

    # Index 6: earned_at - For recent achievements queries
    print("  - Creating index: earned_at")
    achievements_col.create_index([("earned_at", DESCENDING)], name="idx_earned_at")

    print(f"✅ Created {6} indexes for 'user_learning_achievements'")

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 80)
    print("Index Creation Summary:")
    print("=" * 80)

    # List all indexes
    print("\n📋 user_learning_xp indexes:")
    for index_info in xp_col.list_indexes():
        print(f"  - {index_info['name']}: {index_info['key']}")

    print("\n📋 user_learning_achievements indexes:")
    for index_info in achievements_col.list_indexes():
        print(f"  - {index_info['name']}: {index_info['key']}")

    # Get collection stats
    xp_count = xp_col.count_documents({})
    ach_count = achievements_col.count_documents({})

    print("\n📊 Collection Statistics:")
    print(f"  - user_learning_xp: {xp_count} documents")
    print(f"  - user_learning_achievements: {ach_count} documents")

    print("\n✅ All gamification indexes created successfully!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        create_indexes()
    except Exception as e:
        print(f"\n❌ Error creating indexes: {e}")
        raise
