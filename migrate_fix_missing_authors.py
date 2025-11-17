"""
Migration script to fix missing authors in published books
Creates author entries in book_authors collection for published books
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime, timezone

# MongoDB connection
MONGODB_URI = os.environ.get(
    "MONGODB_URI_AUTH",
    "mongodb://ai_service_user:wordai_secure_2024@localhost:27017/ai_service_db?authSource=ai_service_db",
)


def migrate_fix_missing_authors():
    """
    Find all published books and ensure authors exist in book_authors collection
    """
    print("🔄 Starting migration to fix missing authors...")
    print(
        f"📡 Connecting to MongoDB: {MONGODB_URI.replace(MONGODB_URI.split('@')[0].split('//')[1], '***')}"
    )

    client = MongoClient(MONGODB_URI)
    db = client.ai_service_db

    try:
        # Find all published books
        published_books = list(
            db.online_books.find({"community_config.is_public": True})
        )

        print(f"\n📚 Found {len(published_books)} published books")

        authors_created = 0
        authors_existing = 0
        books_without_authors = 0
        books_updated = 0

        for book in published_books:
            book_id = book.get("book_id")
            title = book.get("title", "Untitled")
            authors_list = book.get("authors", [])
            user_id = book.get("user_id")
            community_config = book.get("community_config", {})

            # Fallback: If no authors field, try to get from community_config
            if not authors_list and community_config.get("author_id"):
                authors_list = [community_config["author_id"]]
                print(f"📝 Using author_id from community_config for book {book_id}")

                # Update book document with authors field
                db.online_books.update_one(
                    {"book_id": book_id}, {"$set": {"authors": authors_list}}
                )
                print(f"   Updated book document with authors field")
                books_updated += 1

            if not authors_list:
                print(f"⚠️  Book {book_id} ({title}) has no authors! Skipping...")
                books_without_authors += 1
                continue

            # Check each author
            for author_id in authors_list:
                existing_author = db.book_authors.find_one({"author_id": author_id})

                if existing_author:
                    print(f"✅ Author {author_id} already exists")
                    authors_existing += 1

                    # Ensure book is in author's books list
                    if book_id not in existing_author.get("books", []):
                        db.book_authors.update_one(
                            {"author_id": author_id}, {"$addToSet": {"books": book_id}}
                        )
                        print(f"   Added book {book_id} to author's books list")
                else:
                    # Create new author
                    author_name = (
                        author_id.replace("@", "")
                        .replace("_", " ")
                        .replace("-", " ")
                        .title()
                    )

                    author_doc = {
                        "author_id": author_id,
                        "user_id": user_id,
                        "name": author_name,
                        "bio": "",
                        "avatar_url": "",
                        "social_links": {},
                        "books": [book_id],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }

                    db.book_authors.insert_one(author_doc)
                    print(
                        f"✨ Created new author: {author_id} ({author_name}) for book {book_id}"
                    )
                    authors_created += 1

        print("\n" + "=" * 60)
        print("📊 MIGRATION SUMMARY:")
        print(f"   Published books: {len(published_books)}")
        print(f"   Books updated with authors field: {books_updated}")
        print(f"   Books without authors (skipped): {books_without_authors}")
        print(f"   Authors already existing: {authors_existing}")
        print(f"   Authors created: {authors_created}")
        print("=" * 60)
        print("✅ Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    migrate_fix_missing_authors()
