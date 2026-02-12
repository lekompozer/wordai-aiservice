"""Generate only missing conversations from failed batches"""

import sys
import asyncio
import argparse

sys.path.append("/app")

from src.database.db_manager import DBManager
from parse_600_conversations import parse_topic_conversation_file
from generate_600_conversations import build_batch_prompt, save_conversation
import json
from openai import OpenAI
from datetime import datetime
import os

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")


async def generate_batch_with_retry(batch, max_retries=5):
    """Generate batch with more aggressive retry"""

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    prompt = build_batch_prompt(batch)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=8000,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from API")

            # Clean markdown
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines)

            data = json.loads(content)
            return data

        except (json.JSONDecodeError, ValueError) as e:
            if attempt < max_retries - 1:
                wait_time = 3 + attempt  # Exponential backoff
                print(f"  ⚠️ Attempt {attempt + 1}/{max_retries} failed: {str(e)[:80]}")
                print(f"  ⏳ Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            else:
                print(f"  ❌ All retries failed: {e}")
                raise

    raise RuntimeError("Max retries exceeded")


async def main():
    print("=" * 80)
    print("GENERATE MISSING CONVERSATIONS (202 missing)")
    print("=" * 80)
    print()

    # Parse all 600 conversations
    file_path = "docs/wordai/Learn English With Songs/Topic Conversation.md"
    print(f"📖 Parsing: {file_path}")
    conversations = parse_topic_conversation_file(file_path)
    print(f"✅ Parsed {len(conversations)} conversations")
    print()

    # Get existing IDs
    print("🔌 Connecting to MongoDB...")
    db_manager = DBManager()
    existing_ids = set(db_manager.db.conversation_library.distinct("conversation_id"))
    print(f"📊 In DB: {len(existing_ids)} conversations")
    print()

    # Find missing by index
    missing_conversations = []
    for i, conv in enumerate(conversations, 1):
        # Use topic_slug from parsed data (already computed correctly)
        conv_id = f"conv_{conv['level'].value}_{conv['topic_slug']}_{conv['topic_number']:02d}_{i:03d}"

        if conv_id not in existing_ids:
            missing_conversations.append(
                {"index": i, "conv_def": conv, "conv_id": conv_id}
            )

    print(f"❌ Missing: {len(missing_conversations)} conversations")
    print()

    # Group into batches of 3
    batches = []
    for i in range(0, len(missing_conversations), 3):
        batch_items = missing_conversations[i : i + 3]
        batches.append(batch_items)

    total_batches = len(batches)
    print(f"📦 Processing {total_batches} batches (3 conversations each)")
    print()

    success = 0
    failed = 0

    for i, batch_items in enumerate(batches, 1):
        conv_ids = [item["conv_id"] for item in batch_items]
        print(f"[{i}/{total_batches}] Batch {i}: {len(batch_items)} conversations")
        print(f"  IDs: {', '.join(conv_ids)}")

        try:
            # Prepare batch for prompt
            batch_for_prompt = [item["conv_def"] for item in batch_items]

            # Generate with retry
            generated_list = await generate_batch_with_retry(batch_for_prompt)

            # Save each
            for item, generated in zip(batch_items, generated_list):
                conv_id = save_conversation(
                    item["conv_def"],
                    generated,
                    db_manager,
                    item["index"],  # Use original index for consistent conv_id
                )
                print(f"  ✅ {conv_id}")
                success += 1

            print()

            # Rate limit
            if i < total_batches:
                await asyncio.sleep(2)

        except Exception as e:
            print(f"  ❌ Batch failed: {str(e)[:100]}")
            failed += len(batch_items)
            print()

    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print(f"✅ Success: {success}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total in DB: {db_manager.db.conversation_library.count_documents({})}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
