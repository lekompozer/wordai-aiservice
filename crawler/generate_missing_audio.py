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

    # Initialize TTS service
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

    if not conversations:
        print("✅ All conversations already have audio!")
        return

    print(f"\n🎯 SEQUENTIAL GENERATION: {len(conversations)} conversations")
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
    print("⏱️  Starting sequential audio generation...\n")

    start_time = time.time()
    success_count = 0
    failed_count = 0
    failed_ids = []

    # Process ONE BY ONE (no parallel)
    for idx, conv in enumerate(conversations, 1):
        conv_id = conv["conversation_id"]
        
        print(f"\n[{idx}/{len(conversations)}] Processing: {conv_id}")
        
        try:
            # Get conversation dialogue
            full_conv = db_manager.db.conversation_library.find_one(
                {"conversation_id": conv_id}
            )
            if not full_conv or not full_conv.get("dialogue"):
                print(f"⚠️  Skipping {conv_id}: No dialogue found")
                failed_count += 1
                failed_ids.append(conv_id)
                continue

            dialogue = full_conv["dialogue"]

            # Generate audio with retry (3 attempts)
            audio_info = None
            for attempt in range(3):
                try:
                    print(f"  🔄 Attempt {attempt + 1}/3...")
                    audio_info = await generate_audio_for_conversation(
                        conv_id, dialogue, tts_service, db_manager
                    )
                    if audio_info:
                        break
                    else:
                        print(f"  ⚠️  Attempt {attempt + 1} returned None")
                        if attempt < 2:
                            await asyncio.sleep(15)  # Wait 15s before retry
                except Exception as e:
                    print(f"  ❌ Attempt {attempt + 1} error: {str(e)[:100]}")
                    if attempt < 2:
                        print(f"  ⏳ Waiting 15s before retry...")
                        await asyncio.sleep(15)

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
                success_count += 1
                print(f"  ✅ Success ({success_count}/{len(conversations)})")
            else:
                failed_count += 1
                failed_ids.append(conv_id)
                print(f"  ❌ Failed after 3 attempts")

        except Exception as e:
            failed_count += 1
            failed_ids.append(conv_id)
            print(f"  ❌ Exception: {str(e)[:150]}")

        # Show progress every 10
        if idx % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining = (len(conversations) - idx) * avg_time
            print(f"\n📊 Progress: {idx}/{len(conversations)} | Success: {success_count} | Failed: {failed_count}")
            print(f"   Time: {elapsed/60:.1f}min elapsed, ~{remaining/60:.1f}min remaining\n")

    end_time = time.time()
    duration = end_time - start_time

    # Summary
    print("\n" + "=" * 80)
    print("📊 FINAL SUMMARY:")
    print("=" * 80)
    print(f"Total processed: {len(conversations)}")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")
    
    if failed_ids:
        print(f"\nFailed IDs ({len(failed_ids)}):")
        for fid in failed_ids[:10]:
            print(f"  - {fid}")
        if len(failed_ids) > 10:
            print(f"  ... and {len(failed_ids) - 10} more")

    print(f"\nDuration: {duration/60:.1f} minutes ({duration:.0f} seconds)")

    if success_count > 0:
        avg_time = duration / success_count
        print(f"Average time per successful audio: {avg_time:.1f} seconds")

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
