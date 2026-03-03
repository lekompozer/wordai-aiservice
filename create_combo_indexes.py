"""
Create MongoDB indexes for book_combos and combo_purchases collections.
Run once after deploying the combo book feature.

Usage (on server):
    docker cp create_combo_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_combo_indexes.py
"""

import sys
import os

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db


def create_indexes():
    print("Creating indexes for book_combos collection...")

    # Unique combo_id lookup
    db.book_combos.create_index("combo_id", unique=True, name="combo_id_unique")
    print("  ✅ combo_id (unique)")

    # Owner's combos (active or all)
    db.book_combos.create_index(
        [("owner_user_id", 1), ("is_deleted", 1)],
        name="owner_is_deleted",
    )
    print("  ✅ (owner_user_id, is_deleted)")

    # Public listing: published + not deleted
    db.book_combos.create_index(
        [("is_published", 1), ("is_deleted", 1), ("created_at", -1)],
        name="published_not_deleted_date",
    )
    print("  ✅ (is_published, is_deleted, created_at)")

    # Text search on title / description
    db.book_combos.create_index(
        [("title", "text"), ("description", "text")],
        name="combo_text_search",
    )
    print("  ✅ text index (title, description)")

    print("\nCreating indexes for combo_purchases collection...")

    # Unique purchase_id
    db.combo_purchases.create_index(
        "purchase_id", unique=True, name="purchase_id_unique"
    )
    print("  ✅ purchase_id (unique)")

    # User's purchase history, newest first
    db.combo_purchases.create_index(
        [("user_id", 1), ("purchased_at", -1)],
        name="user_purchased_at",
    )
    print("  ✅ (user_id, purchased_at)")

    # User + combo_id lookup (prevent duplicate lifetime purchase)
    db.combo_purchases.create_index(
        [("user_id", 1), ("combo_id", 1)],
        name="user_combo_id",
    )
    print("  ✅ (user_id, combo_id)")

    # Array index on book_ids_snapshot for $elemMatch queries
    db.combo_purchases.create_index(
        "book_ids_snapshot",
        name="book_ids_snapshot_array",
    )
    print("  ✅ book_ids_snapshot (array index)")

    print("\n✅ All combo indexes created successfully.")


if __name__ == "__main__":
    create_indexes()
