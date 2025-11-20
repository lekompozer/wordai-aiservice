#!/usr/bin/env python3
"""
Setup MongoDB indexes for book view tracking system

Collection: book_view_sessions
Purpose: Track unique book views per user/browser per day
"""

import os
from pymongo import MongoClient, ASCENDING
from datetime import datetime

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017/")
MONGODB_DB = os.getenv("MONGODB_DB", "wordai")

print("🔗 Connecting to MongoDB...")
client = MongoClient(MONGODB_URL)
db = client[MONGODB_DB]

print(f"✅ Connected to database: {MONGODB_DB}")

# Collection name
collection = db["book_view_sessions"]

print("\n📋 Creating indexes for book_view_sessions collection...")

try:
    # 1. Compound index for deduplication check (UNIQUE per book/viewer/day)
    # This ensures 1 view per viewer per book per day
    index1 = collection.create_index(
        [("book_id", ASCENDING), ("viewer_id", ASCENDING), ("viewed_at", ASCENDING)],
        name="book_viewer_date_unique",
        background=True,
    )
    print(f"✅ Created index: {index1} (book_id, viewer_id, viewed_at)")

    # 2. TTL index for automatic cleanup (expires_at)
    # Documents will be automatically deleted after expires_at timestamp
    index2 = collection.create_index(
        [("expires_at", ASCENDING)],
        name="view_session_ttl",
        expireAfterSeconds=0,  # Delete at expires_at time
        background=True,
    )
    print(f"✅ Created TTL index: {index2} (expires_at)")

    # 3. Index for analytics queries by book
    index3 = collection.create_index(
        [("book_id", ASCENDING), ("viewed_at", ASCENDING)],
        name="book_views_by_date",
        background=True,
    )
    print(f"✅ Created index: {index3} (book_id, viewed_at)")

    # 4. Index for user analytics (if needed)
    index4 = collection.create_index(
        [("user_id", ASCENDING), ("viewed_at", ASCENDING)],
        name="user_views_by_date",
        sparse=True,  # Only for documents with user_id
        background=True,
    )
    print(f"✅ Created index: {index4} (user_id, viewed_at)")

    print("\n✅ All indexes created successfully!")

    # List all indexes
    print("\n📊 Current indexes on book_view_sessions:")
    for index in collection.list_indexes():
        print(f"  - {index['name']}: {index.get('key', {})}")
        if "expireAfterSeconds" in index:
            print(f"    TTL: {index['expireAfterSeconds']}s")

    # Show collection stats
    stats = db.command("collStats", "book_view_sessions")
    print(f"\n📈 Collection stats:")
    print(f"  - Documents: {stats.get('count', 0)}")
    print(f"  - Size: {stats.get('size', 0)} bytes")
    print(f"  - Indexes: {stats.get('nindexes', 0)}")

except Exception as e:
    print(f"\n❌ Error creating indexes: {e}")
    raise

finally:
    client.close()
    print("\n👋 Connection closed")
