"""
Check chi tiết nội dung conversations trong database
So sánh data đúng vs sai
"""

from src.database.db_manager import DBManager
from crawler.conversations_data import get_conversations_by_topic


def main():
    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("CHECK CONVERSATIONS ĐÚNG vs SAI")
    print("=" * 80)

    # 1. Check 1 conversation ĐÚNG (Topic 1, Index 1)
    print("\n📗 CONVERSATION ĐÚNG - Topic 1, Index 1:")
    print("-" * 80)
    correct = db.conversation_library.find_one(
        {"topic_number": 1, "conversation_index": 1}
    )
    if correct:
        print(f"  Conversation ID: {correct['conversation_id']}")
        print(f"  Topic: {correct['topic_number']} - {correct.get('topic_en')}")
        print(f"  Level: {correct.get('level')}")
        print(f"  Index: {correct['conversation_index']} ✅ (Correct range: 1-20)")
        print(f"  Title EN: {correct.get('title_en')}")
        print(f"  Title VI: {correct.get('title_vi')}")
        dialogue = correct.get("dialogue", [])
        print(
            f"  Has dialogue: {'YES (' + str(len(dialogue)) + ' lines)' if dialogue else 'NO'}"
        )
        if dialogue:
            print(f"  First line: {dialogue[0].get('text', '')[:50]}...")

    # 2. Check 1 conversation SAI (Topic 3, Index 21)
    print("\n📕 CONVERSATION SAI - Topic 3, Index 21 (should be 1-20):")
    print("-" * 80)
    wrong = db.conversation_library.find_one(
        {"topic_number": 3, "conversation_index": 21}
    )
    if wrong:
        print(f"  Conversation ID: {wrong['conversation_id']}")
        print(f"  Topic: {wrong['topic_number']} - {wrong.get('topic_en')}")
        print(f"  Level: {wrong.get('level')}")
        print(f"  Index: {wrong['conversation_index']} ❌ (Should be 1-20, not 21!)")
        print(f"  Title EN: {wrong.get('title_en')}")
        print(f"  Title VI: {wrong.get('title_vi')}")
        dialogue = wrong.get("dialogue", [])
        print(
            f"  Has dialogue: {'YES (' + str(len(dialogue)) + ' lines)' if dialogue else 'NO'}"
        )
        if dialogue:
            print(f"  First line: {dialogue[0].get('text', '')[:50]}...")
    else:
        print("  NOT FOUND")

    # 3. Phân bố index
    print("\n📊 PHÂN BỐ INDEX:")
    print("-" * 80)
    ranges = [
        ("001-020 (ĐÚNG)", 1, 20),
        ("021-040 (SAI)", 21, 40),
        ("041-100 (SAI)", 41, 100),
        ("101-200 (SAI)", 101, 200),
        ("201-400 (SAI)", 201, 400),
        ("401+ (SAI)", 401, 10000),
    ]

    for name, min_idx, max_idx in ranges:
        count = db.conversation_library.count_documents(
            {"conversation_index": {"$gte": min_idx, "$lte": max_idx}}
        )
        status = "✅" if "ĐÚNG" in name else "❌"
        print(f"  {status} {name}: {count} conversations")

    # 4. So sánh với file conversations_data.py
    print("\n📋 SO SÁNH VỚI FILE conversations_data.py:")
    print("-" * 80)

    # Topic 1 - should match
    print("\n  Topic 1 (Should match):")
    file_convs_1 = get_conversations_by_topic(1)
    db_convs_1 = list(
        db.conversation_library.find(
            {"topic_number": 1},
            {"conversation_id": 1, "conversation_index": 1, "title_en": 1},
        ).sort("conversation_index", 1)
    )

    print(f"    File: {len(file_convs_1)} conversations")
    print(f"    DB:   {len(db_convs_1)} conversations")

    if len(file_convs_1) == len(db_convs_1) == 20:
        print("    ✅ Count matches!")
        # Check first 3
        for i in range(3):
            file_conv = file_convs_1[i]
            db_conv = db_convs_1[i]
            match = "✅" if file_conv["title_en"] == db_conv.get("title_en") else "❌"
            print(f"      {match} [{i+1:02d}] File: {file_conv['title_en']}")
            print(f"           DB:   {db_conv.get('title_en', 'N/A')}")

    # Topic 3 - should NOT match (DB has wrong indexes)
    print("\n  Topic 3 (DB has WRONG indexes):")
    file_convs_3 = get_conversations_by_topic(3)
    db_convs_3 = list(
        db.conversation_library.find(
            {"topic_number": 3},
            {"conversation_id": 1, "conversation_index": 1, "title_en": 1},
        ).sort("conversation_index", 1)
    )

    print(f"    File: {len(file_convs_3)} conversations (index 1-20)")
    print(f"    DB:   {len(db_convs_3)} conversations")

    if db_convs_3:
        print(
            f"    ❌ DB indexes: {db_convs_3[0]['conversation_index']} - {db_convs_3[-1]['conversation_index']}"
        )
        print(f"    ❌ Should be: 1 - 20")

        # Show first 3 DB conversations
        print("\n    First 3 in DB:")
        for db_conv in db_convs_3[:3]:
            print(
                f"      [{db_conv['conversation_index']:03d}] {db_conv.get('title_en', 'N/A')}"
            )

    # 5. Count conversations to DELETE
    print("\n🗑️  CONVERSATIONS CẦN XÓA:")
    print("-" * 80)
    to_delete = db.conversation_library.count_documents(
        {"conversation_index": {"$gt": 20}}
    )
    print(f"  Total: {to_delete} conversations với index > 20")

    # Group by topic
    print("\n  By topic:")
    for topic_num in range(1, 31):
        count = db.conversation_library.count_documents(
            {"topic_number": topic_num, "conversation_index": {"$gt": 20}}
        )
        if count > 0:
            print(f"    Topic {topic_num:02d}: {count} conversations to delete")

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    total = db.conversation_library.count_documents({})
    correct_count = db.conversation_library.count_documents(
        {"conversation_index": {"$gte": 1, "$lte": 20}}
    )
    wrong_count = to_delete

    print(f"  Total in DB: {total}")
    print(f"  ✅ Correct (index 1-20): {correct_count}")
    print(f"  ❌ Wrong (index > 20): {wrong_count}")
    print(f"  Expected after cleanup: 600 (30 topics × 20)")
    print(f"  Missing after cleanup: {600 - correct_count}")


if __name__ == "__main__":
    main()
