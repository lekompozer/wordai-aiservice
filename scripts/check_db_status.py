#!/usr/bin/env python3
"""Check database status"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

# Count books and chapters
total_books = db.online_books.count_documents({})
sachonline_books = db.online_books.count_documents({"authors": "@sachonline"})
total_chapters = db.book_chapters.count_documents({})

print("=" * 60)
print("📊 DATABASE STATUS")
print("=" * 60)
print(f"📚 Total books: {total_books}")
print(f"📚 @sachonline books: {sachonline_books}")
print(f"📄 Total chapters: {total_chapters}")

# Get sachonline books
books = list(
    db.online_books.find({"authors": "@sachonline"}).sort("created_at", -1).limit(10)
)
print(f"\n🔍 @sachonline books (latest 10):")
for idx, b in enumerate(books, 1):
    chapters = db.book_chapters.count_documents({"book_id": b["book_id"]})
    book_id = b["book_id"]
    title = b["title"][:50]
    print(f"  [{idx}] {book_id} - {title}")
    print(f"      Chapters: {chapters}")

    if chapters > 0:
        chapter = db.book_chapters.find_one({"book_id": book_id})
        if chapter:
            print(f"      Chapter type: {chapter.get('chapter_type', 'N/A')}")
            print(f"      PDF URL: {chapter.get('pdf_url', 'N/A')[:60]}")

# Check recent chapters
print(f"\n📄 Recent chapters:")
recent_chapters = list(db.book_chapters.find().sort("created_at", -1).limit(5))
for idx, c in enumerate(recent_chapters, 1):
    print(f"  [{idx}] {c.get('chapter_id')} - Book: {c.get('book_id')}")
    print(f"      Type: {c.get('chapter_type', 'N/A')}")

print("=" * 60)
