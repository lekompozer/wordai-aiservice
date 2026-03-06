"""
Phase 1 Learning Path — Index Creation Script
==============================================
Creates MongoDB indexes for the new Dual-Part completion system fields
added in Phase 1 of the Smart Learning Path implementation.

Collections touched:
  - user_conversation_progress
  - user_learning_profile
  - conversation_library

Run on production:
  docker cp create_learning_path_indexes.py ai-chatbot-rag:/app/
  docker exec ai-chatbot-rag python3 /app/create_learning_path_indexes.py
"""

from datetime import datetime

from pymongo import ASCENDING, DESCENDING

from src.database.db_manager import DBManager


def create_indexes():
    db_manager = DBManager()
    db = db_manager.db
    results = []

    print(f"[{datetime.now().isoformat()}] Connected to {db.name}")

    # ── user_conversation_progress ─────────────────────────────────────────
    progress = db["user_conversation_progress"]

    # Core lookup: user's progress on a conversation
    idx = progress.create_index(
        [("user_id", ASCENDING), ("conversation_id", ASCENDING)],
        unique=True,
        name="user_conversation_unique",
        background=True,
    )
    results.append(("user_conversation_progress", idx))

    # Dual-part completion queries (e.g. "how many fully completed?")
    idx = progress.create_index(
        [("user_id", ASCENDING), ("is_completed", ASCENDING)],
        name="user_is_completed",
        background=True,
    )
    results.append(("user_conversation_progress", idx))

    # Gap-only completed (for dual_part stats)
    idx = progress.create_index(
        [
            ("user_id", ASCENDING),
            ("gap_completed", ASCENDING),
            ("test_completed", ASCENDING),
        ],
        name="user_gap_test_completed",
        background=True,
    )
    results.append(("user_conversation_progress", idx))

    # Best score + difficulty (leaderboard / progress view)
    idx = progress.create_index(
        [
            ("user_id", ASCENDING),
            ("gap_difficulty", ASCENDING),
            ("gap_best_score", DESCENDING),
        ],
        name="user_difficulty_best_score",
        background=True,
    )
    results.append(("user_conversation_progress", idx))

    # ── user_learning_profile ──────────────────────────────────────────────
    profile = db["user_learning_profile"]

    # Primary lookup
    idx = profile.create_index(
        [("user_id", ASCENDING)],
        unique=True,
        name="user_profile_unique",
        background=True,
    )
    results.append(("user_learning_profile", idx))

    # Streak cache fast-path
    idx = profile.create_index(
        [("user_id", ASCENDING), ("current_streak", DESCENDING)],
        name="user_current_streak",
        background=True,
    )
    results.append(("user_learning_profile", idx))

    # XP rank queries
    idx = profile.create_index(
        [("total_xp", DESCENDING)],
        name="total_xp_rank",
        background=True,
    )
    results.append(("user_learning_profile", idx))

    # ── conversation_library ───────────────────────────────────────────────
    conv = db["conversation_library"]

    # Test-linked-to-conversation lookup (used in submit_test event push)
    idx = conv.create_index(
        [("online_test_id", ASCENDING)],
        name="online_test_id",
        background=True,
        sparse=True,  # many conversations don't have a test
    )
    results.append(("conversation_library", idx))

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n✅ Created / confirmed {len(results)} indexes:")
    for col, name in results:
        print(f"   [{col}] {name}")

    print(f"\n[{datetime.now().isoformat()}] Done.")


if __name__ == "__main__":
    create_indexes()
