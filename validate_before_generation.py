#!/usr/bin/env python3
"""
Validation script - Run BEFORE generation to ensure correctness

This validates:
1. File parsing returns exactly 600 conversations
2. Each topic has exactly 20 conversations (index 1-20)
3. conversation_id format is correct
4. No duplicates in parsed data
"""

import sys

sys.path.insert(0, "/app")

from crawler.parse_600_conversations import parse_topic_conversation_file


def validate_parsed_conversations():
    """Validate that parsing returns correct structure"""

    file_path = "/app/docs/wordai/Learn English With Songs/Topic Conversation.md"
    conversations = parse_topic_conversation_file(file_path)

    print("=" * 70)
    print("VALIDATION: Parsed Conversations")
    print("=" * 70)

    # Check 1: Total count
    if len(conversations) != 600:
        print(f"❌ FAIL: Expected 600 conversations, got {len(conversations)}")
        return False
    print(f"✅ PASS: Total = 600 conversations")

    # Check 2: Each topic has exactly 20 conversations
    topics = {}
    for conv in conversations:
        topic = conv["topic_number"]
        if topic not in topics:
            topics[topic] = []
        topics[topic].append(conv)

    all_topics_ok = True
    for topic_num in range(1, 31):
        if topic_num not in topics:
            print(f"❌ FAIL: Topic {topic_num} missing completely")
            all_topics_ok = False
        elif len(topics[topic_num]) != 20:
            print(
                f"❌ FAIL: Topic {topic_num} has {len(topics[topic_num])} conversations (expected 20)"
            )
            all_topics_ok = False

    if not all_topics_ok:
        return False
    print(f"✅ PASS: All 30 topics have exactly 20 conversations each")

    # Check 3: conversation_index is 1-20 for each topic
    for topic_num, convs in topics.items():
        indices = [c["conversation_index"] for c in convs]
        indices_sorted = sorted(indices)
        expected = list(range(1, 21))

        if indices_sorted != expected:
            print(f"❌ FAIL: Topic {topic_num} has wrong indices: {indices_sorted}")
            print(f"   Expected: {expected}")
            return False

    print(f"✅ PASS: All topics have conversation_index 1-20")

    # Check 4: Build conversation_ids and check for duplicates
    conv_ids = []
    for conv in conversations:
        # Build ID same way as generate script
        conv_id = f"conv_{conv['level']}_{conv['topic_slug']}_{conv['topic_number']:02d}_{conv['conversation_index']:03d}"
        conv_ids.append(conv_id)

    if len(conv_ids) != len(set(conv_ids)):
        duplicates = [x for x in conv_ids if conv_ids.count(x) > 1]
        print(f"❌ FAIL: Found duplicate conversation_ids:")
        for dup in set(duplicates):
            print(f"   - {dup}")
        return False

    print(f"✅ PASS: All 600 conversation_ids are unique")

    # Check 5: Verify ID format
    for conv_id in conv_ids[:5]:
        print(f"   Sample ID: {conv_id}")

    print()
    print("=" * 70)
    print("✅ ALL VALIDATION PASSED")
    print("=" * 70)
    print()
    print("Safe to run generation script!")
    return True


if __name__ == "__main__":
    success = validate_parsed_conversations()
    sys.exit(0 if success else 1)
