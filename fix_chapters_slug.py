#!/usr/bin/env python3
"""Fix existing chapters - add slug field"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

print("=" * 60)
print("🔧 Fix Existing Chapters - Add slug")
print("=" * 60)

# Get all sachonline books
sachonline_books = list(db.online_books.find({"authors": "@sachonline"}))
book_ids = [b["book_id"] for b in sachonline_books]

# Get chapters without slug
chapters = list(
    db.book_chapters.find({"book_id": {"$in": book_ids}, "slug": {"$exists": False}})
)

print(f"\n📄 Found {len(chapters)} chapters without slug\n")

total_updated = 0

for ch in chapters:
    book_id = ch["book_id"]
    book = db.online_books.find_one({"book_id": book_id})

    if book:
        title = ch.get("title", "Full Book")

        # Generate slug from title
        slug = title.lower()
        slug = slug.replace(" ", "-")
        slug = slug.replace(":", "")
        slug = slug.replace("?", "")
        slug = slug.replace("!", "")

        print(f"📖 {book['title'][:40]}")
        print(f"   Chapter: {title} → slug: {slug}")

        # Update chapter with slug
        result = db.book_chapters.update_one(
            {"_id": ch["_id"]}, {"$set": {"slug": slug}}
        )

        if result.modified_count > 0:
            total_updated += 1
            print(f"   ✅ Updated!")
        print()

print("=" * 60)
print(f"✅ Updated {total_updated} chapters with slug")
print("=" * 60)

# Verify
print("\n🔍 Verification:")
for book_id in book_ids:
    chapters = list(db.book_chapters.find({"book_id": book_id}))
    book = db.online_books.find_one({"book_id": book_id})

    for ch in chapters:
        has_slug = "slug" in ch
        slug = ch.get("slug", "N/A")

        status = "✅" if has_slug else "❌"
        print(f"{status} {book['title'][:40]}: slug={slug}")

print("\n" + "=" * 60)
