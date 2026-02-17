"""
Create indexes for user_learning_streak collection

This collection tracks daily learning activity and streak information.

Run in Docker:
    docker exec ai-chatbot-rag python create_learning_streak_indexes.py
"""

from src.database.db_manager import DBManager
from pymongo import ASCENDING, DESCENDING


def create_learning_streak_indexes():
    """Create all indexes for user_learning_streak collection"""

    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("CREATING LEARNING STREAK INDEXES")
    print("=" * 80)
    print(f"Database: {db.name}")
    print()

    # ========================================================================
    # user_learning_streak
    # ========================================================================
    print("🔥 Creating indexes for: user_learning_streak")

    collection = db.user_learning_streak

    # Drop existing indexes (except _id)
    try:
        collection.drop_indexes()
        print("  ✓ Dropped existing indexes")
    except Exception as e:
        print(f"  ⚠ No existing indexes to drop: {e}")

    # Primary key
    collection.create_index(
        [("streak_id", ASCENDING)], unique=True, name="idx_streak_id"
    )
    print("  ✓ idx_streak_id (unique)")

    # User's streak records
    collection.create_index([("user_id", ASCENDING)], name="idx_user_id")
    print("  ✓ idx_user_id")

    # Search by date
    collection.create_index([("date", ASCENDING)], name="idx_date")
    print("  ✓ idx_date")

    # User + Date (unique: one record per user per day)
    collection.create_index(
        [("user_id", ASCENDING), ("date", ASCENDING)],
        unique=True,
        name="idx_user_date",
    )
    print("  ✓ idx_user_date (unique)")

    # Sort by date (for getting latest streak)
    collection.create_index(
        [("user_id", ASCENDING), ("date", DESCENDING)], name="idx_user_date_desc"
    )
    print("  ✓ idx_user_date_desc")

    # Activity type search (for analytics)
    collection.create_index([("activities.type", ASCENDING)], name="idx_activity_type")
    print("  ✓ idx_activity_type")

    print()
    print("=" * 80)
    print("✅ LEARNING STREAK INDEXES CREATED SUCCESSFULLY")
    print("=" * 80)
    print()


if __name__ == "__main__":
    create_learning_streak_indexes()
