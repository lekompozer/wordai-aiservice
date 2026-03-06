#!/usr/bin/env python3
"""
Fix conversation duplicates and identify missing conversations
1. Find and delete duplicate conversations
2. List exact missing conversations
3. Generate missing conversations with DeepSeek
"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager
from crawler.parse_600_conversations import parse_topic_conversation_file


def build_expected_conversation_id(conv):
    """Build conversation_id from parsed conversation"""
    # Format: conv_{level}_{topic_slug}_{topic_number:02d}_{index:03d}
    return f"conv_{conv['level']}_{conv['topic_slug']}_{conv['topic_number']:02d}_{conv['conversation_index']:03d}"


def main():
    # Parse expected conversations from file
    file_path = "/app/docs/wordai/Learn English With Songs/Topic Conversation.md"
    expected_convs = parse_topic_conversation_file(file_path)

    print(f"📖 Expected from file: {len(expected_convs)} conversations")

    # Build set of expected conversation IDs
    expected_ids = set()
    expected_map = {}  # conversation_id -> conversation data

    for conv in expected_convs:
        conv_id = build_expected_conversation_id(conv)
        expected_ids.add(conv_id)
        expected_map[conv_id] = conv

    print(f"✅ Built {len(expected_ids)} expected conversation IDs")
    print()

    # Get conversations from database
    db_manager = DBManager()
    db = db_manager.db

    db_convs = list(
        db.conversation_library.find(
            {},
            {
                "conversation_id": 1,
                "topic_number": 1,
                "topic_slug": 1,
                "conversation_index": 1,
                "level": 1,
                "title_en": 1,
                "created_at": 1,
            },
        ).sort([("topic_number", 1), ("conversation_index", 1)])
    )

    print(f"📊 Database: {len(db_convs)} conversations")
    print()

    # Build set of DB conversation IDs
    db_ids = set()
    db_map = {}
    duplicates_by_id = {}  # conversation_id -> list of MongoDB _id

    for conv in db_convs:
        conv_id = conv["conversation_id"]
        db_ids.add(conv_id)

        # Track duplicates
        if conv_id not in duplicates_by_id:
            duplicates_by_id[conv_id] = []
        duplicates_by_id[conv_id].append(conv)

    # Find duplicates
    duplicates = {k: v for k, v in duplicates_by_id.items() if len(v) > 1}

    if duplicates:
        print("=" * 70)
        print(f"🔍 FOUND {len(duplicates)} DUPLICATE CONVERSATION IDs")
        print("=" * 70)

        total_extra = 0
        for conv_id, conv_list in sorted(duplicates.items()):
            print(f"\n{conv_id}: {len(conv_list)} copies")
            for i, conv in enumerate(conv_list):
                created = conv.get("created_at", "Unknown")
                print(f"   [{i+1}] _id: {conv['_id']}, created: {created}")

            total_extra += len(conv_list) - 1

        print(f"\n⚠️  Total extra (duplicate) documents: {total_extra}")
        print()

        # Ask to delete duplicates (keep oldest by created_at)
        print("=" * 70)
        print("DELETE DUPLICATES (Keep oldest, delete newer)")
        print("=" * 70)

        deleted_count = 0
        for conv_id, conv_list in duplicates.items():
            # Sort by created_at, keep first (oldest)
            sorted_convs = sorted(conv_list, key=lambda x: x.get("created_at", ""))
            to_delete = sorted_convs[1:]  # Delete all except first

            for conv in to_delete:
                db.conversation_library.delete_one({"_id": conv["_id"]})
                deleted_count += 1
                print(f"❌ Deleted: {conv_id} (_id: {conv['_id']})")

        print(f"\n✅ Deleted {deleted_count} duplicate conversations")
        print()
    else:
        print("✅ No duplicates found")
        print()

    # Re-fetch DB after deletion
    db_convs_clean = list(db.conversation_library.find({}, {"conversation_id": 1}))
    db_ids_clean = {conv["conversation_id"] for conv in db_convs_clean}

    print(f"📊 Database after cleanup: {len(db_ids_clean)} conversations")
    print()

    # Find missing conversations
    missing_ids = expected_ids - db_ids_clean
    extra_ids = db_ids_clean - expected_ids

    if missing_ids:
        print("=" * 70)
        print(f"❌ MISSING {len(missing_ids)} CONVERSATIONS")
        print("=" * 70)

        # Group by topic
        missing_by_topic = {}
        for conv_id in sorted(missing_ids):
            conv_data = expected_map[conv_id]
            topic = conv_data["topic_number"]
            if topic not in missing_by_topic:
                missing_by_topic[topic] = []
            missing_by_topic[topic].append(conv_data)

        for topic in sorted(missing_by_topic.keys()):
            convs = missing_by_topic[topic]
            print(f"\nTopic {topic}: {len(convs)} missing")
            for conv in sorted(convs, key=lambda x: x["conversation_index"]):
                print(f"   - [{conv['conversation_index']:03d}] {conv['title_en']}")

        # Write missing conversations to file for DeepSeek generation
        import json

        missing_list = []
        for conv_id in sorted(missing_ids):
            conv_data = expected_map[conv_id]
            missing_list.append(
                {
                    "conversation_id": conv_id,
                    "topic_number": conv_data["topic_number"],
                    "topic_slug": conv_data["topic_slug"],
                    "topic_en": conv_data["topic_en"],
                    "topic_vi": conv_data["topic_vi"],
                    "conversation_index": conv_data["conversation_index"],
                    "title_en": conv_data["title_en"],
                    "title_vi": conv_data["title_vi"],
                    "level": conv_data["level"],
                }
            )

        with open("/tmp/missing_conversations.json", "w") as f:
            json.dump(missing_list, f, indent=2, ensure_ascii=False)

        print(
            f"\n✅ Saved missing conversations list to: /tmp/missing_conversations.json"
        )

    if extra_ids:
        print("\n" + "=" * 70)
        print(f"⚠️  EXTRA {len(extra_ids)} CONVERSATIONS (not in file)")
        print("=" * 70)
        for conv_id in sorted(extra_ids):
            print(f"   - {conv_id}")
        print("\n⚠️  These should be deleted manually if they are mistakes")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Expected: {len(expected_ids)}")
    print(f"Database (clean): {len(db_ids_clean)}")
    print(f"Missing: {len(missing_ids)}")
    print(f"Extra: {len(extra_ids)}")

    if len(missing_ids) == 0 and len(extra_ids) == 0:
        print("\n✅ PERFECT MATCH - Database has exactly 600 correct conversations!")
    else:
        print("\n❌ MISMATCH - Need to fix")


if __name__ == "__main__":
    main()
