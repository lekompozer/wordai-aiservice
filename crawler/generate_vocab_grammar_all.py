#!/usr/bin/env python3
"""
Generate Vocabulary and Grammar for ALL Conversations

This script:
1. Gets all conversations from conversation_library
2. For each conversation, extracts vocabulary and grammar patterns
3. Saves to conversation_vocabulary and conversation_grammar collections

Collections:
- conversation_vocabulary: {conversation_id, vocabulary: [{word, pos, definition, level, examples}]}
- conversation_grammar: {conversation_id, grammar_patterns: [{pattern, type, explanation, examples}]}
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
import asyncio
from typing import List, Dict
import re
from collections import defaultdict

# Import NLP libraries if available (fallback to basic extraction if not)
try:
    import spacy

    nlp = spacy.load("en_core_web_sm")
    HAS_SPACY = True
except:
    HAS_SPACY = False
    print("⚠️ spaCy not available - using basic extraction")


def extract_vocabulary(dialogue: List[Dict]) -> List[Dict]:
    """
    Extract vocabulary from conversation dialogue

    Returns:
        List of {word, pos, definition, level, frequency, examples}
    """
    vocabulary = []

    # Combine all English text
    all_text = " ".join([line.get("text_en", "") for line in dialogue])

    if HAS_SPACY:
        # Use spaCy for better extraction
        doc = nlp(all_text.lower())

        word_freq = defaultdict(int)
        word_examples = defaultdict(list)

        for sent in doc.sents:
            sent_text = sent.text
            for token in sent:
                # Skip stopwords, punctuation, spaces
                if token.is_stop or token.is_punct or token.is_space:
                    continue

                # Focus on content words
                if token.pos_ in ["NOUN", "VERB", "ADJ", "ADV"]:
                    word = token.lemma_
                    word_freq[word] += 1
                    if len(word_examples[word]) < 2:  # Keep max 2 examples
                        word_examples[word].append(sent_text)

        # Convert to vocabulary entries
        for word, freq in sorted(word_freq.items(), key=lambda x: x[1], reverse=True):
            doc_word = nlp(word)
            pos = doc_word[0].pos_ if len(doc_word) > 0 else "UNKNOWN"

            # Estimate CEFR level based on frequency (simple heuristic)
            if freq >= 3:
                level = "A1"
            elif freq >= 2:
                level = "A2"
            else:
                level = "B1"

            vocabulary.append(
                {
                    "word": word,
                    "pos": pos,
                    "frequency": freq,
                    "level": level,
                    "examples": word_examples[word],
                }
            )

    else:
        # Basic extraction without spaCy
        words = re.findall(r"\b[a-zA-Z]+\b", all_text.lower())
        word_freq = defaultdict(int)

        # Simple stopwords list
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "my",
            "your",
            "his",
            "her",
        }

        for word in words:
            if word not in stopwords and len(word) > 2:
                word_freq[word] += 1

        for word, freq in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[
            :50
        ]:
            vocabulary.append(
                {
                    "word": word,
                    "pos": "UNKNOWN",
                    "frequency": freq,
                    "level": "B1",
                    "examples": [],
                }
            )

    return vocabulary[:50]  # Return top 50 words


def extract_grammar_patterns(dialogue: List[Dict]) -> List[Dict]:
    """
    Extract grammar patterns from conversation

    Returns:
        List of {pattern, type, explanation, examples}
    """
    patterns = []

    # Combine all English text
    all_text = " ".join([line.get("text_en", "") for line in dialogue])

    # Pattern detection rules
    pattern_rules = [
        # Present Simple
        {
            "regex": r"\b(am|is|are|do|does|don\'t|doesn\'t)\b",
            "type": "Present Simple",
            "pattern": "Subject + verb (base form/s)",
            "explanation": "Used for habits, facts, and general truths",
        },
        # Present Continuous
        {
            "regex": r"\b(am|is|are)\s+\w+ing\b",
            "type": "Present Continuous",
            "pattern": "Subject + am/is/are + verb-ing",
            "explanation": "Used for actions happening now or temporary situations",
        },
        # Past Simple
        {
            "regex": r"\b(was|were|did|didn\'t|went|had|said|came)\b",
            "type": "Past Simple",
            "pattern": "Subject + verb (past form)",
            "explanation": "Used for completed actions in the past",
        },
        # Future (will/going to)
        {
            "regex": r"\b(will|won\'t|\'ll|going to)\b",
            "type": "Future",
            "pattern": "Subject + will/going to + verb",
            "explanation": "Used for future plans, predictions, and intentions",
        },
        # Modal verbs
        {
            "regex": r"\b(can|could|may|might|must|should|would)\b",
            "type": "Modal Verbs",
            "pattern": "Subject + modal + verb (base form)",
            "explanation": "Used for ability, permission, possibility, obligation, advice",
        },
        # Questions
        {
            "regex": r"\b(what|where|when|why|who|how|which)\b.*\?",
            "type": "Wh-Questions",
            "pattern": "Wh-word + auxiliary + subject + verb",
            "explanation": "Used to ask for specific information",
        },
        # Comparatives
        {
            "regex": r"\b(\w+er\s+than|more\s+\w+\s+than)\b",
            "type": "Comparatives",
            "pattern": "adjective-er/more + adjective + than",
            "explanation": "Used to compare two things",
        },
        # Superlatives
        {
            "regex": r"\bthe\s+(\w+est|most\s+\w+)\b",
            "type": "Superlatives",
            "pattern": "the + adjective-est/most + adjective",
            "explanation": "Used to describe the extreme degree",
        },
    ]

    # Find examples for each pattern
    for rule in pattern_rules:
        matches = re.finditer(rule["regex"], all_text, re.IGNORECASE)
        examples = []

        for match in matches:
            # Get sentence containing the match
            start = max(0, match.start() - 50)
            end = min(len(all_text), match.end() + 50)
            context = all_text[start:end].strip()

            # Find complete sentence
            sentences = re.split(r"[.!?]", context)
            for sent in sentences:
                if match.group() in sent:
                    examples.append(sent.strip())
                    break

            if len(examples) >= 2:  # Max 2 examples per pattern
                break

        if examples:
            patterns.append(
                {
                    "pattern": rule["pattern"],
                    "type": rule["type"],
                    "explanation": rule["explanation"],
                    "examples": examples,
                }
            )

    return patterns


async def generate_vocab_grammar_for_conversation(
    conv_id: str, dialogue: List[Dict], db
):
    """Generate and save vocabulary and grammar for one conversation"""

    print(f"  📝 Processing: {conv_id}")

    # Extract vocabulary
    vocabulary = extract_vocabulary(dialogue)

    # Extract grammar patterns
    grammar_patterns = extract_grammar_patterns(dialogue)

    # Save vocabulary
    if vocabulary:
        db.conversation_vocabulary.update_one(
            {"conversation_id": conv_id},
            {
                "$set": {
                    "conversation_id": conv_id,
                    "vocabulary": vocabulary,
                    "total_words": len(vocabulary),
                    "generated_at": None,  # Will be set by MongoDB
                }
            },
            upsert=True,
        )

    # Save grammar patterns
    if grammar_patterns:
        db.conversation_grammar.update_one(
            {"conversation_id": conv_id},
            {
                "$set": {
                    "conversation_id": conv_id,
                    "grammar_patterns": grammar_patterns,
                    "total_patterns": len(grammar_patterns),
                    "generated_at": None,
                }
            },
            upsert=True,
        )

    return len(vocabulary), len(grammar_patterns)


async def generate_batch(conv_ids: List[str], worker_id: int, db):
    """Process a batch of conversations"""

    success = 0
    failed = 0
    total_vocab = 0
    total_grammar = 0

    for i, conv_id in enumerate(conv_ids):
        try:
            print(f"[Worker {worker_id}] [{i+1}/{len(conv_ids)}] {conv_id}")

            # Get conversation
            conv = db.conversation_library.find_one({"conversation_id": conv_id})

            if not conv or not conv.get("dialogue"):
                print(f"  ⚠️ Skipping: No dialogue")
                failed += 1
                continue

            dialogue = conv["dialogue"]

            # Generate vocab and grammar
            vocab_count, grammar_count = await generate_vocab_grammar_for_conversation(
                conv_id, dialogue, db
            )

            total_vocab += vocab_count
            total_grammar += grammar_count
            success += 1

            print(f"  ✅ Vocabulary: {vocab_count}, Grammar: {grammar_count}")

        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            failed += 1

    return worker_id, success, failed, total_vocab, total_grammar


async def main():
    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("🎯 GENERATE VOCABULARY & GRAMMAR FOR ALL CONVERSATIONS")
    print("=" * 80)

    # Get all conversations
    print("\n🔍 Finding all conversations...")
    conversations = list(db.conversation_library.find({}, {"conversation_id": 1}))
    conv_ids = [c["conversation_id"] for c in conversations]

    print(f"📊 Found {len(conv_ids)} conversations")
    print(f"🧠 Using {'spaCy NLP' if HAS_SPACY else 'basic extraction'}")
    print("\n" + "=" * 80)
    print("⏱️  Starting generation with 5 workers...\n")

    # Split into 5 batches
    batch_size = len(conv_ids) // 5
    batches = [
        (
            conv_ids[i * batch_size : (i + 1) * batch_size]
            if i < 4
            else conv_ids[i * batch_size :]
        )
        for i in range(5)
    ]

    for i, batch in enumerate(batches, 1):
        print(f"Worker {i}: {len(batch)} conversations")
    print("")

    # Run 5 workers in parallel
    tasks = [generate_batch(batch, i + 1, db) for i, batch in enumerate(batches)]
    results = await asyncio.gather(*tasks)

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY:")
    print("=" * 80)

    total_success = sum(r[1] for r in results)
    total_failed = sum(r[2] for r in results)
    total_vocab_words = sum(r[3] for r in results)
    total_grammar_patterns = sum(r[4] for r in results)

    for worker_id, success, failed, vocab, grammar in results:
        print(f"Worker {worker_id}: {success} success, {failed} failed")
        print(f"  Vocabulary: {vocab} words, Grammar: {grammar} patterns")

    print(f"\nTOTAL: {total_success} success, {total_failed} failed")
    print(f"Total vocabulary words: {total_vocab_words}")
    print(f"Total grammar patterns: {total_grammar_patterns}")
    print("=" * 80)

    # Verify final state
    vocab_count = db.conversation_vocabulary.count_documents({})
    grammar_count = db.conversation_grammar.count_documents({})

    print(f"\n✅ Final database state:")
    print(f"   Vocabulary entries: {vocab_count}")
    print(f"   Grammar entries: {grammar_count}")
    print(
        f"   Coverage: {vocab_count}/{len(conv_ids)} = {vocab_count/len(conv_ids)*100:.1f}%"
    )


if __name__ == "__main__":
    asyncio.run(main())
