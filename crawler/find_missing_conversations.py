"""Find missing conversations from the 600 total"""

import sys

sys.path.append("/app")

from src.database.db_manager import DBManager
from parse_600_conversations import parse_topic_conversation_file


def main():
    # Parse expected 600 conversations
    file_path = "docs/wordai/Learn English With Songs/Topic Conversation.md"
    print(f"📖 Parsing: {file_path}")
    conversations = parse_topic_conversation_file(file_path)
    print(f"✅ Expected: {len(conversations)} conversations")

    # Get existing conversation IDs from DB
    db_manager = DBManager()
    existing_ids = set(db_manager.db.conversation_library.distinct("conversation_id"))
    print(f"📊 In DB: {len(existing_ids)} conversations")
    print()

    # Find missing conversations
    missing = []
    for i, conv in enumerate(conversations, 1):
        # Use topic_slug from parsed data (already computed correctly)
        conv_id = f"conv_{conv['level'].value}_{conv['topic_slug']}_{conv['topic_number']:02d}_{i:03d}"

        if conv_id not in existing_ids:
            missing.append(
                {
                    "index": i,
                    "conv_id": conv_id,
                    "level": conv["level"].value,
                    "topic": conv["topic_en"],
                    "title": conv["title_en"],
                }
            )

    print(f"❌ Missing: {len(missing)} conversations")
    print()

    if missing:
        print("Missing conversation IDs:")
        print("-" * 80)
        for m in missing:
            print(f"  [{m['index']:3d}] {m['conv_id']}")
            print(f"        {m['level']:12s} | {m['topic']:30s} | {m['title']}")
        print("-" * 80)

        # Group by batch (every 3)
        batches_with_missing = set()
        for m in missing:
            batch_num = (m["index"] - 1) // 3 + 1
            batches_with_missing.add(batch_num)

        print()
        print(f"📦 Affected batches: {len(batches_with_missing)}")
        print(f"   Batch numbers: {sorted(batches_with_missing)}")
        print()

        # Save missing indices to file
        missing_indices = [m["index"] for m in missing]
        with open("/tmp/missing_indices.txt", "w") as f:
            f.write("\n".join(map(str, missing_indices)))
        print(f"💾 Saved missing indices to /tmp/missing_indices.txt")
    else:
        print("✅ All 600 conversations are in the database!")


if __name__ == "__main__":
    main()
