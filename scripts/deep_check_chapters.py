#!/usr/bin/env python3
"""Deep check all sachonline chapters"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

print("=" * 60)
print("🔍 Deep Check All @sachonline Chapters")
print("=" * 60)

# Get all sachonline books
books = list(db.online_books.find({"authors": "@sachonline"}).sort("created_at", -1))

print(f"\n📚 Found {len(books)} books by @sachonline\n")

total_chapters = 0
missing_id = []
missing_fields = []

for idx, book in enumerate(books, 1):
    book_id = book["book_id"]
    title = book["title"]

    # Get chapters
    chapters = list(db.book_chapters.find({"book_id": book_id}))
    total_chapters += len(chapters)

    print(f"[{idx}] {book_id}")
    print(f"    Title: {title[:50]}")
    print(f"    Chapters: {len(chapters)}")

    for ch_idx, ch in enumerate(chapters, 1):
        # Check _id field
        if "_id" not in ch:
            missing_id.append(f"{book_id} - Chapter {ch_idx}")
            print(f"    ❌ Chapter {ch_idx} missing _id!")

        # Check required fields
        required = ["chapter_id", "book_id", "chapter_number", "title"]
        missing = [f for f in required if f not in ch]
        if missing:
            missing_fields.append(f"{book_id} - Chapter {ch_idx}: {missing}")
            print(f"    ❌ Chapter {ch_idx} missing: {missing}")

        # Show chapter details
        chapter_type = ch.get("chapter_type", "N/A")
        pdf_url = ch.get("pdf_url", "N/A")[:50]
        print(
            f"    ✅ Ch{ch_idx}: {ch.get('title', 'N/A')[:30]} ({chapter_type}) - PDF: {pdf_url}..."
        )

    print()

print("=" * 60)
print(f"📊 SUMMARY")
print("=" * 60)
print(f"Total books: {len(books)}")
print(f"Total chapters: {total_chapters}")
print(f"Chapters missing _id: {len(missing_id)}")
print(f"Chapters with missing fields: {len(missing_fields)}")

if missing_id:
    print(f"\n❌ Missing _id:")
    for m in missing_id:
        print(f"  - {m}")

if missing_fields:
    print(f"\n❌ Missing fields:")
    for m in missing_fields:
        print(f"  - {m}")

if not missing_id and not missing_fields:
    print(f"\n✅ ALL CHAPTERS HAVE REQUIRED FIELDS!")

print("=" * 60)
