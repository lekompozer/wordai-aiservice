#!/usr/bin/env python3
"""
Generate Vocabulary and Grammar for ALL Conversations using DeepSeek V3

This script:
1. Gets all conversations from conversation_library WITHOUT vocabulary
2. For each conversation, uses DeepSeek V3 to generate vocabulary and grammar
3. Saves to conversation_vocabulary collection

Schema (following conversation_models.py):
- conversation_vocabulary: {
    vocab_id: "vocab_{conversation_id}",
    conversation_id: str,
    vocabulary: [{word, definition_en, definition_vi, example, pos_tag}],
    grammar_points: [{pattern, explanation_en, explanation_vi, example}],
    generated_by: "deepseek-v3",
    generated_at: datetime
  }
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
import asyncio
from typing import List, Dict
import json
from openai import OpenAI
from datetime import datetime

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY not set in environment")


def build_vocab_grammar_prompt(conversation_data: Dict) -> str:
    """Build prompt for DeepSeek to generate vocabulary and grammar"""

    level = conversation_data.get("level", "intermediate")
    title_en = conversation_data.get("title", {}).get("en", "Untitled")
    title_vi = conversation_data.get("title", {}).get("vi", "Chưa có tiêu đề")
    dialogue = conversation_data.get("dialogue", [])

    # Combine dialogue text
    dialogue_text = "\n".join(
        [
            f"{i+1}. [{line.get('speaker', 'Unknown')}] {line.get('text_en', '')}"
            for i, line in enumerate(dialogue)
        ]
    )

    # Determine vocabulary and grammar count by level
    vocab_count_map = {"beginner": 10, "intermediate": 12, "advanced": 15}
    grammar_count_map = {"beginner": 4, "intermediate": 5, "advanced": 6}

    vocab_count = vocab_count_map.get(level, 12)
    grammar_count = grammar_count_map.get(level, 5)

    prompt = f"""Analyze this English conversation and extract vocabulary and grammar points for English learners at {level.upper()} level.

CONVERSATION:
Title: {title_en} ({title_vi})
Level: {level.upper()}

Dialogue:
{dialogue_text}

TASK: Extract vocabulary and grammar from this conversation ONLY (do not add external words).

OUTPUT FORMAT (pure JSON, no markdown):
{{
  "vocabulary": [
    {{
      "word": "word or phrase from dialogue",
      "definition_en": "English definition",
      "definition_vi": "Vietnamese definition",
      "example": "Exact sentence from dialogue where it appears",
      "pos_tag": "NOUN|VERB|ADJ|ADV|PHRASE"
    }}
  ],
  "grammar_points": [
    {{
      "pattern": "Grammar structure (e.g., 'Can I + verb?')",
      "explanation_en": "English explanation",
      "explanation_vi": "Vietnamese explanation",
      "example": "Exact sentence from dialogue demonstrating it"
    }}
  ]
}}

REQUIREMENTS:
1. Vocabulary: Extract {vocab_count} most useful words/phrases for {level} learners
   - Focus on: key verbs, nouns, adjectives, useful phrases
   - Each word MUST appear in the actual dialogue
   - Include exact sentence where it appears as example

2. Grammar Points: Identify {grammar_count} grammar patterns used in dialogue
   - Common patterns: tenses, modals, questions, conditionals, passive, etc.
   - Each pattern MUST be demonstrated in the actual dialogue
   - Provide clear, simple explanations

3. All examples MUST be exact sentences from the dialogue above
4. Vietnamese translations must be natural and accurate
5. Output MUST be valid JSON only (no ```json markers, no extra text)

Generate now:"""

    return prompt


async def generate_vocab_grammar(conversation_data: Dict) -> Dict:
    """Use DeepSeek to generate vocabulary and grammar"""

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    prompt = build_vocab_grammar_prompt(conversation_data)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,  # Lower temperature for more consistent extraction
            max_tokens=3000,
        )

        content = response.choices[0].message.content

        # Clean markdown formatting if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line (```)
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        # Parse JSON
        data = json.loads(content)
        return data

    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {str(e)[:100]}")
        print(f"  Content: {content[:200]}...")
        raise
    except Exception as e:
        print(f"  ❌ DeepSeek API error: {str(e)[:100]}")
        raise


