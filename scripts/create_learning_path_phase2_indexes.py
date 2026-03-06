"""
Phase 2 Learning Path — Index Creation Script
==============================================
Creates MongoDB indexes for the Smart Learning Path collections
introduced in Phase 2 of the implementation.

Collections touched:
  - user_learning_profile
  - user_learning_path

Run on production (no rebuild needed):
  docker cp /home/hoile/wordai/create_learning_path_phase2_indexes.py ai-chatbot-rag:/app/
  docker exec ai-chatbot-rag python3 /app/create_learning_path_phase2_indexes.py
"""

from datetime import datetime

from pymongo import ASCENDING, DESCENDING

from src.database.db_manager import DBManager


def create_indexes():
    db_manager = DBManager()
    db = db_manager.db
    results = []

    print(f"[{datetime.now().isoformat()}] Connected to {db.name}")

    # ── user_learning_profile ──────────────────────────────────────────────
    profile = db["user_learning_profile"]

    idx = profile.create_index(
        [("user_id", ASCENDING)],
        unique=True,
        name="user_profile_unique",
        background=True,
    )
    results.append(("user_learning_profile", idx))

    idx = profile.create_index(
        [("user_id", ASCENDING), ("progression_level", ASCENDING)],
        name="user_progression_level",
        background=True,
    )
    results.append(("user_learning_profile", idx))

    # ── user_learning_path ─────────────────────────────────────────────────
    path = db["user_learning_path"]

    idx = path.create_index(
        [("path_id", ASCENDING)],
        unique=True,
        name="path_id_unique",
        background=True,
    )
    results.append(("user_learning_path", idx))

    idx = path.create_index(
        [("user_id", ASCENDING), ("is_active", ASCENDING)],
        name="user_active_path",
        background=True,
    )
    results.append(("user_learning_path", idx))

    idx = path.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="user_path_history",
        background=True,
    )
    results.append(("user_learning_path", idx))

    # Subdoc lookup for path item completion updates
    idx = path.create_index(
        [("user_id", ASCENDING), ("path_items.conversation_id", ASCENDING)],
        name="user_path_item_conv",
        background=True,
    )
    results.append(("user_learning_path", idx))

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n✅ Created / confirmed {len(results)} indexes:")
    for col, name in results:
        print(f"   [{col}] {name}")

    print(f"\n[{datetime.now().isoformat()}] Done.")


if __name__ == "__main__":
    create_indexes()
