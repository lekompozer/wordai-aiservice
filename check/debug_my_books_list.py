#!/usr/bin/env python3
"""
Debug: Check why newly created book doesn't appear in My Books list
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database

db = get_database()

# User from logs
user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"
book_id = "book_df213acf187b"
slug = "word-ai-user-manual"

print("=" * 100)
print(f"🔍 DEBUG: Why book not showing in My Books?")
print("=" * 100)

print(f"\n👤 User: {user_id}")
print(f"📚 Book ID: {book_id}")
print(f"🔗 Slug: {slug}")

# Check if book exists
book = db.online_books.find_one({"book_id": book_id})

if not book:
    print("\n❌ ERROR: Book not found in database!")
    sys.exit(1)

print("\n" + "=" * 100)
print("📖 BOOK DETAILS")
print("=" * 100)
print(f"   book_id: {book.get('book_id')}")
print(f"   user_id: {book.get('user_id')}")
print(f"   title: {book.get('title')}")
print(f"   slug: {book.get('slug')}")
print(f"   visibility: {book.get('visibility')}")
print(f"   is_deleted: {book.get('is_deleted', False)}")
print(f"   created_at: {book.get('created_at')}")
print(f"   updated_at: {book.get('updated_at')}")

# Check if is_published field exists
is_published = book.get("is_published")
print(f"   is_published: {is_published}")

# Check community_config
community_config = book.get("community_config", {})
print(f"\n📋 community_config:")
print(f"   is_public: {community_config.get('is_public', False)}")
print(f"   published_at: {community_config.get('published_at')}")

# Check user_id match
print(f"\n🔍 USER ID CHECK:")
print(f"   Expected user: {user_id}")
print(f"   Book owner: {book.get('user_id')}")
print(f"   Match: {book.get('user_id') == user_id}")

# Simulate My Books query (GET /api/v1/books)
print("\n" + "=" * 100)
print("🔍 SIMULATING MY BOOKS QUERY")
print("=" * 100)

# Default query from logs: GET /api/v1/books (no filters)
query = {
    "user_id": user_id,
    # My Books typically filters out deleted books
    # But might not have other filters
}

print(f"\nQuery: {query}")

matching_books = list(db.online_books.find(query))
print(f"\n📊 Found {len(matching_books)} books for user")

for i, b in enumerate(matching_books, 1):
    print(f"\n   Book {i}:")
    print(f"   - book_id: {b.get('book_id')}")
    print(f"   - title: {b.get('title')}")
    print(f"   - slug: {b.get('slug')}")
    print(f"   - visibility: {b.get('visibility')}")
    print(f"   - is_deleted: {b.get('is_deleted', False)}")

# Check if new book is in the list
new_book_in_list = any(b.get("book_id") == book_id for b in matching_books)
print(f"\n✅ New book in list: {new_book_in_list}")

if not new_book_in_list:
    print("\n❌ PROBLEM FOUND: Book exists but not returned by query!")

    # Check possible reasons
    print("\n🔍 Possible reasons:")

    if book.get("is_deleted", False):
        print("   ❌ Book is marked as deleted")
    else:
        print("   ✅ Book is not deleted")

    if book.get("user_id") != user_id:
        print(f"   ❌ user_id mismatch: {book.get('user_id')} != {user_id}")
    else:
        print("   ✅ user_id matches")

    # Check if there's a filter on is_published or visibility
    print("\n   ⚠️  Frontend might be filtering by:")
    print(f"      - visibility: {book.get('visibility')}")
    print(f"      - is_published: {book.get('is_published')}")
    print(f"      - community_config.is_public: {community_config.get('is_public')}")

print("\n" + "=" * 100)
print("💡 SOLUTION")
print("=" * 100)

if new_book_in_list:
    print("✅ Book is correctly in database and query results")
    print("⚠️  Issue might be in frontend:")
    print("   1. Frontend caching (not refetching after create)")
    print("   2. Frontend filtering response data")
    print("   3. Frontend not updating state after successful create")
else:
    print("❌ Book exists but not returned by My Books query")
    print("   Check query filters in book_routes.py list_guides() endpoint")

print("\n")
