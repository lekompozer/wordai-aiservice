#!/usr/bin/env python3
"""
Debug script to see exact query used in list_guides endpoint
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv("development.env")

# Connect to MongoDB
mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["ai_service_db"]

uid = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

# Simulate the EXACT query from list_guides endpoint
# WITHOUT any is_published filter (because URL has no parameter)

query = {
    "user_id": uid,
    "is_deleted": False,
}

print("=" * 80)
print("🔍 SIMULATING LIST_GUIDES QUERY (No is_published parameter)")
print("=" * 80)
print(f"\n📝 Query: {query}")

# Execute query
books = list(db.online_books.find(query))

print(f"\n📊 Results: {len(books)} books found")
print("=" * 80)

for i, book in enumerate(books, 1):
    print(f"\n📖 Book {i}:")
    print(f"   book_id: {book['book_id']}")
    print(f"   title: {book['title']}")
    print(f"   visibility: {book.get('visibility')}")
    print(f"   is_deleted: {book.get('is_deleted')}")
    print(
        f"   is_published: {book.get('community_config', {}).get('is_public', False)}"
    )
    print(f"   created_at: {book.get('created_at')}")

print("\n" + "=" * 80)
print("✅ This should return 2 books for My Books page")
print("=" * 80)
