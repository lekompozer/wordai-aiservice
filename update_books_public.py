#!/usr/bin/env python3
"""Update crawled books to be public"""

from src.database.db_manager import DBManager

db = DBManager().db

print("🔄 Updating crawled books to be public...")

# Update all books from nhasachmienphi.com
result = db.online_books.update_many(
    {"source": "nhasachmienphi.com"}, {"$set": {"community_config.is_public": True}}
)

print(f"✅ Updated {result.modified_count} books")
print(f"   Matched: {result.matched_count}")

# Verify
books = list(
    db.online_books.find(
        {"source": "nhasachmienphi.com"}, {"title": 1, "community_config.is_public": 1}
    )
)
print(f"\n📚 Verified {len(books)} books:")
for book in books:
    status = (
        "✅ PUBLIC"
        if book.get("community_config", {}).get("is_public")
        else "❌ PRIVATE"
    )
    print(f"   {status} - {book.get('title')}")
