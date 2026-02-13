"""
Đánh lại index cho tất cả conversations trong database
Mỗi topic sẽ có index từ 001 -> N (N = số conversations của topic đó)
VD: Topic 15 có 32 convs → 001-032
    Topic 1 có 20 convs → 001-020
"""

import sys

sys.path.append("/app")

from src.database.db_manager import DBManager


def main():
    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("REINDEX ALL CONVERSATIONS")
    print("=" * 80)

    # Get all topics
    topics = db.conversation_library.distinct("topic_number")
    topics.sort()

    print(f"\n📁 Found {len(topics)} topics in database")

    total_updated = 0

    for topic_num in topics:
        # Get all conversations for this topic, sorted by current conversation_id
        convs = list(
            db.conversation_library.find({"topic_number": topic_num}).sort(
                "conversation_id", 1
            )
        )

        if not convs:
            continue

        # Get topic metadata from first conversation
        first_conv = convs[0]
        level = first_conv.get("level", "beginner")
        topic_slug = first_conv.get("topic_slug", f"topic_{topic_num}")

        print(f"\n{'='*80}")
        print(f"TOPIC {topic_num}: {topic_slug} ({level})")
        print(f"{'='*80}")
        print(f"Conversations: {len(convs)}")
        print(f"New index range: 001 → {len(convs):03d}")

        # Reindex each conversation
        for new_index, conv in enumerate(convs, 1):
            old_id = conv["conversation_id"]

            # Build new conversation_id
            # Format: conv_{level}_{slug}_{topic:02d}_{index:03d}
            new_id = f"conv_{level}_{topic_slug}_{topic_num:02d}_{new_index:03d}"

            if old_id != new_id:
                # Update conversation_id
                result = db.conversation_library.update_one(
                    {"_id": conv["_id"]}, {"$set": {"conversation_id": new_id}}
                )

                if result.modified_count > 0:
                    print(f"  [{new_index:03d}] {old_id} → {new_id}")
                    total_updated += 1
            else:
                print(f"  [{new_index:03d}] {new_id} (unchanged)")

        print(f"✅ Topic {topic_num}: Reindexed {len(convs)} conversations")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(
        f"Total conversations processed: {sum(db.conversation_library.count_documents({'topic_number': t}) for t in topics)}"
    )
    print(f"Total IDs updated: {total_updated}")
    print("✅ Reindexing complete!")


if __name__ == "__main__":
    main()
