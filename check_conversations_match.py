#!/usr/bin/env python3
"""
Check if conversations in database match with Topic Conversation.md file
"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager
from crawler.parse_600_conversations import parse_topic_conversation_file


def main():
    # Parse expected conversations from file
    file_path = "/app/docs/wordai/Learn English With Songs/Topic Conversation.md"
    expected_convs = parse_topic_conversation_file(file_path)

    print(f"📖 File Topic Conversation.md: {len(expected_convs)} conversations")
    print()

    # Count expected by topic
    expected_by_topic = {}
    for conv in expected_convs:
        topic = conv["topic_number"]
        if topic not in expected_by_topic:
            expected_by_topic[topic] = []
        expected_by_topic[topic].append(conv)

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
            },
        ).sort([("topic_number", 1), ("conversation_index", 1)])
    )

    print(f"📊 Database: {len(db_convs)} conversations")
    print()

    # Count by topic
    db_by_topic = {}
    for conv in db_convs:
        topic = conv.get("topic_number")
        if topic not in db_by_topic:
            db_by_topic[topic] = []
        db_by_topic[topic].append(conv)

    # Compare
    print("=" * 70)
    print("COMPARISON BY TOPIC")
    print("=" * 70)

    all_topics = sorted(set(list(expected_by_topic.keys()) + list(db_by_topic.keys())))

    missing_total = 0
    extra_total = 0

    for topic in all_topics:
        expected_count = len(expected_by_topic.get(topic, []))
        db_count = len(db_by_topic.get(topic, []))

        status = "✅" if expected_count == db_count else "❌"
        print(f"{status} Topic {topic}: Expected {expected_count}, DB {db_count}")

        if db_count < expected_count:
            missing = expected_count - db_count
            missing_total += missing
            print(f"   ⚠️  Missing {missing} conversations")
        elif db_count > expected_count:
            extra = db_count - expected_count
            extra_total += extra
            print(f"   ⚠️  Extra {extra} conversations")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Expected total: {len(expected_convs)}")
    print(f"Database total: {len(db_convs)}")
    print(f"Missing: {len(expected_convs) - len(db_convs)}")
    print(f"Extra: {max(0, len(db_convs) - len(expected_convs))}")

    if len(db_convs) == len(expected_convs):
        print()
        print("✅ DATABASE MATCHES FILE - All 600 conversations present!")
    else:
        print()
        print("❌ MISMATCH - Database does not match file")

        # Show which topics are incomplete
        if missing_total > 0:
            print()
            print("Topics with missing conversations:")
            for topic in all_topics:
                expected_count = len(expected_by_topic.get(topic, []))
                db_count = len(db_by_topic.get(topic, []))
                if db_count < expected_count:
                    print(f"   Topic {topic}: Need {expected_count - db_count} more")


if __name__ == "__main__":
    main()
