"""
Phase 5 Marketplace Database Setup
Creates collections, indexes, and initial data for marketplace feature

Run: python migrations/phase5_marketplace_setup.py
"""

import sys
import os
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config.config as config


def setup_marketplace_collections():
    """Create collections and indexes for Phase 5 Marketplace"""

    print("🚀 Starting Phase 5 Marketplace Database Setup...")

    # Connect to MongoDB
    mongo_uri = getattr(config, "MONGODB_URI_AUTH", None) or getattr(
        config, "MONGODB_URI", "mongodb://localhost:27017"
    )
    client = MongoClient(mongo_uri)
    db_name = getattr(config, "MONGODB_NAME", "wordai_db")
    db = client[db_name]

    print(f"✅ Connected to MongoDB: {db_name}")

    # ====================================
    # 1. Update online_tests collection
    # ====================================
    print("\n📝 Step 1: Updating online_tests collection schema...")

    # Add marketplace_config field to existing tests (default: not public)
    result = db.online_tests.update_many(
        {"marketplace_config": {"$exists": False}},
        {
            "$set": {
                "marketplace_config": {
                    "is_public": False,
                    "price_points": 0,
                    "cover_image_url": None,
                    "cover_thumbnail_url": None,
                    "description": "",
                    "short_description": "",
                    "category": "other",
                    "tags": [],
                    "difficulty_level": "beginner",
                    "current_version": "v1",
                    "total_participants": 0,
                    "total_earnings": 0,
                    "total_platform_fees": 0,
                    "marketplace_earnings_available": 0,
                    "marketplace_earnings_transferred": 0,
                    "average_rating": 0.0,
                    "rating_count": 0,
                    "average_participant_score": 0.0,
                    "completion_rate": 0.0,
                    "published_at": None,
                    "last_updated": datetime.now(timezone.utc),
                }
            }
        },
    )
    print(
        f"   ✅ Updated {result.modified_count} existing tests with marketplace_config"
    )

    # Create indexes for marketplace queries
    print("\n   Creating indexes for online_tests...")

    indexes = [
        ({"marketplace_config.is_public": 1}, "marketplace_is_public"),
        ({"marketplace_config.category": 1}, "marketplace_category"),
        ({"marketplace_config.price_points": 1}, "marketplace_price"),
        ({"marketplace_config.average_rating": -1}, "marketplace_rating_desc"),
        (
            {"marketplace_config.total_participants": -1},
            "marketplace_participants_desc",
        ),
        ({"marketplace_config.published_at": -1}, "marketplace_published_desc"),
        ([("marketplace_config.tags", TEXT)], "marketplace_tags_text"),
        (
            {"marketplace_config.is_public": 1, "marketplace_config.category": 1},
            "marketplace_public_category",
        ),
        ({"creator_id": 1, "marketplace_config.is_public": 1}, "creator_public_tests"),
    ]

    for index_keys, index_name in indexes:
        try:
            if isinstance(index_keys, list):
                db.online_tests.create_index(index_keys, name=index_name)
            else:
                db.online_tests.create_index(
                    [(k, v) for k, v in index_keys.items()], name=index_name
                )
            print(f"      ✅ Created index: {index_name}")
        except Exception as e:
            print(f"      ⚠️  Index {index_name} already exists or error: {e}")

    # ====================================
    # 2. Create test_versions collection
    # ====================================
    print("\n📝 Step 2: Creating test_versions collection...")

    if "test_versions" not in db.list_collection_names():
        db.create_collection("test_versions")
        print("   ✅ Created test_versions collection")
    else:
        print("   ⚠️  test_versions collection already exists")

    # Create indexes for test_versions
    print("   Creating indexes for test_versions...")

    version_indexes = [
        ({"test_id": 1, "version": 1}, "test_version_unique"),
        ({"test_id": 1, "created_at": -1}, "test_versions_by_date"),
        ({"test_id": 1, "is_current": 1}, "test_current_version"),
    ]

    for index_keys, index_name in version_indexes:
        try:
            if index_name == "test_version_unique":
                db.test_versions.create_index(
                    [(k, v) for k, v in index_keys.items()],
                    name=index_name,
                    unique=True,
                )
            else:
                db.test_versions.create_index(
                    [(k, v) for k, v in index_keys.items()], name=index_name
                )
            print(f"      ✅ Created index: {index_name}")
        except Exception as e:
            print(f"      ⚠️  Index {index_name} already exists or error: {e}")

    # ====================================
    # 3. Create test_ratings collection
    # ====================================
    print("\n📝 Step 3: Creating test_ratings collection...")

    if "test_ratings" not in db.list_collection_names():
        db.create_collection("test_ratings")
        print("   ✅ Created test_ratings collection")
    else:
        print("   ⚠️  test_ratings collection already exists")

    # Create indexes for test_ratings
    print("   Creating indexes for test_ratings...")

    rating_indexes = [
        ({"rating_id": 1}, "rating_id_unique"),
        ({"test_id": 1, "user_id": 1}, "test_user_rating_unique"),
        ({"test_id": 1, "created_at": -1}, "test_ratings_by_date"),
        ({"user_id": 1, "created_at": -1}, "user_ratings_by_date"),
        ({"test_id": 1, "rating": -1}, "test_ratings_by_score"),
    ]

    for index_keys, index_name in rating_indexes:
        try:
            if "unique" in index_name:
                db.test_ratings.create_index(
                    [(k, v) for k, v in index_keys.items()],
                    name=index_name,
                    unique=True,
                )
            else:
                db.test_ratings.create_index(
                    [(k, v) for k, v in index_keys.items()], name=index_name
                )
            print(f"      ✅ Created index: {index_name}")
        except Exception as e:
            print(f"      ⚠️  Index {index_name} already exists or error: {e}")

    # ====================================
    # 4. Create test_purchases collection
    # ====================================
    print("\n📝 Step 4: Creating test_purchases collection...")

    if "test_purchases" not in db.list_collection_names():
        db.create_collection("test_purchases")
        print("   ✅ Created test_purchases collection")
    else:
        print("   ⚠️  test_purchases collection already exists")

    # Create indexes for test_purchases
    print("   Creating indexes for test_purchases...")

    purchase_indexes = [
        ({"purchase_id": 1}, "purchase_id_unique"),
        ({"test_id": 1, "buyer_id": 1}, "test_buyer_purchase_unique"),
        ({"buyer_id": 1, "purchased_at": -1}, "buyer_purchases_by_date"),
        ({"creator_id": 1, "purchased_at": -1}, "creator_sales_by_date"),
        ({"test_id": 1, "purchased_at": -1}, "test_purchases_by_date"),
    ]

    for index_keys, index_name in purchase_indexes:
        try:
            if "unique" in index_name:
                db.test_purchases.create_index(
                    [(k, v) for k, v in index_keys.items()],
                    name=index_name,
                    unique=True,
                )
            else:
                db.test_purchases.create_index(
                    [(k, v) for k, v in index_keys.items()], name=index_name
                )
            print(f"      ✅ Created index: {index_name}")
        except Exception as e:
            print(f"      ⚠️  Index {index_name} already exists or error: {e}")

    # ====================================
    # 5. Create user_points collection
    # ====================================
    print("\n📝 Step 5: Creating/Updating user_points collection...")

    if "user_points" not in db.list_collection_names():
        db.create_collection("user_points")
        print("   ✅ Created user_points collection")
    else:
        print("   ⚠️  user_points collection already exists")

    # Add marketplace_earnings field to existing users
    result = db.user_points.update_many(
        {"marketplace_earnings": {"$exists": False}},
        {
            "$set": {
                "marketplace_earnings": {
                    "available": 0,
                    "transferred": 0,
                    "total_lifetime": 0,
                }
            }
        },
    )
    print(f"   ✅ Updated {result.modified_count} users with marketplace_earnings")

    # Create indexes for user_points
    print("   Creating indexes for user_points...")

    try:
        db.user_points.create_index(
            [("user_id", ASCENDING)], name="user_id_unique", unique=True
        )
        print(f"      ✅ Created index: user_id_unique")
    except Exception as e:
        print(f"      ⚠️  Index user_id_unique already exists or error: {e}")

    # ====================================
    # 6. Create point_transactions collection
    # ====================================
    print("\n📝 Step 6: Creating/Updating point_transactions collection...")

    if "point_transactions" not in db.list_collection_names():
        db.create_collection("point_transactions")
        print("   ✅ Created point_transactions collection")
    else:
        print("   ⚠️  point_transactions collection already exists")

    # Create indexes for point_transactions
    print("   Creating indexes for point_transactions...")

    transaction_indexes = [
        ({"transaction_id": 1}, "transaction_id_unique"),
        ({"user_id": 1, "created_at": -1}, "user_transactions_by_date"),
        ({"type": 1, "created_at": -1}, "transactions_by_type_date"),
        ({"reference_type": 1, "reference_id": 1}, "transaction_reference"),
    ]

    for index_keys, index_name in transaction_indexes:
        try:
            if "unique" in index_name:
                db.point_transactions.create_index(
                    [(k, v) for k, v in index_keys.items()],
                    name=index_name,
                    unique=True,
                )
            else:
                db.point_transactions.create_index(
                    [(k, v) for k, v in index_keys.items()], name=index_name
                )
            print(f"      ✅ Created index: {index_name}")
        except Exception as e:
            print(f"      ⚠️  Index {index_name} already exists or error: {e}")

    # ====================================
    # Summary
    # ====================================
    print("\n" + "=" * 60)
    print("✅ Phase 5 Marketplace Database Setup Complete!")
    print("=" * 60)
    print("\nCollections created/updated:")
    print("  1. ✅ online_tests (marketplace_config added)")
    print("  2. ✅ test_versions (NEW)")
    print("  3. ✅ test_ratings (NEW)")
    print("  4. ✅ test_purchases (NEW)")
    print("  5. ✅ user_points (marketplace_earnings added)")
    print("  6. ✅ point_transactions (indexes added)")

    print("\n📊 Collection Statistics:")
    for collection_name in [
        "online_tests",
        "test_versions",
        "test_ratings",
        "test_purchases",
        "user_points",
        "point_transactions",
    ]:
        if collection_name in db.list_collection_names():
            count = db[collection_name].count_documents({})
            print(f"  - {collection_name}: {count} documents")

    print("\n🎉 Ready to implement marketplace features!")

    client.close()


if __name__ == "__main__":
    try:
        setup_marketplace_collections()
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
