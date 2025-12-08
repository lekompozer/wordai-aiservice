#!/usr/bin/env python3
"""
Migration Script: Add Purchase Stats Fields to Books
Adds purchase tracking fields to existing books in online_books collection.

Fields added to stats object:
- one_time_purchases: 0
- forever_purchases: 0
- pdf_downloads: 0
- one_time_revenue: 0
- forever_revenue: 0
- pdf_revenue: 0

Usage:
    python migrate_add_purchase_stats_fields.py
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection - try both MONGODB_URI_AUTH (production) and MONGODB_URI (local)
MONGODB_URI = os.getenv(
    "MONGODB_URI_AUTH",
    os.getenv(
        "MONGODB_URI",
        "mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin",
    ),
)
DB_NAME = "ai_service_db"
COLLECTION_NAME = "online_books"


def migrate():
    """Add purchase stats fields to all books"""
    print("=" * 80)
    print("MIGRATION: Add Purchase Stats Fields to Books")
    print("=" * 80)

    try:
        # Connect to MongoDB
        print(f"\n📡 Connecting to MongoDB: {MONGODB_URI[:50]}...")
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # Test connection
        client.admin.command("ping")
        print("✅ Connected to MongoDB successfully")

        # Find books that don't have purchase stats fields
        query = {
            "$or": [
                {"stats.one_time_purchases": {"$exists": False}},
                {"stats.forever_purchases": {"$exists": False}},
                {"stats.pdf_downloads": {"$exists": False}},
                {"stats.one_time_revenue": {"$exists": False}},
                {"stats.forever_revenue": {"$exists": False}},
                {"stats.pdf_revenue": {"$exists": False}},
            ]
        }

        books_to_update = collection.count_documents(query)

        if books_to_update == 0:
            print(
                "\n✅ No books need migration. All books already have purchase stats fields."
            )
            return

        print(f"\n📊 Found {books_to_update} books needing migration")
        print("\n🔄 Adding purchase stats fields...")

        # Update all books
        result = collection.update_many(
            query,
            {
                "$set": {
                    # Purchase counts
                    "stats.one_time_purchases": 0,
                    "stats.forever_purchases": 0,
                    "stats.pdf_downloads": 0,
                    # Purchase revenue
                    "stats.one_time_revenue": 0,
                    "stats.forever_revenue": 0,
                    "stats.pdf_revenue": 0,
                }
            },
        )

        print(f"✅ Migration completed successfully!")
        print(f"   - Matched: {result.matched_count} books")
        print(f"   - Modified: {result.modified_count} books")

        # Verify migration
        print("\n🔍 Verifying migration...")
        remaining = collection.count_documents(query)
        if remaining == 0:
            print("✅ All books now have purchase stats fields")
        else:
            print(f"⚠️  Warning: {remaining} books still missing fields")

        # Show sample book with new fields
        print("\n📝 Sample book with new fields:")
        sample_book = collection.find_one(
            {"stats.one_time_purchases": {"$exists": True}},
            {
                "_id": 0,
                "book_id": 1,
                "title": 1,
                "stats.one_time_purchases": 1,
                "stats.forever_purchases": 1,
                "stats.pdf_downloads": 1,
                "stats.one_time_revenue": 1,
                "stats.forever_revenue": 1,
                "stats.pdf_revenue": 1,
            },
        )
        if sample_book:
            print(f"   Book ID: {sample_book.get('book_id')}")
            print(f"   Title: {sample_book.get('title')}")
            print(f"   Stats: {sample_book.get('stats', {})}")

        print("\n" + "=" * 80)
        print("✅ MIGRATION SUCCESSFUL")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if "client" in locals():
            client.close()
            print("\n🔌 MongoDB connection closed")


if __name__ == "__main__":
    migrate()