async def generate_vocab_grammar_for_conversation(conv_id: str, db):
    """Generate and save vocabulary and grammar for one conversation"""

    print(f"  📝 Processing: {conv_id}")

    # Get conversation from DB
    conv = db.conversation_library.find_one({"conversation_id": conv_id})

    if not conv or not conv.get("dialogue"):
        print(f"  ⚠️ Skipping: No dialogue")
        return None, None

    # Generate using DeepSeek
    try:
        result = await generate_vocab_grammar(conv)

        vocabulary = result.get("vocabulary", [])
        grammar_points = result.get("grammar_points", [])

        # Prepare document following conversation_models.py schema
        vocab_doc = {
            "vocab_id": f"vocab_{conv_id}",
            "conversation_id": conv_id,
            "vocabulary": vocabulary,
            "grammar_points": grammar_points,
            "generated_by": "deepseek-v3",
            "generated_at": datetime.utcnow(),
        }

        # Save to conversation_vocabulary
        db.conversation_vocabulary.update_one(
            {"conversation_id": conv_id}, {"$set": vocab_doc}, upsert=True
        )

        return len(vocabulary), len(grammar_points)

    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return None, None


async def process_single_conversation(
    conv_id: str, worker_id: int, index: int, total: int, db
):
    """Process a single conversation with logging"""
    try:
        print(f"[Worker {worker_id}] [{index}/{total}] {conv_id}")

        vocab_count, grammar_count = await generate_vocab_grammar_for_conversation(
            conv_id, db
        )

        if vocab_count is not None and grammar_count is not None:
            print(f"  ✅ Vocabulary: {vocab_count}, Grammar: {grammar_count}")
            return (True, vocab_count, grammar_count)
        else:
            return (False, 0, 0)

    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return (False, 0, 0)


async def generate_batch(conv_ids: List[str], worker_id: int, db):
    """Process a batch of conversations IN PARALLEL with rate limiting"""

    print(
        f"[Worker {worker_id}] Starting {len(conv_ids)} conversations in parallel...\n"
    )

    # Create tasks for ALL conversations in batch
    tasks = []
    for i, conv_id in enumerate(conv_ids, 1):
        # Add small staggered delay to avoid all hitting API at once
        async def delayed_process(cid=conv_id, idx=i):
            await asyncio.sleep((idx - 1) * 0.1)  # Stagger by 0.1s
            return await process_single_conversation(
                cid, worker_id, idx, len(conv_ids), db
            )

        tasks.append(delayed_process())

    # Run all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count results
    success = 0
    failed = 0
    total_vocab = 0
    total_grammar = 0

    for result in results:
        if isinstance(result, Exception):
            failed += 1
        elif result and isinstance(result, tuple) and result[0]:
            success += 1
            total_vocab += result[1]
            total_grammar += result[2]
        else:
            failed += 1

    print(f"\n[Worker {worker_id}] Completed: {success} success, {failed} failed\n")

    return worker_id, success, failed, total_vocab, total_grammar


async def main():
    db_manager = DBManager()
    db = db_manager.db

    print("=" * 80)
    print("🎯 GENERATE VOCABULARY & GRAMMAR USING DEEPSEEK V3")
    print("=" * 80)

    # Get conversations WITHOUT vocabulary
    print("\n🔍 Finding conversations without vocabulary...")

    # Get all conversation IDs
    all_conv_ids = set(db.conversation_library.distinct("conversation_id"))

    # Get conversation IDs that already have vocabulary
    existing_vocab_ids = set(db.conversation_vocabulary.distinct("conversation_id"))

    # Find conversations without vocabulary
    conv_ids_without_vocab = list(all_conv_ids - existing_vocab_ids)

    print(f"📊 Total conversations: {len(all_conv_ids)}")
    print(f"📚 Already have vocabulary: {len(existing_vocab_ids)}")
    print(f"🆕 Need vocabulary: {len(conv_ids_without_vocab)}")

    if not conv_ids_without_vocab:
        print("\n✅ All conversations already have vocabulary!")
        return

    print(f"\n🚀 Processing {len(conv_ids_without_vocab)} conversations...")
    print("🤖 Using DeepSeek V3 for vocabulary and grammar extraction")
    print("\n" + "=" * 80)
    print("⏱️  Starting generation with 5 workers...\n")

    # Split into 5 batches
    conv_ids = sorted(conv_ids_without_vocab)
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
    total_convs = len(all_conv_ids)

    print(f"\n✅ Final database state:")
    print(f"   Vocabulary entries: {vocab_count}/{total_convs}")
    print(f"   Coverage: {vocab_count/total_convs*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
