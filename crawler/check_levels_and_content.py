#!/usr/bin/env python3
"""
Check conversation levels and sample content to verify topics
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
import random


def main():
    db_manager = DBManager()
    db = db_manager.db

    print("📊 LEVELS DISTRIBUTION:")
    print("=" * 80)

    # Group by level
    levels = list(
        db.conversation_library.aggregate(
            [
                {
                    "$group": {
                        "_id": "$level",
                        "count": {"$sum": 1},
                        "topics": {"$addToSet": "$topic_number"},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
    )

    for level in levels:
        topics_sorted = sorted(level["topics"])
        print(f"\nLevel: {level['_id']}")
        print(f"  Conversations: {level['count']}")
        print(f"  Topics: {', '.join(map(str, topics_sorted))}")

    print("\n" + "=" * 80)
    print("📋 TOPICS WITH LEVELS:")
    print("=" * 80)

    # Group by topic
    topics = list(
        db.conversation_library.aggregate(
            [
                {
                    "$group": {
                        "_id": {
                            "topic_num": "$topic_number",
                            "topic_slug": "$topic_slug",
                            "level": "$level",
                        },
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id.topic_num": 1}},
            ]
        )
    )

    for t in topics:
        num = str(t["_id"]["topic_num"]).rjust(2)
        level = t["_id"]["level"].ljust(12)
        slug = t["_id"]["topic_slug"].ljust(30)
        print(f'Topic {num} | {level} | {slug} | {t["count"]} conversations')

    # Sample random conversations from different topics
    print("\n" + "=" * 80)
    print("🔍 SAMPLE CONTENT CHECK (Random Topics):")
    print("=" * 80)

    # Pick 5 random topics
    random_topics = random.sample(
        [t["_id"]["topic_num"] for t in topics], min(5, len(topics))
    )

    for topic_num in sorted(random_topics):
        print(f"\n{'=' * 80}")
        # Get one conversation from this topic
        conv = db.conversation_library.find_one({"topic_number": topic_num})
        if conv:
            print(
                f"📝 Topic {topic_num}: {conv.get('topic_slug', 'N/A')} ({conv.get('level', 'N/A')})"
            )
            print(f"   Conversation ID: {conv.get('conversation_id', 'N/A')}")
            print(f"   Title (EN): {conv.get('title', {}).get('en', 'N/A')}")
            print(f"   Title (VI): {conv.get('title', {}).get('vi', 'N/A')}")
            print(f"   Audio: {'✅' if conv.get('audio_url') else '❌'}")
            print(f"\n   Dialogue Preview (first 3 lines):")
            dialogue = conv.get("dialogue", [])
            for i, line in enumerate(dialogue[:3]):
                speaker = line.get("speaker", "Unknown")
                en = line.get("en", "N/A")
                vi = line.get("vi", "N/A")
                print(f"      {i+1}. [{speaker}] {en}")
                print(f"         → {vi}")

    # Check audio status
    print("\n" + "=" * 80)
    print("🎵 AUDIO STATUS:")
    print("=" * 80)
    total = db.conversation_library.count_documents({})
    with_audio = db.conversation_library.count_documents(
        {"audio_url": {"$exists": True, "$ne": None}}
    )
    without_audio = total - with_audio
    print(f"Total conversations: {total}")
    print(f"With audio: {with_audio} ({with_audio*100/total:.1f}%)")
    print(f"Without audio: {without_audio} ({without_audio*100/total:.1f}%)")


if __name__ == "__main__":
    main()
