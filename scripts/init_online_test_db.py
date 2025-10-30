"""
Initialize MongoDB collections and indexes for Online Test System - Phase 1
Run this script to setup database schema for online tests feat    # Create TTL index (auto-delete after 7 days if not completed)
    # Check if TTL index already exists, if so, drop and recreate
    try:
        collection.create_index(
            [("last_saved_at", ASCENDING)],
            name="last_saved_at_ttl",  # Explicit name to avoid conflicts
            expireAfterSeconds=7 * 24 * 60 * 60,  # 7 days
            partialFilterExpression={"is_completed": False}
        )
        print(f"  ✅ Created TTL index on last_saved_at (7 days)")
    except Exception as e:
        # If index exists with wrong config, drop and recreate
        if "IndexKeySpecsConflict" in str(e) or "already exists" in str(e).lower():
            print(f"  ℹ️  TTL index already exists, dropping and recreating...")
            try:
                collection.drop_index("last_saved_at_1")  # Drop old index
            except:
                pass
            try:
                collection.drop_index("last_saved_at_ttl")  # Drop if exists with new name
            except:
                pass
            # Recreate
            collection.create_index(
                [("last_saved_at", ASCENDING)],
                name="last_saved_at_ttl",
                expireAfterSeconds=7 * 24 * 60 * 60,
                partialFilterExpression={"is_completed": False}
            )
            print(f"  ✅ Recreated TTL index on last_saved_at (7 days)")
        else:
            print(f"  ⚠️  Warning creating TTL index: {e}")sage:
    python scripts/init_online_test_db.py
"""

import sys
import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config.config as config


def init_online_tests_collection(db):
    """Initialize online_tests collection with indexes"""
    collection_name = "online_tests"

    print(f"🔧 Setting up collection: {collection_name}")

    # Create collection if not exists
    if collection_name not in db.list_collection_names():
        db.create_collection(collection_name)
        print(f"  ✅ Created collection: {collection_name}")
    else:
        print(f"  ℹ️  Collection already exists: {collection_name}")

    collection = db[collection_name]

    # Create indexes
    indexes = [
        # Single field indexes
        ("creator_id", ASCENDING),
        ("created_at", DESCENDING),
        ("is_active", ASCENDING),
        # Compound indexes
        (["creator_id", "created_at"], DESCENDING),
        (["is_active", "created_at"], DESCENDING),
    ]

    for index in indexes:
        if isinstance(index, tuple) and isinstance(index[0], list):
            # Compound index
            field_list = [
                (field, direction)
                for field, direction in zip(index[0], [index[1]] * len(index[0]))
            ]
            collection.create_index(field_list)
            print(f"  ✅ Created compound index: {index[0]}")
        else:
            # Single field index
            collection.create_index([(index[0], index[1])])
            print(f"  ✅ Created index on: {index[0]}")

    print(f"✅ Collection {collection_name} setup complete\n")


def init_test_submissions_collection(db):
    """Initialize test_submissions collection with indexes"""
    collection_name = "test_submissions"

    print(f"🔧 Setting up collection: {collection_name}")

    # Create collection if not exists
    if collection_name not in db.list_collection_names():
        db.create_collection(collection_name)
        print(f"  ✅ Created collection: {collection_name}")
    else:
        print(f"  ℹ️  Collection already exists: {collection_name}")

    collection = db[collection_name]

    # Create indexes
    indexes = [
        # Single field indexes
        ("test_id", ASCENDING),
        ("user_id", ASCENDING),
        ("submitted_at", DESCENDING),
        # Compound indexes for efficient queries
        (["test_id", "user_id"], ASCENDING),
        (["user_id", "submitted_at"], DESCENDING),
        (["test_id", "attempt_number"], ASCENDING),
        (["test_id", "user_id", "attempt_number"], ASCENDING),
    ]

    for index in indexes:
        if isinstance(index, tuple) and isinstance(index[0], list):
            # Compound index
            field_list = [(field, ASCENDING) for field in index[0]]
            collection.create_index(field_list)
            print(f"  ✅ Created compound index: {index[0]}")
        else:
            # Single field index
            collection.create_index([(index[0], index[1])])
            print(f"  ✅ Created index on: {index[0]}")

    print(f"✅ Collection {collection_name} setup complete\n")


