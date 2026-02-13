#!/usr/bin/env python3
"""
Check actual dialogue structure in database
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
import json


def main():
    db_manager = DBManager()
    db = db_manager.db

    # Get one conversation to see actual structure
    conv = db.conversation_library.find_one({"topic_number": 6})

    print("📋 RAW CONVERSATION STRUCTURE:")
    print("=" * 80)
    print(f'ID: {conv.get("conversation_id")}')
    print(f'Topic: {conv.get("topic_slug")} ({conv.get("level")})')
    print(f'Title EN: {conv.get("title", {}).get("en")}')
    print(f'Title VI: {conv.get("title", {}).get("vi")}')

    dialogue = conv.get("dialogue", [])
    if dialogue:
        print(f"\nDialogue has {len(dialogue)} lines")
        print(f"First dialogue entry keys: {list(dialogue[0].keys())}")
        print(f"\nFirst 3 dialogue entries:")
        for i, entry in enumerate(dialogue[:3]):
            print(f"\n  [{i+1}] Full entry:")
            print(json.dumps(entry, indent=4, ensure_ascii=False))
    else:
        print("\n❌ No dialogue found!")

    # Check a few more random topics
    print("\n" + "=" * 80)
    print("🔍 CHECKING MULTIPLE TOPICS:")
    print("=" * 80)

    for topic_num in [1, 11, 21]:  # One from each level
        conv = db.conversation_library.find_one({"topic_number": topic_num})
        if conv:
            print(
                f'\nTopic {topic_num}: {conv.get("topic_slug")} ({conv.get("level")})'
            )
            print(f'  Title: {conv.get("title", {}).get("en")}')
            dialogue = conv.get("dialogue", [])
            if dialogue and len(dialogue) > 0:
                print(f"  Dialogue lines: {len(dialogue)}")
                print(f"  First line keys: {list(dialogue[0].keys())}")
                print(
                    f'  Sample: {dialogue[0].get("text", dialogue[0].get("en", "N/A"))}'
                )
            else:
                print(f"  ❌ No dialogue!")


if __name__ == "__main__":
    main()
