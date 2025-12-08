"""
Fix chapter slug unique index
Drop old index (guide_id, slug) and create new index (book_id, slug)
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()


def fix_chapter_slug_index():
    """Fix chapter slug unique index from (guide_id, slug) to (book_id, slug)"""

    # Try MONGODB_URI_AUTH first (production), then fallback
    mongo_uri = os.getenv("MONGODB_URI_AUTH") or os.getenv("MONGODB_URI")

    if not mongo_uri:
        # Build from individual params
        mongo_host = os.getenv("MONGODB_HOST", "mongodb")
        mongo_port = int(os.getenv("MONGODB_PORT", "27017"))
        mongo_user = os.getenv("MONGODB_APP_USERNAME", "ai_service_user")
        mongo_password = os.getenv("MONGODB_APP_PASSWORD")
        mongo_db = os.getenv("MONGODB_NAME", "ai_service_db")

        if not mongo_password:
            print("❌ MongoDB password not found in environment")
            print("Tried: MONGODB_URI_AUTH, MONGODB_URI, MONGODB_APP_PASSWORD")
            sys.exit(1)

        mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource=admin"

    print(f"🔌 Connecting to MongoDB...")
    client = MongoClient(mongo_uri)

    # Get database name from URI or env
    db_name = os.getenv("MONGODB_NAME", "ai_service_db")
    db = client[db_name]
    chapters = db["book_chapters"]

    print("🔍 Checking existing indexes...")
    existing_indexes = chapters.index_information()
    print(f"Found {len(existing_indexes)} indexes:")
    for idx_name, idx_info in existing_indexes.items():
        print(f"  - {idx_name}: {idx_info.get('key', [])}")

    # Drop old index if exists
    if "chapter_slug_unique" in existing_indexes:
        old_keys = existing_indexes["chapter_slug_unique"].get("key", [])
        print(f"\n🗑️  Found old index 'chapter_slug_unique' with keys: {old_keys}")

        # Check if it's the wrong index (guide_id, slug)
        if old_keys == [("guide_id", 1), ("slug", 1)]:
            print("⚠️  This is the WRONG index (guide_id, slug)")
            print("🗑️  Dropping old index...")
            chapters.drop_index("chapter_slug_unique")
            print("✅ Old index dropped")
        elif old_keys == [("book_id", 1), ("slug", 1)]:
            print("✅ Index is already correct (book_id, slug)")
            print("No changes needed!")
            return
        else:
            print(f"⚠️  Unexpected index keys: {old_keys}")
            print("🗑️  Dropping anyway to be safe...")
            chapters.drop_index("chapter_slug_unique")
            print("✅ Index dropped")
    else:
        print("\n⚠️  Index 'chapter_slug_unique' not found")

    # Create new correct index
    print("\n🔨 Creating new index (book_id, slug)...")
    chapters.create_index(
        [("book_id", 1), ("slug", 1)],
        unique=True,
        name="chapter_slug_unique",
    )
    print("✅ New index created successfully")

    # Verify
    print("\n🔍 Verifying new indexes...")
    new_indexes = chapters.index_information()
    if "chapter_slug_unique" in new_indexes:
        new_keys = new_indexes["chapter_slug_unique"].get("key", [])
        print(f"✅ Index 'chapter_slug_unique': {new_keys}")

        if new_keys == [("book_id", 1), ("slug", 1)]:
            print("✅✅ Index is correct!")
        else:
            print(f"❌ Index keys are wrong: {new_keys}")
    else:
        print("❌ Index not found after creation!")

    # Check for duplicate slugs within the same book
    print("\n🔍 Checking for duplicate slugs within same book...")
    pipeline = [
        {
            "$group": {
                "_id": {"book_id": "$book_id", "slug": "$slug"},
                "count": {"$sum": 1},
                "chapter_ids": {"$push": "$chapter_id"},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]

    duplicates = list(chapters.aggregate(pipeline))
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} duplicate slug(s) within same book:")
        for dup in duplicates:
            print(
                f"   - book_id: {dup['_id']['book_id']}, slug: {dup['_id']['slug']}, count: {dup['count']}"
            )
            print(f"     chapter_ids: {dup['chapter_ids']}")
        print(
            "\n⚠️  You need to manually fix these duplicates before the index can work properly"
        )
    else:
        print("✅ No duplicate slugs found within same book")

    print("\n✅ Migration completed!")


if __name__ == "__main__":
    try:
        fix_chapter_slug_index()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
