"""
Migration Script: Remove invitation_token unique index from test_shares collection

This script removes the unique constraint on invitation_token field because:
- Auto-accept flow doesn't need invitation tokens
- Multiple shares with null invitation_token caused duplicate key errors

CAUTION: This will drop and recreate the test_shares collection!
All existing shares will be DELETED!

Usage:
    python scripts/migrate_test_shares_remove_token_index.py

Author: GitHub Copilot
Date: 04/11/2025
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def migrate_test_shares():
    """Drop and recreate test_shares collection without invitation_token unique index"""

    # MongoDB connection
    MONGO_URI = os.getenv(
        "MONGODB_URI_AUTH",
        os.getenv("MONGO_URI", "mongodb://mongodb:27017"),
    )
    DB_NAME = os.getenv("MONGO_DB_NAME", os.getenv("MONGODB_NAME", "ai_service_db"))

    print(f"🔗 Connecting to MongoDB: {MONGO_URI}")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    collection_name = "test_shares"
    collection = db[collection_name]

    # Check if collection exists and count documents
    if collection_name in db.list_collection_names():
        doc_count = collection.count_documents({})
        print(
            f"\n⚠️  WARNING: Collection '{collection_name}' exists with {doc_count} documents"
        )

        if doc_count > 0:
            print(f"⚠️  This operation will DELETE all {doc_count} existing shares!")
            print(f"⚠️  Press Ctrl+C within 5 seconds to cancel...")
            import time

            time.sleep(5)

        # Drop the collection
        print(f"\n🗑️  Dropping collection: {collection_name}")
        db.drop_collection(collection_name)
        print(f"✅ Collection dropped")
    else:
        print(f"\nℹ️  Collection '{collection_name}' does not exist yet")

    # Recreate collection
    print(f"\n📦 Creating collection: {collection_name}")
    db.create_collection(collection_name)
    collection = db[collection_name]
    print(f"✅ Collection created")

    print("\n📊 Creating indexes for test_shares collection...")

    # Index 1: Lookup shares by test_id (owner dashboard)
    collection.create_index([("test_id", ASCENDING)], name="idx_test_id")
    print("✅ Created index: idx_test_id")

    # Index 2: Lookup shares by sharee email
    collection.create_index([("sharee_email", ASCENDING)], name="idx_sharee_email")
    print("✅ Created index: idx_sharee_email")

    # Index 3: Lookup shares by sharee_id (user's invitations)
    collection.create_index([("sharee_id", ASCENDING)], name="idx_sharee_id")
    print("✅ Created index: idx_sharee_id")

    # Index 4: Filter by sharee + status
    collection.create_index(
        [("sharee_id", ASCENDING), ("status", ASCENDING)], name="idx_sharee_status"
    )
    print("✅ Created index: idx_sharee_status")

    # Index 5: Query by status (for cron job and filtering)
    collection.create_index(
        [("status", ASCENDING), ("deadline", ASCENDING)], name="idx_status_deadline"
    )
    print("✅ Created index: idx_status_deadline")

    # Index 6: Compound index for deadline expiration cron job
    collection.create_index(
        [("status", ASCENDING), ("deadline", ASCENDING)],
        name="idx_deadline_expiration",
        partialFilterExpression={"status": "accepted", "deadline": {"$exists": True}},
    )
    print("✅ Created index: idx_deadline_expiration (partial)")

    # Index 7: Compound index for test + sharee (access validation)
    collection.create_index(
        [("test_id", ASCENDING), ("sharee_id", ASCENDING), ("status", ASCENDING)],
        name="idx_test_sharee_status",
    )
    print("✅ Created index: idx_test_sharee_status")

    # Index 8: TTL index for old declined/expired shares (cleanup after 90 days)
    collection.create_index(
        [("created_at", ASCENDING)],
        expireAfterSeconds=90 * 24 * 60 * 60,  # 90 days
        name="idx_ttl_cleanup",
        partialFilterExpression={"status": {"$in": ["declined", "expired"]}},
    )
    print("✅ Created index: idx_ttl_cleanup (TTL 90 days)")

    # Index 9: Compound unique index to prevent duplicate shares
    collection.create_index(
        [("test_id", ASCENDING), ("sharee_email", ASCENDING)],
        unique=True,
        name="idx_test_sharee_unique",
        partialFilterExpression={"status": {"$nin": ["declined", "expired"]}},
    )
    print("✅ Created index: idx_test_sharee_unique (prevents duplicate active shares)")

    # ❌ REMOVED: idx_invitation_token_unique (caused duplicate key error with null values)
    print(
        "\n⚠️  Note: invitation_token unique index removed (auto-accept flow doesn't need it)"
    )

    # List all indexes
    print("\n📋 Current indexes:")
    for idx in collection.list_indexes():
        print(f"   - {idx['name']}: {idx.get('key', {})}")
        if idx.get("unique"):
            print(f"     ✓ Unique constraint")
        if idx.get("partialFilterExpression"):
            print(f"     ✓ Partial: {idx['partialFilterExpression']}")
        if idx.get("expireAfterSeconds"):
            print(f"     ✓ TTL: {idx['expireAfterSeconds']}s")

    print(f"\n✅ Migration completed successfully!")
    print(f"\n📝 Summary:")
    print(f"   - Dropped old test_shares collection")
    print(f"   - Created new collection with 9 indexes")
    print(f"   - Removed invitation_token unique constraint")
    print(f"   - Auto-accept flow can now create shares without tokens")

    client.close()


if __name__ == "__main__":
    print("=" * 70)
    print("🔧 Test Shares Collection Migration")
    print("=" * 70)
    print()
    print("This script will:")
    print("  1. Drop the existing test_shares collection (if exists)")
    print("  2. Recreate it with updated indexes")
    print("  3. Remove invitation_token unique constraint")
    print()

    try:
        migrate_test_shares()
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
