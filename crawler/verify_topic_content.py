#!/usr/bin/env python3
"""
Verify conversation content matches topics
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
import random


def main():
    db_manager = DBManager()
    db = db_manager.db

    print("🔍 CONTENT VERIFICATION - Random Sample from Each Level:")
    print("=" * 80)

    # Test topics from each level
    test_topics = [
        (3, "family_relationships", "beginner"),
        (5, "shopping", "beginner"),
        (13, "education_learning", "intermediate"),
        (18, "finance_money", "intermediate"),
        (22, "law_justice", "advanced"),
    ]

    for topic_num, expected_slug, expected_level in test_topics:
        # Get a random conversation from this topic
        convs = list(db.conversation_library.find({"topic_number": topic_num}).limit(2))

        if not convs:
            print(f"\n❌ Topic {topic_num}: No conversations found!")
            continue

        conv = random.choice(convs)

        print(f"\n{'=' * 80}")
        print(f"📝 Topic {topic_num}: {expected_slug} ({expected_level})")
        print(f"{'=' * 80}")
        print(f"Conversation ID: {conv.get('conversation_id')}")
        print(
            f"Actual slug: {conv.get('topic_slug')} ✅"
            if conv.get("topic_slug") == expected_slug
            else f"Actual slug: {conv.get('topic_slug')} ❌"
        )
        print(
            f"Actual level: {conv.get('level')} ✅"
            if conv.get("level") == expected_level
            else f"Actual level: {conv.get('level')} ❌"
        )
        print(f"\nTitle: {conv.get('title', {}).get('en')}")
        print(f"       {conv.get('title', {}).get('vi')}")
        print(f"Audio: {'✅ Available' if conv.get('audio_url') else '❌ Missing'}")

        dialogue = conv.get("dialogue", [])
        print(f"\nDialogue ({len(dialogue)} lines):")

        # Show full dialogue
        for i, line in enumerate(dialogue, 1):
            speaker = line.get("speaker", "Unknown")
            text_en = line.get("text_en", "N/A")
            text_vi = line.get("text_vi", "N/A")
            print(f"  {i:2d}. [{speaker}] {text_en}")
            print(f"      → {text_vi}")

        # Quick content check - does it match the topic?
        print(f"\n✅ Content Check:")
        topic_keywords = {
            "family_relationships": [
                "family",
                "mother",
                "father",
                "sister",
                "brother",
                "parent",
                "child",
                "relative",
            ],
            "shopping": [
                "buy",
                "shop",
                "price",
                "cost",
                "store",
                "purchase",
                "pay",
                "sale",
            ],
            "education_learning": [
                "school",
                "study",
                "learn",
                "class",
                "student",
                "teacher",
                "homework",
                "exam",
            ],
            "finance_money": [
                "money",
                "bank",
                "account",
                "invest",
                "save",
                "budget",
                "financial",
                "payment",
            ],
            "law_justice": [
                "law",
                "legal",
                "court",
                "judge",
                "attorney",
                "crime",
                "justice",
                "police",
            ],
        }

        keywords = topic_keywords.get(expected_slug, [])
        full_text = " ".join([line.get("text_en", "").lower() for line in dialogue])
        found_keywords = [kw for kw in keywords if kw in full_text]

        if found_keywords:
            print(f"   Found topic keywords: {', '.join(found_keywords)}")
        else:
            print(f"   ⚠️ No obvious topic keywords found - manual review recommended")


if __name__ == "__main__":
    main()
