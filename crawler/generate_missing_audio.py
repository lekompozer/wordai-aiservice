#!/usr/bin/env python3
"""
Generate audio for all conversations without audio_url
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DBManager
from src.services.google_tts_service import GoogleTTSService
import asyncio
from crawler.generate_conversation_audio import generate_audio_for_conversation
import time


async def generate_batch(conversation_ids, worker_id, db_manager, tts_service):
    """Generate audio for a batch of conversations"""
    success = 0
    failed = 0
    failed_ids = []

    for i, conv_id in enumerate(conversation_ids):
        try:
            print(
                f"[Worker {worker_id}] [{i+1}/{len(conversation_ids)}] Processing: {conv_id}"
            )

            # Get conversation from DB to get dialogue
            conv = db_manager.db.conversation_library.find_one(
                {"conversation_id": conv_id}
            )
            if not conv or not conv.get("dialogue"):
                print(f"[Worker {worker_id}] ⚠️ Skipping {conv_id}: No dialogue found")
                failed += 1
                failed_ids.append(conv_id)
                continue

            dialogue = conv["dialogue"]

            # Generate audio
            audio_info = await generate_audio_for_conversation(
                conv_id, dialogue, tts_service, db_manager
            )

            if audio_info:
                # Update DB with audio URL
                db_manager.db.conversation_library.update_one(
                    {"conversation_id": conv_id},
                    {
                        "$set": {
                            "audio_url": audio_info["audio_url"],
                            "audio_info": {
                                "r2_key": audio_info["r2_key"],
                                "library_file_id": audio_info.get("library_file_id"),
                                "duration": audio_info["duration"],
                                "format": audio_info["format"],
                                "voices_used": audio_info["voices_used"],
                                "generated_at": audio_info["generated_at"],
                            },
                        }
                    },
                )
                success += 1
                print(
                    f"[Worker {worker_id}] ✅ Success: {conv_id} ({success}/{len(conversation_ids)})"
                )
            else:
                failed += 1
                failed_ids.append(conv_id)
                print(
                    f"[Worker {worker_id}] ❌ Failed: {conv_id} - Audio generation returned None"
                )

        except Exception as e:
            failed += 1
            failed_ids.append(conv_id)
            print(f"[Worker {worker_id}] ❌ Failed: {conv_id} - {str(e)[:150]}")

    return worker_id, success, failed, failed_ids


async def main():
    db_manager = DBManager()
    db = db_manager.db

    # Initialize TTS service (shared across workers)
    from src.services.google_tts_service import GoogleTTSService

    tts_service = GoogleTTSService()
    print("✅ Initialized GoogleTTSService")

    # Get all conversations without audio
    print("🔍 Finding conversations without audio...")
    conversations = list(
        db.conversation_library.find(
            {"audio_url": {"$exists": False}},
            {"conversation_id": 1, "topic_number": 1, "topic_slug": 1},
        )
    )

    conv_ids = [c["conversation_id"] for c in conversations]

    if not conv_ids:
        print("✅ All conversations already have audio!")
        return

    print(
        f"\n🎯 Starting parallel generation: {len(conv_ids)} conversations with 5 workers"
    )
    print("=" * 80)

    # Show distribution by topic
    topic_counts = {}
    for c in conversations:
        topic = f"{c['topic_number']}: {c['topic_slug']}"
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    print("\nConversations to process by topic:")
    for topic in sorted(topic_counts.keys()):
        print(f"  {topic}: {topic_counts[topic]} conversations")

    print("\n" + "=" * 80)
    print("⏱️  Starting audio generation...\n")

    start_time = time.time()

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

    # Show batch sizes
    for i, batch in enumerate(batches, 1):
        print(f"Worker {i}: {len(batch)} conversations")
    print("")

    # Run 5 workers in parallel (pass shared db_manager and tts_service)
    tasks = [
        generate_batch(batch, i + 1, db_manager, tts_service)
        for i, batch in enumerate(batches)
    ]
    results = await asyncio.gather(*tasks)

    end_time = time.time()
    duration = end_time - start_time

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY:")
    print("=" * 80)

    total_success = sum(r[1] for r in results)
    total_failed = sum(r[2] for r in results)

    for worker_id, success, failed, failed_ids in results:
        print(f"Worker {worker_id}: {success} success, {failed} failed")
        if failed_ids:
            print(
                f"  Failed IDs: {', '.join(failed_ids[:5])}{'...' if len(failed_ids) > 5 else ''}"
            )

    print(f"\nTOTAL: {total_success} success, {total_failed} failed")
    print(f"Duration: {duration/60:.1f} minutes ({duration:.0f} seconds)")

    if total_success > 0:
        avg_time = duration / total_success
        print(f"Average time per conversation: {avg_time:.1f} seconds")

    print("=" * 80)

    # Verify final state
    final_without_audio = db.conversation_library.count_documents(
        {"audio_url": {"$exists": False}}
    )
    final_with_audio = db.conversation_library.count_documents(
        {"audio_url": {"$exists": True, "$ne": None}}
    )

    print(f"\n✅ Final state:")
    print(f"   Conversations with audio: {final_with_audio}")
    print(f"   Conversations without audio: {final_without_audio}")


if __name__ == "__main__":
    asyncio.run(main())
