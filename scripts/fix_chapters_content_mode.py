#!/usr/bin/env python3
"""Fix existing chapters - add content_mode field"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

print("=" * 60)
print("🔧 Fix Existing Chapters - Add content_mode")
print("=" * 60)

# Get all sachonline books
books = list(db.online_books.find({"authors": "@sachonline"}))
print(f"\n📚 Found {len(books)} books by @sachonline\n")

total_updated = 0

for book in books:
    book_id = book["book_id"]
    title = book["title"][:50]

    # Get chapters with chapter_type = "pdf" but missing content_mode
    chapters = list(
        db.book_chapters.find(
            {
                "book_id": book_id,
                "chapter_type": "pdf",
                "content_mode": {"$exists": False},
            }
        )
    )

    if chapters:
        print(f"📖 {title}")
        print(f"   Book ID: {book_id}")
        print(f"   Chapters to update: {len(chapters)}")

        for ch in chapters:
            # Update chapter with content_mode
            result = db.book_chapters.update_one(
                {"_id": ch["_id"]}, {"$set": {"content_mode": "pdf_file"}}
            )

            if result.modified_count > 0:
                total_updated += 1
                print(f"   ✅ Updated chapter: {ch.get('title', 'N/A')}")
        print()

print("=" * 60)
print(f"✅ Updated {total_updated} chapters with content_mode='pdf_file'")
print("=" * 60)

# Verify
print("\n🔍 Verification:")
for book in books:
    chapters = list(db.book_chapters.find({"book_id": book["book_id"]}))
    for ch in chapters:
        has_content_mode = "content_mode" in ch
        content_mode = ch.get("content_mode", "N/A")
        chapter_type = ch.get("chapter_type", "N/A")

        status = "✅" if has_content_mode else "❌"
        print(
            f"{status} {book['title'][:40]}: type={chapter_type}, mode={content_mode}"
        )

print("\n" + "=" * 60)
