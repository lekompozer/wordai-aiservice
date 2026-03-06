#!/usr/bin/env python3
"""Delete all old crawled books from nhasachmienphi.com"""

from src.database.db_manager import DBManager


def delete_old_books():
    db_manager = DBManager()
    db = db_manager.db

    print("🗑️  Deleting old crawled books...")

    # Delete books
    result = db.online_books.delete_many({"source": "nhasachmienphi.com"})
    print(f"   📚 Deleted {result.deleted_count} books")

    # Delete chapters (orphaned)
    # Get all book_ids from online_books
    book_ids = [book["book_id"] for book in db.online_books.find({}, {"book_id": 1})]

    # Delete chapters not in book_ids
    chapter_result = db.book_chapters.delete_many({"book_id": {"$nin": book_ids}})
    print(f"   📄 Deleted {chapter_result.deleted_count} orphaned chapters")

    print("✅ Cleanup complete!")


if __name__ == "__main__":
    delete_old_books()
