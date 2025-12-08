#!/usr/bin/env python3
"""
Fix all books missing is_deleted field
Set is_deleted=False for all existing books that don't have this field
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.db_manager import DBManager

# Get DB connection
db_manager = DBManager()
db = db_manager.db

print("\n" + "=" * 70)
print("🔧 FIXING BOOKS MISSING is_deleted FIELD")
print("=" * 70)

# Find all books WITHOUT is_deleted field
books_without_field = list(
    db.online_books.find(
        {"is_deleted": {"$exists": False}},
        {"book_id": 1, "title": 1, "user_id": 1, "_id": 0},
    )
)

print(f"\n📊 Found {len(books_without_field)} books without is_deleted field")

if len(books_without_field) == 0:
    print("✅ All books already have is_deleted field!")
    print("=" * 70 + "\n")
    sys.exit(0)

print("\n📝 Books to update:")
for book in books_without_field:
    print(f"  - {book.get('book_id')}: {book.get('title')}")

# Confirm update
print("\n" + "=" * 70)
print("⚠️  This will set is_deleted=False for all these books")
print("=" * 70)

# Perform update
result = db.online_books.update_many(
    {"is_deleted": {"$exists": False}}, {"$set": {"is_deleted": False}}
)

print(f"\n✅ Updated {result.modified_count} books")
print(f"   Matched: {result.matched_count}")

# Verify
print("\n" + "=" * 70)
print("🔍 VERIFICATION:")
print("=" * 70)

remaining = db.online_books.count_documents({"is_deleted": {"$exists": False}})
print(f"\n✅ Books without is_deleted field: {remaining}")

if remaining == 0:
    print("🎉 SUCCESS! All books now have is_deleted field")
else:
    print(f"⚠️  WARNING: {remaining} books still missing field")

# Show sample updated books
print("\n📚 Sample updated books:")
sample = list(
    db.online_books.find(
        {"is_deleted": False}, {"book_id": 1, "title": 1, "is_deleted": 1, "_id": 0}
    ).limit(5)
)

for book in sample:
    print(f"  - {book.get('book_id')}: is_deleted={book.get('is_deleted')}")

print("\n" + "=" * 70)
print("✅ FIX COMPLETE")
print("=" * 70 + "\n")
