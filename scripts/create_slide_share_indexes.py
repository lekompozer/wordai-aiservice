"""
MongoDB Indexes for Slide Sharing Feature

Run this script to create indexes for optimal query performance
"""

from src.database.db_manager import DBManager


def create_slide_share_indexes():
    """Create indexes for slide_shares collection"""
    db_manager = DBManager()
    collection = db_manager.db.slide_shares

    print("📊 Creating indexes for slide_shares collection...")

    # Index for finding shares by share_id (primary lookup)
    collection.create_index("share_id", unique=True)
    print("  ✅ Created index: share_id (unique)")

    # Index for finding user's shares
    collection.create_index([("owner_id", 1), ("created_at", -1)])
    print("  ✅ Created index: owner_id + created_at")

    # Index for finding shares by document_id
    collection.create_index("document_id")
    print("  ✅ Created index: document_id")

    # Index for finding active shares
    collection.create_index([("is_active", 1), ("revoked", 1), ("expires_at", 1)])
    print("  ✅ Created index: is_active + revoked + expires_at")

    # Index for analytics queries
    collection.create_index("view_count")
    print("  ✅ Created index: view_count")

    # Compound index for owner's active shares
    collection.create_index(
        [("owner_id", 1), ("is_active", 1), ("revoked", 1)], name="owner_active_shares"
    )
    print("  ✅ Created index: owner_active_shares")

    print("✅ All indexes created successfully!")


if __name__ == "__main__":
    create_slide_share_indexes()
