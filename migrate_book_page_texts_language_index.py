#!/usr/bin/env python3
"""
Migration: Update book_page_texts unique index to include language field.
Old: (book_id, page_number) UNIQUE
New: (book_id, page_number, language) UNIQUE

Run inside the Docker container:
  docker exec ai-chatbot-rag python3 /app/migrate_book_page_texts_language_index.py
"""

import sys
import logging
sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

from src.database.db_manager import DBManager
from pymongo import ASCENDING

def main():
    db_manager = DBManager()
    db = db_manager.db
    col = db.book_page_texts

    print("Migrating book_page_texts indexes...")

    # 1. Patch existing docs that are missing language field
    result = col.update_many(
        {"language": {"$exists": False}},
        {"$set": {"language": "en"}}
    )
    print(f"  Patched {result.modified_count} docs missing language field → 'en'")

    # 2. List current indexes
    existing = {idx["name"]: idx for idx in col.list_indexes()}
    print(f"  Current indexes: {list(existing.keys())}")

    # 3. Drop old unique index (book_id + page_number only)
    for name, idx in existing.items():
        key_fields = list(idx.get("key", {}).keys())
        if "book_id" in key_fields and "page_number" in key_fields and "language" not in key_fields:
            if idx.get("unique"):
                print(f"  Dropping old unique index: {name}")
                col.drop_index(name)

    # 4. Create new unique index with language
    print("  Creating book_id_page_number_language_unique ...")
    col.create_index(
        [("book_id", ASCENDING), ("page_number", ASCENDING), ("language", ASCENDING)],
        unique=True,
        name="book_id_page_number_language_unique"
    )

    print("\n--- book_page_texts indexes after migration ---")
    for idx in col.list_indexes():
        print(f"  {idx['name']}: {idx['key']}")

    print("\n✅ Migration complete!")

if __name__ == "__main__":
    main()
