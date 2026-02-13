#!/usr/bin/env python3
"""
Parallel audio generation for 480 conversations using Vertex AI
5 workers processing simultaneously
"""

import asyncio
from src.database.db_manager import DBManager
from src.services.google_tts_service import GoogleTTSService
from crawler.generate_conversation_audio import generate_audio_for_conversation


async def generate_batch(conversation_ids, worker_id, db_manager, tts_service):
    """Process a batch of conversations for one worker"""
    success = 0
    failed = 0

    for i, conv_id in enumerate(conversation_ids):
        try:
            print(
                f"[Worker {worker_id}] [{i+1}/{len(conversation_ids)}] Processing: {conv_id}"
            )

            # Get conversation from DB
            conv = db_manager.db.conversation_library.find_one(
                {"conversation_id": conv_id}
            )

            if not conv or not conv.get("dialogue"):
                print(f"[Worker {worker_id}] ⚠️ Skip: {conv_id} - No dialogue")
                failed += 1
                continue

            # Generate audio
            audio_info = await generate_audio_for_conversation(
                conv_id, conv["dialogue"], tts_service, db_manager
            )

            if audio_info:
                success += 1
                print(
                    f"[Worker {worker_id}] ✅ Success: {conv_id} ({success}/{len(conversation_ids)})"
                )
            else:
                failed += 1
                print(f"[Worker {worker_id}] ❌ Failed: {conv_id} - audio_info is None")

        except Exception as e:
            failed += 1
            print(f"[Worker {worker_id}] ❌ Failed: {conv_id} - {str(e)[:100]}")

    return worker_id, success, failed


async def main():
    """Main parallel generation"""
    db_manager = DBManager()
    db = db_manager.db

    # Initialize TTS service
    tts_service = GoogleTTSService()
    print("✅ Initialized GoogleTTSService with Vertex AI")
    print("")

    # Get all conversations without audio
    conversations = list(
        db.conversation_library.find(
            {"audio_url": {"$exists": False}}, {"conversation_id": 1}
        ).limit(480)
    )

    conv_ids = [c["conversation_id"] for c in conversations]
    print(
        f"🎯 Starting parallel generation: {len(conv_ids)} conversations with 5 workers"
    )
    print("")

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

    print(f"📦 Batch sizes: {[len(b) for b in batches]}")
    print("")

    # Run 5 workers in parallel
    tasks = [
        generate_batch(batch, i + 1, db_manager, tts_service)
        for i, batch in enumerate(batches)
    ]
    results = await asyncio.gather(*tasks)

    # Summary
    print("")
    print("=" * 60)
    print("📊 SUMMARY:")
    total_success = sum(r[1] for r in results)
    total_failed = sum(r[2] for r in results)
    for worker_id, success, failed in results:
        print(f"   Worker {worker_id}: {success} success, {failed} failed")
    print(f"   TOTAL: {total_success} success, {total_failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
