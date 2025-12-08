#!/usr/bin/env python3
"""
Check is_deleted field for newly created book
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.db_manager import DBManager

# Get DB connection
db_manager = DBManager()
db = db_manager.db  # Access db directly

user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

print("\n" + "=" * 60)
print("🔍 CHECKING is_deleted FIELD FOR ALL USER BOOKS")
print("=" * 60)

# Find ALL books for this user (no filters)
all_books = list(
    db.online_books.find(
        {"user_id": user_id},
        {"book_id": 1, "title": 1, "is_deleted": 1, "created_at": 1, "_id": 0},
    ).sort("created_at", -1)
)

print(f"\n📚 Found {len(all_books)} total books in database:")
for i, book in enumerate(all_books, 1):
    print(f"\n{i}. Book ID: {book.get('book_id')}")
    print(f"   Title: {book.get('title')}")
    print(f"   is_deleted: {book.get('is_deleted', 'FIELD NOT SET!')}")
    print(f"   created_at: {book.get('created_at')}")

# Now check with is_deleted filter
print("\n" + "=" * 60)
print("🔍 BOOKS WITH is_deleted=False (what API returns):")
print("=" * 60)

active_books = list(
    db.online_books.find(
        {"user_id": user_id, "is_deleted": False},
        {"book_id": 1, "title": 1, "is_deleted": 1, "_id": 0},
    )
)

print(f"\n✅ Found {len(active_books)} active books:")
for book in active_books:
    print(f"  - {book.get('book_id')}: {book.get('title')}")

# Check if new book has is_deleted field
print("\n" + "=" * 60)
print("🔍 CHECKING NEWLY CREATED BOOK:")
print("=" * 60)

new_book = db.online_books.find_one({"book_id": "book_df213acf187b"})

if new_book:
    print(f"\n✅ Found book: {new_book.get('title')}")
    print(f"   is_deleted field exists: {'is_deleted' in new_book}")
    print(f"   is_deleted value: {new_book.get('is_deleted')}")
    print(f"   Type: {type(new_book.get('is_deleted'))}")

    if "is_deleted" not in new_book:
        print("\n❌ PROBLEM: is_deleted field is MISSING!")
        print("   MongoDB query with is_deleted=False will NOT match this book!")
else:
    print("\n❌ Book not found!")

print("\n" + "=" * 60)
print("💡 SOLUTION:")
print("=" * 60)
print("If is_deleted field is missing, we need to:")
print("1. Update all books without is_deleted field to set is_deleted=False")
print("2. Or change query to handle missing field")
print("=" * 60 + "\n")
