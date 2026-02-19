"""
Phase 1 Learning Path — Completion Status Migration
====================================================
Backfills the new Phase 1 fields on existing `user_conversation_progress`
documents that were created before the Dual-Part system went live.

New fields backfilled:
  gap_completed   bool    True if the user ever scored ≥ 70% on gap exercise
  gap_best_score  float   Highest score (0-100) across all gap attempts
  gap_difficulty  str     "easy"|"medium"|"hard" (inferred from conversation_library)
  test_completed  bool    True if the user ever scored ≥ 80% on linked online test
  test_best_score float   Highest score (0-100) across all test attempts

Strategy:
  1. Iterate all existing progress docs that DON'T have gap_completed field
  2. Look up their gap attempts in conversation_attempts collection
  3. Look up their test submissions in test_submissions (via conversation_library.online_test_id)
  4. Backfill the fields with a bulk_write

Run on production (no rebuild needed):
  scp create (already on server from git pull)
  docker cp /home/hoile/wordai/migrate_completion_status.py ai-chatbot-rag:/app/
  docker exec ai-chatbot-rag python3 /app/migrate_completion_status.py

NOTE: Script is idempotent — re-running is safe (skips already-migrated docs).
"""

from datetime import datetime
from pymongo import UpdateOne

from src.database.db_manager import DBManager

BATCH_SIZE = 500
GAP_PASS_THRESHOLD = 70.0
TEST_PASS_THRESHOLD = 80.0


def migrate():
    db_manager = DBManager()
    db = db_manager.db

    progress_col = db["user_conversation_progress"]
    attempts_col = db["conversation_attempts"]
    submissions_col = db["test_submissions"]
    conv_col = db["conversation_library"]

    print(
        f"[{datetime.now().isoformat()}] Starting Phase 1 completion status migration…"
    )

    # Build conversation → difficulty + online_test_id map (once, in memory)
    print("  Loading conversation metadata…")
    conv_meta: dict[str, dict] = {}
    for c in conv_col.find(
        {},
        projection={"conversation_id": 1, "level": 1, "online_test_id": 1, "_id": 0},
    ):
        cid = c.get("conversation_id")
        if cid:
            conv_meta[cid] = {
                "level": c.get("level", "beginner"),
                "online_test_id": (
                    str(c["online_test_id"]) if c.get("online_test_id") else None
                ),
            }

    # Map level → difficulty
    def level_to_difficulty(level: str) -> str:
        lvl = (level or "").lower()
        if lvl in ("advanced", "hard"):
            return "hard"
        if lvl in ("intermediate", "medium"):
            return "medium"
        return "easy"

    # Filter: docs that haven't been migrated yet
    query = {"gap_completed": {"$exists": False}}
    total = progress_col.count_documents(query)
    print(f"  Found {total} progress docs to migrate")

    if total == 0:
        print("  ✅ Nothing to migrate — all docs already have gap_completed field.")
        client.close()
        return

    migrated = 0
    skipped = 0
    ops: list[UpdateOne] = []

    cursor = progress_col.find(query, no_cursor_timeout=True)
    try:
        for doc in cursor:
            user_id = doc.get("user_id")
            conversation_id = doc.get("conversation_id")

            if not user_id or not conversation_id:
                skipped += 1
                continue

            meta = conv_meta.get(conversation_id, {})
            difficulty = level_to_difficulty(meta.get("level", "beginner"))

            # ── Gap exercise history ──────────────────────────────────────
            gap_attempts = list(
                attempts_col.find(
                    {"user_id": user_id, "conversation_id": conversation_id},
                    projection={"score": 1, "_id": 0},
                )
            )
            gap_scores = [
                float(a.get("score", 0))
                for a in gap_attempts
                if a.get("score") is not None
            ]
            gap_best_score = max(gap_scores) if gap_scores else 0.0
            gap_completed = gap_best_score >= GAP_PASS_THRESHOLD

            # ── Online test history ────────────────────────────────────────
            online_test_id = meta.get("online_test_id")
            test_best_score = 0.0
            test_completed = False

            if online_test_id:
                test_subs = list(
                    submissions_col.find(
                        {"user_id": user_id, "test_id": online_test_id},
                        projection={"score_percentage": 1, "_id": 0},
                    )
                )
                test_scores = [
                    float(s.get("score_percentage", 0))
                    for s in test_subs
                    if s.get("score_percentage") is not None
                ]
                test_best_score = max(test_scores) if test_scores else 0.0
                test_completed = test_best_score >= TEST_PASS_THRESHOLD

            # Dual-part: fully completed only when BOTH parts done
            is_fully_completed = gap_completed and test_completed
            # If test score is missing (no test linked), treat gap-only as completed
            if not online_test_id and gap_completed:
                is_fully_completed = True
                test_completed = True  # no test → consider fulfilled

            ops.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "gap_completed": gap_completed,
                            "gap_best_score": gap_best_score,
                            "gap_difficulty": difficulty,
                            "test_completed": test_completed,
                            "test_best_score": test_best_score,
                            "is_completed": is_fully_completed,
                            "migrated_at": datetime.utcnow().isoformat(),
                        }
                    },
                )
            )
            migrated += 1

            if len(ops) >= BATCH_SIZE:
                result = progress_col.bulk_write(ops, ordered=False)
                print(
                    f"  Batch written: {result.modified_count} updated "
                    f"(total so far: {migrated})"
                )
                ops = []

    finally:
        cursor.close()

    if ops:
        result = progress_col.bulk_write(ops, ordered=False)
        print(f"  Final batch: {result.modified_count} updated")

    print(
        f"\n✅ Migration complete — migrated: {migrated}, skipped: {skipped}\n"
        f"[{datetime.now().isoformat()}] Done."
    )


if __name__ == "__main__":
    migrate()
