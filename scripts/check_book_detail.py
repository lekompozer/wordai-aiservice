#!/usr/bin/env python3
"""Check book detail with all fields"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager
import json

db = DBManager().db

# Get latest crawled book
book = db.online_books.find_one({"authors": "@sachonline"}, sort=[("created_at", -1)])

if book:
    print("=" * 60)
    print(f"📖 Book: {book['title']}")
    print("=" * 60)
    print(f"Book ID: {book['book_id']}")
    print(f"Slug: {book['slug']}")
    print(f"User ID: {book['user_id']}")
    print(f"Authors: {book['authors']}")
    print(f"Published: {book.get('is_published', False)}")
    print(f"Deleted: {book.get('is_deleted', False)}")
    print(f"Cover: {book.get('cover_image_url', 'N/A')[:70]}")

    # Community config
    cc = book.get("community_config", {})
    print(f"\n📢 Community Config:")
    print(f"  is_public: {cc.get('is_public', False)}")
    print(f"  category: {cc.get('category', 'N/A')}")
    print(f"  tags: {cc.get('tags', [])}")

    # Access config
    ac = book.get("access_config", {})
    print(f"\n💰 Access Config:")
    print(f"  one_time_view_points: {ac.get('one_time_view_points', 0)}")
    print(f"  forever_view_points: {ac.get('forever_view_points', 0)}")
    print(f"  is_one_time_enabled: {ac.get('is_one_time_enabled', False)}")
    print(f"  is_forever_enabled: {ac.get('is_forever_enabled', False)}")

    # Check chapters
    chapters = list(
        db.book_chapters.find({"book_id": book["book_id"]}).sort("chapter_number", 1)
    )
    print(f"\n📄 Chapters: {len(chapters)}")

    for idx, ch in enumerate(chapters, 1):
        print(f"\n  [{idx}] Chapter {ch.get('chapter_number', 'N/A')}")
        print(f"      chapter_id: {ch.get('chapter_id', 'N/A')}")
        print(f"      title: {ch.get('title', 'N/A')}")
        print(f"      chapter_type: {ch.get('chapter_type', 'N/A')}")
        print(f"      pdf_url: {ch.get('pdf_url', 'N/A')[:70]}")

        # Show all fields in chapter
        print(f"      All fields: {list(ch.keys())}")

    print("\n" + "=" * 60)

    # Check if this matches API response structure
    print("🔍 Checking API compatibility:")

    required_book_fields = [
        "book_id",
        "title",
        "slug",
        "user_id",
        "authors",
        "cover_image_url",
    ]
    required_chapter_fields = ["chapter_id", "book_id", "chapter_number", "title"]

    missing_book = [f for f in required_book_fields if f not in book]
    print(f"  Missing book fields: {missing_book or 'None ✅'}")

    if chapters:
        missing_chapter = [f for f in required_chapter_fields if f not in chapters[0]]
        print(f"  Missing chapter fields: {missing_chapter or 'None ✅'}")

    print("=" * 60)
