"""
Update online_books documents with correct LetsRead masterBookIds.

The masterBookIds were discovered via Chrome DevTools network capture looking
at the Preview API calls made by letsreadasia.org.

These were previously incorrect (using cover image CDN UUID instead of masterBookId).

Run on prod server:
    docker cp update_letsread_book_ids.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/update_letsread_book_ids.py
"""

import re
from datetime import datetime
from src.database.db_manager import DBManager


LETSREAD_BOOK_IDS = [
    {
        "title_hint": "The Protectors",
        "letsread_book_id": "61b2f862-f64b-443b-9f6c-73f71024b538",
        "letsread_lang_id": "4846240843956224",
    },
    {
        "title_hint": "The Spirit of Ocean Nights",
        "letsread_book_id": "eb4d3602-f4fb-4cae-a574-a838980af834",
        "letsread_lang_id": "4846240843956224",
    },
    {
        "title_hint": "Roots Are Stronger Than Steel",
        "letsread_book_id": "617336b6-6033-4a2d-9ac9-72587cb75574",
        "letsread_lang_id": "4846240843956224",
    },
    {
        "title_hint": "Children of the Sun and Stars",
        "letsread_book_id": "830e07c9-9c5e-4c12-9f5a-b2e538554be1",
        "letsread_lang_id": "4846240843956224",
    },
]


def update_books():
    db_manager = DBManager()
    db = db_manager.db

    ok = 0
    fail = 0

    for entry in LETSREAD_BOOK_IDS:
        title_hint = entry["title_hint"]
        pattern = re.compile(re.escape(title_hint), re.IGNORECASE)
        book = db.online_books.find_one({"title": {"$regex": pattern}})

        if not book:
            print(f"  ❌ Not found: '{title_hint}'")
            fail += 1
            continue

        result = db.online_books.update_one(
            {"_id": book["_id"]},
            {
                "$set": {
                    "metadata.letsread_book_id": entry["letsread_book_id"],
                    "metadata.letsread_lang_id": entry["letsread_lang_id"],
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        print(
            f"  ✅ Updated '{book['title']}' (_id={book['_id']}) "
            f"→ {entry['letsread_book_id']}"
            f" (modified: {result.modified_count})"
        )
        ok += 1

    print(f"\n✅ Done: {ok} updated, {fail} not found")


if __name__ == "__main__":
    update_books()
