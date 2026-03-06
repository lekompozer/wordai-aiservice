#!/usr/bin/env python3
"""
Migration: update book_page_audio indexes to include `language` field.

Old unique index: (book_id, voice_name, version)
New unique index: (book_id, voice_name, language, version)

Run once on the server after deploying the EN-VI audio support changes.
"""

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db
col = db["book_page_audio"]

print("Migrating book_page_audio indexes...")

# ── 1. Patch existing docs that are missing language field ────────────────────
result = col.update_many(
    {"language": {"$exists": False}},
    {"$set": {"language": "en"}},
)
print(f"  Patched {result.modified_count} docs missing language field → 'en'")

# ── 2. Drop old indexes ───────────────────────────────────────────────────────
for idx_name in ("book_id_voice_version_unique", "book_id_voice_version_desc"):
    try:
        col.drop_index(idx_name)
        print(f"  ✅ Dropped old index: {idx_name}")
    except Exception as e:
        print(f"  ⚠️  Could not drop {idx_name}: {e} (may not exist, OK)")

# ── 3. Create new indexes with language ──────────────────────────────────────
print("  Creating book_id_voice_lang_version_unique ...")
col.create_index(
    [("book_id", 1), ("voice_name", 1), ("language", 1), ("version", 1)],
    unique=True,
    name="book_id_voice_lang_version_unique",
)

print("  Creating book_id_voice_lang_version_desc ...")
col.create_index(
    [("book_id", 1), ("voice_name", 1), ("language", 1), ("version", -1)],
    name="book_id_voice_lang_version_desc",
)

# ── 4. Summary ────────────────────────────────────────────────────────────────
print("\n--- book_page_audio indexes ---")
for idx in col.list_indexes():
    print(f"  {idx['name']}: {idx['key']}")

print("\n✅ Migration complete!")
