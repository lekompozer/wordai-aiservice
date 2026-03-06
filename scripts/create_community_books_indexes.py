"""
Create MongoDB Indexes for Community Books Performance
Run this script once to create necessary indexes
"""

from src.database.db_manager import DBManager


def create_indexes():
    """Create MongoDB indexes for community books queries"""
    db_manager = DBManager()
    db = db_manager.db

    print("📊 Creating MongoDB indexes for community books...")

    # 1. Index on community_config.category (for child category queries)
    db.online_books.create_index(
        [("community_config.category", 1)], name="idx_community_category"
    )
    print("✅ Created index: community_config.category")

    # 2. Index on community_config.parent_category (for parent category queries)
    db.online_books.create_index(
        [("community_config.parent_category", 1)], name="idx_community_parent_category"
    )
    print("✅ Created index: community_config.parent_category")

    # 3. Compound index for public books with category
    db.online_books.create_index(
        [
            ("community_config.category", 1),
            ("community_config.is_public", 1),
            ("deleted_at", 1),
        ],
        name="idx_community_public_books",
    )
    print("✅ Created compound index: category + is_public + deleted_at")

    # 4. Compound index for sorting by views
    db.online_books.create_index(
        [
            ("community_config.category", 1),
            ("community_config.total_views", -1),
        ],
        name="idx_community_category_views",
    )
    print("✅ Created compound index: category + total_views (for top books)")

    # 5. Compound index for sorting by rating
    db.online_books.create_index(
        [
            ("community_config.category", 1),
            ("community_config.average_rating", -1),
        ],
        name="idx_community_category_rating",
    )
    print("✅ Created compound index: category + average_rating")

    # 6. Compound index for sorting by published date
    db.online_books.create_index(
        [
            ("community_config.category", 1),
            ("community_config.published_at", -1),
        ],
        name="idx_community_category_published",
    )
    print("✅ Created compound index: category + published_at (for newest)")

    # List all indexes
    print("\n📋 All indexes on online_books collection:")
    indexes = db.online_books.list_indexes()
    for idx in indexes:
        print(f"   - {idx['name']}: {idx.get('key', {})}")

    print("\n✅ All indexes created successfully!")


if __name__ == "__main__":
    create_indexes()
