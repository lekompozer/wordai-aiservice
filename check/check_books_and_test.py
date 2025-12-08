#!/usr/bin/env python3
"""
Check what books exist in the database
"""
import sys

sys.path.insert(0, "/app/src")

from src.config.database import get_database

db = get_database()

print("🔍 Checking published books in database...")
print("=" * 80)

# Find all published books
books = list(
    db.online_books.find(
        {"community_config.is_public": True},
        {
            "book_id": 1,
            "title": 1,
            "slug": 1,
            "community_config.is_public": 1,
            "access_config": 1,
        },
    ).limit(10)
)

print(f"\n📚 Found {len(books)} published books:\n")

for i, book in enumerate(books, 1):
    book_id = book.get("book_id")
    title = book.get("title", "No title")
    slug = book.get("slug", "no-slug")
    has_access_config = "access_config" in book

    print(f"{i}. Book ID: {book_id}")
    print(f"   Title: {title}")
    print(f"   Slug: {slug}")
    print(f"   Has access_config: {has_access_config}")

    if has_access_config and book["access_config"]:
        ac = book["access_config"]
        print(f"   Access config keys: {list(ac.keys())}")
        # Check for our specific fields
        if "download_pdf_points" in ac:
            print(f"   ✅ download_pdf_points: {ac['download_pdf_points']}")
        if "pdf_download_points" in ac:
            print(f"   ⚠️ pdf_download_points: {ac['pdf_download_points']}")
    print()

print("=" * 80)
print("\n🔍 Testing with first book ID...")
if books:
    test_book_id = books[0].get("book_id")
    print(f"Book ID to test: {test_book_id}")

    import requests

    url = f"http://localhost:8000/books/{test_book_id}/preview"
    print(f"URL: {url}")

    response = requests.get(url)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        if "access_config" in data and data["access_config"]:
            print("\n✅ API Response access_config:")
            import json

            print(json.dumps(data["access_config"], indent=2))
