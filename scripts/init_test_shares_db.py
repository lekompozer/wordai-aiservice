"""
Database Initialization Script for Online Test Sharing System - Phase 4

This script creates the test_shares collection with optimized indexes
for the test sharing and collaboration features.

Usage:
    python scripts/init_test_shares_db.py

Author: GitHub Copilot
Date: 03/11/2025
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def init_test_shares_collection():
    """Initialize test_shares collection with indexes"""

    # MongoDB connection
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("MONGO_DB_NAME", "wordai")

    print(f"🔗 Connecting to MongoDB: {MONGO_URI}")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    # Create collection if not exists
    collection_name = "test_shares"
    if collection_name not in db.list_collection_names():
        db.create_collection(collection_name)
        print(f"✅ Created collection: {collection_name}")
    else:
        print(f"ℹ️  Collection already exists: {collection_name}")

    collection = db[collection_name]

    print("\n📊 Creating indexes for test_shares collection...")

    # Drop existing indexes (except _id) to start fresh
    try:
        existing_indexes = collection.list_indexes()
        for idx in existing_indexes:
            if idx["name"] != "_id_":
                collection.drop_index(idx["name"])
                print(f"🗑️  Dropped old index: {idx['name']}")
    except Exception as e:
        print(f"⚠️  Could not drop indexes: {e}")

    # Index 1: Query shares by test_id (most common query)
    collection.create_index([("test_id", ASCENDING)], name="idx_test_id")
    print("✅ Created index: idx_test_id")

    # Index 2: Query shares by sharer (owner dashboard)
    collection.create_index(
        [("sharer_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_sharer_created",
    )
    print("✅ Created index: idx_sharer_created")

    # Index 3: Query shares by sharee_email (before user registers)
    collection.create_index([("sharee_email", ASCENDING)], name="idx_sharee_email")
    print("✅ Created index: idx_sharee_email")

    # Index 4: Query shares by sharee_id (after user accepts)
    collection.create_index(
        [("sharee_id", ASCENDING), ("status", ASCENDING)], name="idx_sharee_status"
    )
    print("✅ Created index: idx_sharee_status")

    # Index 5: Unique invitation token lookup
    collection.create_index(
        [("invitation_token", ASCENDING)],
        unique=True,
        name="idx_invitation_token_unique",
    )
    print("✅ Created index: idx_invitation_token_unique")

    # Index 6: Query by status (for cron job and filtering)
    collection.create_index(
        [("status", ASCENDING), ("deadline", ASCENDING)], name="idx_status_deadline"
    )
    print("✅ Created index: idx_status_deadline")

    # Index 7: Compound index for deadline expiration cron job
    # Query: status = 'accepted' AND deadline < now()
    collection.create_index(
        [("status", ASCENDING), ("deadline", ASCENDING)],
        name="idx_deadline_expiration",
        partialFilterExpression={"status": "accepted", "deadline": {"$exists": True}},
    )
    print("✅ Created index: idx_deadline_expiration (partial)")

    # Index 8: Compound index for test + sharee (access validation)
    collection.create_index(
        [("test_id", ASCENDING), ("sharee_id", ASCENDING), ("status", ASCENDING)],
        name="idx_test_sharee_status",
    )
    print("✅ Created index: idx_test_sharee_status")

    # Index 9: TTL index for old declined/expired shares (cleanup after 90 days)
    collection.create_index(
        [("created_at", ASCENDING)],
        expireAfterSeconds=90 * 24 * 60 * 60,  # 90 days
        name="idx_ttl_cleanup",
        partialFilterExpression={"status": {"$in": ["declined", "expired"]}},
    )
    print("✅ Created index: idx_ttl_cleanup (TTL 90 days)")

    print("\n" + "=" * 60)
    print("✅ Database initialization completed successfully!")
    print("=" * 60)

    # Display collection stats
    stats = db.command("collstats", collection_name)
    print(f"\n📊 Collection Stats:")
    print(f"   Documents: {stats.get('count', 0)}")
    print(f"   Indexes: {stats.get('nindexes', 0)}")
    print(f"   Size: {stats.get('size', 0) / 1024:.2f} KB")

    # List all indexes
    print(f"\n📋 Indexes Created:")
    for idx in collection.list_indexes():
        print(f"   - {idx['name']}: {idx.get('key', {})}")

    client.close()
    print("\n🔌 MongoDB connection closed")


def show_schema_example():
    """Display test_shares schema example"""
    print("\n" + "=" * 60)
    print("📝 test_shares Collection Schema")
    print("=" * 60)

    schema = {
        "_id": "ObjectId (auto-generated)",
        "share_id": "str (uuid-v4)",
        "test_id": "str (reference to online_tests)",
        "sharer_id": "str (Firebase UID of test owner)",
        "sharee_email": "str (email of person to share with)",
        "sharee_id": "str | None (Firebase UID after user accepts)",
        "invitation_token": "str (uuid-v4, unique)",
        "status": "str (pending | accepted | completed | expired | declined)",
        "deadline": "datetime | None (optional deadline)",
        "created_at": "datetime (when share was created)",
        "accepted_at": "datetime | None (when user accepted invitation)",
        "completed_at": "datetime | None (when user completed test)",
        "message": "str | None (optional message from sharer)",
    }

    print("\nFields:")
    for field, desc in schema.items():
        print(f"  {field:20} -> {desc}")

    print("\nStatus Workflow:")
    print("  pending   -> Email sent, waiting for user to accept")
    print("  accepted  -> User accepted, can take test")
    print("  completed -> User finished test")
    print("  expired   -> Deadline passed, no longer valid")
    print("  declined  -> User rejected invitation")

    print("\nIndexes Purpose:")
    print("  1. idx_test_id                 -> List all shares for a test")
    print("  2. idx_sharer_created          -> Owner dashboard (my shared tests)")
    print("  3. idx_sharee_email            -> Find pending invites by email")
    print("  4. idx_sharee_status           -> User's invitations list")
    print("  5. idx_invitation_token_unique -> Accept/decline invitation lookup")
    print("  6. idx_status_deadline         -> Filter by status and deadline")
    print("  7. idx_deadline_expiration     -> Cron job to expire shares")
    print("  8. idx_test_sharee_status      -> Validate user access to test")
    print("  9. idx_ttl_cleanup             -> Auto-delete old declined/expired")


if __name__ == "__main__":
    print("🚀 Starting database initialization for Test Sharing System - Phase 4")
    print("=" * 60)

    try:
        init_test_shares_collection()
        show_schema_example()

        print("\n" + "=" * 60)
        print("✅ All done! You can now use the test sharing features.")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
