#!/usr/bin/env python3
"""Compare working book vs crawled book in database"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

print("=" * 70)
print("🔍 Compare Working vs Crawled Books")
print("=" * 70)

# Working book (has chapters displayed)
working_book_id = "book_19127824bb26"  # Tiểu Sử Các Quốc Gia...

# Crawled book (no chapters displayed)
crawled_book_id = "book_35a0af85e24c"  # Kinh Nghiệm Thành Công...

for label, book_id in [
    ("WORKING BOOK", working_book_id),
    ("CRAWLED BOOK", crawled_book_id),
]:
    print(f"\n{'='*70}")
    print(f"{label}: {book_id}")
    print("=" * 70)

    book = db.online_books.find_one({"book_id": book_id})
    if book:
        print(f"Title: {book['title'][:60]}")

        # Get ALL chapters (no filter)
        all_chapters = list(db.book_chapters.find({"book_id": book_id}))
        print(f"\nTotal chapters in DB: {len(all_chapters)}")

        # Check with is_published filter (what API uses)
        published_chapters = list(
            db.book_chapters.find({"book_id": book_id, "is_published": True})
        )
        print(f"Published chapters: {len(published_chapters)}")

        if all_chapters:
            ch = all_chapters[0]
            print(f"\nFirst chapter fields:")
            print(f"  title: {ch.get('title', 'N/A')}")
            print(f"  chapter_id: {ch.get('chapter_id', 'N/A')}")
            print(f"  chapter_number: {ch.get('chapter_number', 'N/A')}")
            print(f"  slug: {ch.get('slug', 'N/A')}")
            print(f"  chapter_type: {ch.get('chapter_type', 'N/A')}")
            print(f"  content_mode: {ch.get('content_mode', 'N/A')}")
            print(f"  is_published: {ch.get('is_published', 'MISSING!')}")
            print(f"  order_index: {ch.get('order_index', 'MISSING!')}")
            print(f"\n  All fields: {list(ch.keys())}")

print("\n" + "=" * 70)
print("🔍 DIAGNOSIS")
print("=" * 70)
print("\nAPI query uses: db.book_chapters.find({'book_id': ..., 'is_published': True})")
print("If chapters don't have is_published=True, they won't appear in API!")
print("=" * 70)
