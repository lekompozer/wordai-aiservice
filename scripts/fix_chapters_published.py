#!/usr/bin/env python3
"""Fix existing crawled chapters - add is_published and order_index"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

print("=" * 60)
print("🔧 Fix Crawled Chapters - Add Missing Fields")
print("=" * 60)

# Get all sachonline books
sachonline_books = list(db.online_books.find({"authors": "@sachonline"}))
book_ids = [b["book_id"] for b in sachonline_books]

# Get chapters missing is_published
chapters = list(
    db.book_chapters.find(
        {"book_id": {"$in": book_ids}, "is_published": {"$exists": False}}
    )
)

print(f"\n📄 Found {len(chapters)} chapters missing is_published\n")

total_updated = 0

for ch in chapters:
    book_id = ch["book_id"]
    book = db.online_books.find_one({"book_id": book_id})

    if book:
        title = ch.get("title", "Unknown")

        print(f"📖 {book['title'][:40]}")
        print(f"   Chapter: {title}")

        # Update chapter with missing fields
        update_fields = {}

        if "is_published" not in ch:
            update_fields["is_published"] = True
            print(f"   + is_published: True")

        if "order_index" not in ch:
            update_fields["order_index"] = 0
            print(f"   + order_index: 0")

        if "is_preview_free" not in ch:
            update_fields["is_preview_free"] = False
            print(f"   + is_preview_free: False")

        if update_fields:
            result = db.book_chapters.update_one(
                {"_id": ch["_id"]}, {"$set": update_fields}
            )

            if result.modified_count > 0:
                total_updated += 1
                print(f"   ✅ Updated!")
        print()

print("=" * 60)
print(f"✅ Updated {total_updated} chapters")
print("=" * 60)

# Verify
print("\n🔍 Verification - Published chapters by book:")
for book_id in book_ids:
    book = db.online_books.find_one({"book_id": book_id})

    if not book:
        continue

    # Check with API filter
    published_chapters = list(
        db.book_chapters.find({"book_id": book_id, "is_published": True}).sort(
            "order_index", 1
        )
    )

    status = "✅" if len(published_chapters) > 0 else "❌"
    print(
        f"{status} {book['title'][:50]}: {len(published_chapters)} published chapter(s)"
    )

print("\n" + "=" * 60)
