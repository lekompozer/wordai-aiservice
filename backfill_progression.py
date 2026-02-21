"""
Backfill l1_completed & l1_counted_convs for users who have
gap_completed=True in user_conversation_progress but were missed
because events used the wrong Redis queue key.

Run via: docker cp + docker exec
"""

from src.database.db_manager import DBManager

db = DBManager().db

profile_col = db["user_learning_profile"]
progress_col = db["user_conversation_progress"]

profiles = list(
    profile_col.find(
        {},
        {
            "_id": 0,
            "user_id": 1,
            "progression_level": 1,
            "l1_counted_convs": 1,
            "l2_counted_convs": 1,
            "l3_counted_convs": 1,
        },
    )
)

print(f"Found {len(profiles)} profiles to check")

for profile in profiles:
    user_id = profile["user_id"]
    level = profile.get("progression_level", 1)
    counted_key = f"l{level}_counted_convs"
    counter_key = f"l{level}_completed"
    already_counted = set(profile.get(counted_key, []))

    # Find all gap-completed progress docs for this user
    gap_docs = list(
        progress_col.find(
            {"user_id": user_id, "gap_completed": True},
            {"conversation_id": 1, "gap_difficulty": 1, "_id": 0},
        )
    )

    new_convs = []
    for doc in gap_docs:
        cid = doc["conversation_id"]
        diff = doc.get("gap_difficulty", "easy")
        if cid in already_counted:
            continue

        # Level-gated check
        qualifies = False
        if level == 1:
            qualifies = True
        elif level == 2:
            qualifies = diff in ("medium", "hard")
        elif level == 3:
            qualifies = diff == "hard"

        if qualifies or True:  # always add to counted_convs even if not qualifying
            new_convs.append((cid, diff, qualifies))

    if not new_convs:
        print(f"  user={user_id}: nothing to backfill")
        continue

    qualifying = [c for c, d, q in new_convs if q]
    all_ids = [c for c, d, q in new_convs]

    print(
        f"  user={user_id} level={level}: {len(qualifying)} qualifying, {len(all_ids)} total new convs to mark counted"
    )

    if qualifying:
        profile_col.update_one(
            {"user_id": user_id},
            {
                "$inc": {counter_key: len(qualifying)},
                "$push": {counted_key: {"$each": all_ids}},
            },
        )
        print(
            f"    → incremented {counter_key} by {len(qualifying)}, added {len(all_ids)} to {counted_key}"
        )
    else:
        profile_col.update_one(
            {"user_id": user_id}, {"$push": {counted_key: {"$each": all_ids}}}
        )
        print(f"    → added {len(all_ids)} to {counted_key} (no qualifying count)")

print("\nBackfill complete!")

# Verify
for profile in profiles:
    uid = profile["user_id"]
    updated = profile_col.find_one(
        {"user_id": uid},
        {
            "l1_completed": 1,
            "l1_counted_convs": 1,
            "l2_completed": 1,
            "l3_completed": 1,
            "_id": 0,
        },
    )
    print(f"  {uid}: {updated}")
