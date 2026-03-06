#!/usr/bin/env python3
"""Check chapter slug pattern"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db = DBManager().db

# Get some chapters with slug
chapters_with_slug = list(db.book_chapters.find({"slug": {"$exists": True}}).limit(10))
print("Chapters with slug:")
for ch in chapters_with_slug:
    print(f"  - {ch.get('title', 'N/A')[:40]}: slug={ch.get('slug', 'N/A')}")

# Get sachonline chapters without slug
sachonline_books = db.online_books.find({"authors": "@sachonline"})
book_ids = [b["book_id"] for b in sachonline_books]

chapters_without_slug = list(
    db.book_chapters.find({"book_id": {"$in": book_ids}, "slug": {"$exists": False}})
)

print(f"\n@sachonline chapters WITHOUT slug: {len(chapters_without_slug)}")
for ch in chapters_without_slug:
    print(
        f"  - {ch.get('title', 'N/A')}: chapter_number={ch.get('chapter_number', 'N/A')}"
    )
