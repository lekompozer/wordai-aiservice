#!/usr/bin/env python3
"""
Update LetsRead book attribution: @letsreadasia -> @Storybook
Run inside the Docker container:
  docker exec ai-chatbot-rag python3 /app/update_letsread_attribution.py
"""

import sys
sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

def main():
    db_manager = DBManager()
    db = db_manager.db

    # Find all LetsRead books (identified by metadata.source)
    letsread_books = list(db.online_books.find(
        {"metadata.source": "letsreadasia.org"},
        {"_id": 1, "title": 1, "authors": 1}
    ))

    print(f"Found {len(letsread_books)} LetsRead book(s):")
    for book in letsread_books:
        print(f"  - {book['title']}  authors={book.get('authors')} _id={book['_id']}")

    # Update authors field for all LetsRead books
    result = db.online_books.update_many(
        {"metadata.source": "letsreadasia.org"},
        {
            "$set": {
                "authors": ["@Storybook"],
                "metadata.original_author": "Let's Read Asia",  # keep original attribution in metadata
                "metadata.uploaded_by": "@Storybook",
            }
        }
    )

    print(f"\nUpdated {result.modified_count} book(s) — authors set to ['@Storybook']")

    # Verify
    updated = list(db.online_books.find(
        {"metadata.source": "letsreadasia.org"},
        {"title": 1, "authors": 1}
    ))
    print("\nVerification:")
    for book in updated:
        print(f"  - {book['title']}  authors={book.get('authors')}")

if __name__ == "__main__":
    main()
