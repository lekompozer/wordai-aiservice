#!/usr/bin/env python3
"""Verify books appear on author profile"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager


def main():
    print("=" * 60)
    print("🔍 Verify Books on Author Profile")
    print("=" * 60)

    db_manager = DBManager()
    db = db_manager.db

    # Query books like API does
    books = list(
        db.online_books.find(
            {
                "authors": "@sachonline",
                "community_config.is_public": True,
                "is_deleted": {"$ne": True},
            }
        ).sort("created_at", -1)
    )

    print(f"\n📚 Found {len(books)} public books by @sachonline\n")

    for idx, book in enumerate(books, 1):
        cover = book.get("cover_image_url", "")
        category = book.get("community_config", {}).get("category", "N/A")
        points = book.get("access_config", {}).get("one_time_view_points", 0)

        print(f"[{idx}] {book['title']}")
        print(f"    Slug: {book['slug']}")
        print(f"    Category: {category}")
        print(f"    Price: {points} points (one-time)")
        print(f"    Cover: {cover[:70]}{'...' if len(cover) > 70 else ''}")
        print(f"    Public: {book.get('community_config', {}).get('is_public', False)}")
        print()

    # Check if all have correct R2 URLs
    all_cover_ok = all(
        b.get("cover_image_url", "").startswith(
            "https://static.wordai.pro/books/covers/"
        )
        for b in books
    )

    print("=" * 60)
    if all_cover_ok:
        print("✅ ALL books have R2 cover URLs!")
        print("✅ Books should display on https://wordai.pro/authors/@sachonline")
    else:
        print("⚠️  Some books have non-R2 cover URLs")
    print("=" * 60)


if __name__ == "__main__":
    main()
