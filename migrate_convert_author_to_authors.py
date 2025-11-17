#!/usr/bin/env python3
"""
Migration: Convert single author_id to authors array
Date: 2025-01-17

Changes:
- Convert author_id field → authors: [author_id]
- For books without author_id → authors: []
- Remove author_id field after conversion
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime


def migrate_author_to_authors():
    """Convert author_id to authors array in online_books collection"""

    # MongoDB connection
    mongo_uri = os.getenv(
        "MONGODB_URI",
        "mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/",
    )
    db_name = "ai_service_db"

    print(f"🔌 Connecting to MongoDB: {db_name}...")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db["online_books"]

    print("=" * 70)
    print("MIGRATION: Convert author_id → authors array")
    print("=" * 70)

    # Step 1: Count books with old structure (has author_id field)
    books_with_author_id = list(collection.find({"author_id": {"$exists": True}}))
    print(f"\n📊 Found {len(books_with_author_id)} books with author_id field")

    # Step 2: Count books already migrated (has authors field)
    books_with_authors = collection.count_documents({"authors": {"$exists": True}})
    print(f"✅ Found {books_with_authors} books already have authors field")

    # Step 3: Migrate books with author_id
    if len(books_with_author_id) == 0:
        print(
            "\n✅ No books need migration. All books already migrated or don't have author_id."
        )
        return

    print(f"\n🚀 Starting migration for {len(books_with_author_id)} books...")
    migrated_count = 0
    error_count = 0

    for book in books_with_author_id:
        try:
            book_id = book.get("book_id")
            author_id = book.get("author_id")

            # Convert to authors array
            if author_id:
                authors = [author_id]  # Single author → array
            else:
                authors = []  # No author → empty array

            # Update book: set authors, unset author_id
            result = collection.update_one(
                {"book_id": book_id},
                {
                    "$set": {
                        "authors": authors,
                        "updated_at": datetime.utcnow(),
                    },
                    "$unset": {"author_id": ""},  # Remove old field
                },
            )

            if result.modified_count > 0:
                migrated_count += 1
                print(
                    f"  ✅ Migrated book {book_id}: author_id='{author_id}' → authors={authors}"
                )
            else:
                print(f"  ⚠️  Book {book_id} already migrated or no changes needed")

        except Exception as e:
            error_count += 1
            print(f"  ❌ Error migrating book {book_id}: {str(e)}")

    # Summary
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"✅ Successfully migrated: {migrated_count} books")
    print(f"❌ Errors: {error_count} books")
    print(f"📊 Total processed: {len(books_with_author_id)} books")
    print("=" * 70)

    # Verify migration
    print("\n🔍 Verifying migration...")
    remaining_author_id = collection.count_documents({"author_id": {"$exists": True}})
    total_with_authors = collection.count_documents({"authors": {"$exists": True}})
    print(f"📊 Books still with author_id: {remaining_author_id}")
    print(f"✅ Books with authors field: {total_with_authors}")

    if remaining_author_id > 0:
        print("\n⚠️  WARNING: Some books still have author_id field!")
    else:
        print("\n✅ SUCCESS: All books migrated to authors array!")

    client.close()


if __name__ == "__main__":
    try:
        migrate_author_to_authors()
    except Exception as e:
        print(f"\n❌ MIGRATION FAILED: {str(e)}")
        sys.exit(1)
