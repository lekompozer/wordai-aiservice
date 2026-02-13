#!/usr/bin/env python3
"""
Check vocabulary and grammar data completeness
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager


def main():
    db_manager = DBManager()
    db = db_manager.db

    print("📚 CHECKING VOCABULARY & GRAMMAR DATA")
    print("=" * 80)

    # Total conversations
    total_convs = db.conversation_library.count_documents({})
    print(f"\nTotal conversations in library: {total_convs}")

    # Check conversation_vocabulary collection
    print("\n" + "=" * 80)
    print("📖 VOCABULARY COLLECTION:")
    print("=" * 80)

    vocab_count = db.conversation_vocabulary.count_documents({})
    print(f"Total vocabulary entries: {vocab_count}")

    # Count unique conversations with vocabulary
    vocab_convs = db.conversation_vocabulary.distinct("conversation_id")
    print(f"Conversations with vocabulary: {len(vocab_convs)}")
    print(f"Coverage: {len(vocab_convs) / total_convs * 100:.1f}%")

    # Sample vocabulary entry
    sample_vocab = db.conversation_vocabulary.find_one({})
    if sample_vocab:
        print("\nSample vocabulary entry:")
        print(f"  Conversation ID: {sample_vocab.get('conversation_id')}")
        print(f"  Total words: {len(sample_vocab.get('vocabulary', []))}")
        if sample_vocab.get("vocabulary"):
            first_word = sample_vocab["vocabulary"][0]
            print(
                f"  First word: {first_word.get('word')} ({first_word.get('pos', 'N/A')})"
            )
            print(f"    Definition: {first_word.get('definition', 'N/A')[:50]}...")
            print(f"    Level: {first_word.get('level', 'N/A')}")

    # Check conversation_grammar collection
    print("\n" + "=" * 80)
    print("📝 GRAMMAR COLLECTION:")
    print("=" * 80)

    grammar_count = db.conversation_grammar.count_documents({})
    print(f"Total grammar entries: {grammar_count}")

    # Count unique conversations with grammar
    grammar_convs = db.conversation_grammar.distinct("conversation_id")
    print(f"Conversations with grammar: {len(grammar_convs)}")
    print(f"Coverage: {len(grammar_convs) / total_convs * 100:.1f}%")

    # Sample grammar entry
    sample_grammar = db.conversation_grammar.find_one({})
    if sample_grammar:
        print("\nSample grammar entry:")
        print(f"  Conversation ID: {sample_grammar.get('conversation_id')}")
        print(f"  Total patterns: {len(sample_grammar.get('grammar_patterns', []))}")
        if sample_grammar.get("grammar_patterns"):
            first_pattern = sample_grammar["grammar_patterns"][0]
            print(f"  First pattern: {first_pattern.get('pattern')}")
            print(f"    Type: {first_pattern.get('type', 'N/A')}")
            print(f"    Example: {first_pattern.get('example', 'N/A')}")

    # Find conversations WITHOUT vocabulary or grammar
    print("\n" + "=" * 80)
    print("⚠️  MISSING DATA:")
    print("=" * 80)

    # Get all conversation IDs
    all_conv_ids = set(db.conversation_library.distinct("conversation_id"))
    vocab_conv_ids = set(vocab_convs)
    grammar_conv_ids = set(grammar_convs)

    missing_vocab = all_conv_ids - vocab_conv_ids
    missing_grammar = all_conv_ids - grammar_conv_ids

    print(f"\nConversations without vocabulary: {len(missing_vocab)}")
    if missing_vocab and len(missing_vocab) <= 10:
        print(f"  IDs: {', '.join(list(missing_vocab)[:10])}")
    elif missing_vocab:
        print(f"  First 10: {', '.join(list(missing_vocab)[:10])}")

    print(f"\nConversations without grammar: {len(missing_grammar)}")
    if missing_grammar and len(missing_grammar) <= 10:
        print(f"  IDs: {', '.join(list(missing_grammar)[:10])}")
    elif missing_grammar:
        print(f"  First 10: {', '.join(list(missing_grammar)[:10])}")

    # Check which topics are missing vocab/grammar
    print("\n" + "=" * 80)
    print("📊 MISSING DATA BY TOPIC:")
    print("=" * 80)

    if missing_vocab or missing_grammar:
        # Get topic info for missing conversations
        missing_vocab_topics = {}
        missing_grammar_topics = {}

        for conv_id in missing_vocab:
            conv = db.conversation_library.find_one({"conversation_id": conv_id})
            if conv:
                topic = f"{conv['topic_number']}: {conv['topic_slug']}"
                missing_vocab_topics[topic] = missing_vocab_topics.get(topic, 0) + 1

        for conv_id in missing_grammar:
            conv = db.conversation_library.find_one({"conversation_id": conv_id})
            if conv:
                topic = f"{conv['topic_number']}: {conv['topic_slug']}"
                missing_grammar_topics[topic] = missing_grammar_topics.get(topic, 0) + 1

        if missing_vocab_topics:
            print("\nMissing VOCABULARY by topic:")
            for topic in sorted(missing_vocab_topics.keys()):
                print(f"  {topic}: {missing_vocab_topics[topic]} conversations")

        if missing_grammar_topics:
            print("\nMissing GRAMMAR by topic:")
            for topic in sorted(missing_grammar_topics.keys()):
                print(f"  {topic}: {missing_grammar_topics[topic]} conversations")

    # Summary
    print("\n" + "=" * 80)
    print("✅ SUMMARY:")
    print("=" * 80)
    print(f"Total conversations: {total_convs}")
    print(
        f"With vocabulary: {len(vocab_convs)} ({len(vocab_convs)/total_convs*100:.1f}%)"
    )
    print(
        f"With grammar: {len(grammar_convs)} ({len(grammar_convs)/total_convs*100:.1f}%)"
    )
    print(
        f"Complete (both vocab & grammar): {len(vocab_conv_ids & grammar_conv_ids)} ({len(vocab_conv_ids & grammar_conv_ids)/total_convs*100:.1f}%)"
    )
    print(f"Missing vocab: {len(missing_vocab)}")
    print(f"Missing grammar: {len(missing_grammar)}")


if __name__ == "__main__":
    main()
