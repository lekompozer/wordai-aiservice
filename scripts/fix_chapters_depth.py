#!/usr/bin/env python3
"""Fix existing crawled chapters - add depth field"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

print("=" * 60)
print("🔧 Fix Crawled Chapters - Add depth Field")
print("=" * 60)

# Get all sachonline books
sachonline_books = list(db.online_books.find({"authors": "@sachonline"}))
book_ids = [b["book_id"] for b in sachonline_books]

# Get chapters missing depth
chapters = list(
    db.book_chapters.find({"book_id": {"$in": book_ids}, "depth": {"$exists": False}})
)

print(f"\n📄 Found {len(chapters)} chapters missing depth field\n")

total_updated = 0

for ch in chapters:
    book_id = ch["book_id"]
    book = db.online_books.find_one({"book_id": book_id})

    if book:
        title = ch.get("title", "Unknown")

        print(f"📖 {book['title'][:40]}")
        print(f"   Chapter: {title}")
        print(f"   + depth: 0")

        # Update chapter with depth
        result = db.book_chapters.update_one({"_id": ch["_id"]}, {"$set": {"depth": 0}})

        if result.modified_count > 0:
            total_updated += 1
            print(f"   ✅ Updated!")
        print()

print("=" * 60)
print(f"✅ Updated {total_updated} chapters with depth=0")
print("=" * 60)

# Verify - check all required fields
print("\n🔍 Verification - All required fields:")
required_fields = [
    "chapter_id",
    "slug",
    "order_index",
    "depth",
    "is_published",
    "content_mode",
]

for book_id in book_ids:
    book = db.online_books.find_one({"book_id": book_id})
    if not book:
        continue

    chapters = list(db.book_chapters.find({"book_id": book_id}))

    for ch in chapters:
        missing = [f for f in required_fields if f not in ch]

        if missing:
            print(f"❌ {book['title'][:40]}: Missing {missing}")
        else:
            print(f"✅ {book['title'][:40]}: All required fields present")

print("\n" + "=" * 60)
