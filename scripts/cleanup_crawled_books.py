#!/usr/bin/env python3
"""Clean up crawled books from nhasachmienphi.com"""

from src.database.db_manager import DBManager

db = DBManager().db

print("🧹 Cleaning up crawled books...")

# Find all crawled books
crawled_books = list(db.online_books.find({"source": "nhasachmienphi.com"}))
print(f"\n📚 Found {len(crawled_books)} crawled books")

if crawled_books:
    book_ids = [b.get("book_id") or b.get("_id") for b in crawled_books]

    # Delete chapters first
    chapters_result = db.book_chapters.delete_many({"book_id": {"$in": book_ids}})
    print(f"   ✅ Deleted {chapters_result.deleted_count} chapters")

    # Delete books
    books_result = db.online_books.delete_many({"book_id": {"$in": book_ids}})
    print(f"   ✅ Deleted {books_result.deleted_count} books")

    print(f"\n✅ Cleanup completed!")
    print(f"   Books deleted: {books_result.deleted_count}")
    print(f"   Chapters deleted: {chapters_result.deleted_count}")
else:
    print("   ℹ️  No crawled books to delete")

# Show remaining books for @sachonline
remaining = db.online_books.count_documents({"authors": "@sachonline"})
print(f"\n📖 Remaining books by @sachonline: {remaining}")