def init_test_progress_collection(db):
    """Initialize test_progress collection with indexes and TTL"""
    collection_name = "test_progress"

    print(f"🔧 Setting up collection: {collection_name}")

    # Create collection if not exists
    if collection_name not in db.list_collection_names():
        db.create_collection(collection_name)
        print(f"  ✅ Created collection: {collection_name}")
    else:
        print(f"  ℹ️  Collection already exists: {collection_name}")

    collection = db[collection_name]

    # Create indexes
    indexes = [
        # Single field indexes
        ("session_id", ASCENDING),
        ("user_id", ASCENDING),
        ("test_id", ASCENDING),
        # Note: Skip last_saved_at here, will create TTL index separately
        # Compound indexes
        (["user_id", "test_id", "is_completed"], ASCENDING),
        (["test_id", "user_id"], ASCENDING),
    ]

    for index in indexes:
        if isinstance(index, tuple) and isinstance(index[0], list):
            # Compound index
            field_list = [(field, ASCENDING) for field in index[0]]
            collection.create_index(field_list)
            print(f"  ✅ Created compound index: {index[0]}")
        else:
            # Single field index
            collection.create_index([(index[0], index[1])])
            print(f"  ✅ Created index on: {index[0]}")

    # Create TTL index (auto-delete after 7 days if not completed)
    # Check if TTL index already exists, if so, drop and recreate
    try:
        # First, try to drop any existing last_saved_at indexes
        existing_indexes = collection.list_indexes()
        for idx in existing_indexes:
            if "last_saved_at" in str(idx.get("key", {})):
                try:
                    collection.drop_index(idx["name"])
                    print(f"  🗑️  Dropped existing index: {idx['name']}")
                except:
                    pass

        # Create new TTL index
        collection.create_index(
            [("last_saved_at", ASCENDING)],
            name="last_saved_at_ttl",  # Explicit name
            expireAfterSeconds=7 * 24 * 60 * 60,  # 7 days
            partialFilterExpression={"is_completed": False},
        )
        print(f"  ✅ Created TTL index on last_saved_at (7 days)")
    except Exception as e:
        print(f"  ⚠️  Warning with TTL index: {e}")

    print(f"✅ Collection {collection_name} setup complete\n")


def main():
    """Main function to initialize all collections"""
    print("=" * 60)
    print("🚀 Initializing Online Test System Database - Phase 1")
    print("=" * 60)
    print()

    # Get environment
    env = os.getenv("ENV", "production").lower()
    print(f"📌 Environment: {env}")

    # Connect to MongoDB
    try:
        # Use MONGODB_URI_AUTH for authenticated connection (production)
        # Fall back to MONGODB_URI for local development
        mongo_uri = (
            config.MONGODB_URI_AUTH
            if hasattr(config, "MONGODB_URI_AUTH")
            else config.MONGODB_URI
        )
        db_name = config.MONGODB_NAME

        print(f"🔗 Connecting to MongoDB: {mongo_uri}")
        print(f"📂 Database name: {db_name}")

        client = MongoClient(mongo_uri)
        db = client[db_name]

        # Test connection
        db.command("ping")
        print(f"✅ Connected to MongoDB database: {db_name}\n")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print(f"   Make sure MongoDB is running and connection string is correct")
        return

    # Initialize collections
    try:
        init_online_tests_collection(db)
        init_test_submissions_collection(db)
        init_test_progress_collection(db)

        print("=" * 60)
        print("✅ Database initialization complete!")
        print("=" * 60)
        print()
        print("Collections created:")
        print("  1. online_tests - Stores test definitions and questions")
        print("  2. test_submissions - Stores user submission results")
        print("  3. test_progress - Stores real-time progress (Phase 2)")
        print()
        print("Next steps:")
        print("  1. Implement test_generator_service.py")
        print("  2. Create API endpoints in online_test_routes.py")
        print("  3. Test the complete flow")
        print()

    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
