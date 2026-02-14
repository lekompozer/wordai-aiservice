#!/usr/bin/env python3
"""
Test audio generation with 15s retry for Vertex AI timeout issues

Findings so far:
- Quota: OK (80 req/min, only 3.61% used)
- Latency: 106-231 seconds median-95th percentile
- Error: httpx.ReadTimeout

Test với retry 15s để xem có phải Vertex AI cần warm-up không
"""

import sys
import asyncio
import time

sys.path.append("/app")

from src.database.db_manager import DBManager
from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService


async def build_tts_script(dialogue):
    """Convert dialogue to TTS script (max 2 speakers)"""
    speakers_seen = []
    speaker_to_gender = {}

    for turn in sorted(dialogue, key=lambda x: x["order"]):
        speaker_id = turn["speaker"]
        gender = turn.get("gender", "male").lower()

        if speaker_id not in speakers_seen:
            speakers_seen.append(speaker_id)
            speaker_to_gender[speaker_id] = gender

    speaker_to_idx = {}
    speaker_roles = []

    if len(speakers_seen) <= 2:
        for i, speaker_id in enumerate(speakers_seen[:2]):
            gender = speaker_to_gender[speaker_id]
            speaker_roles.append(gender.capitalize())
            speaker_to_idx[speaker_id] = i
    else:
        # Merge to 2 speakers by gender
        for i, speaker_id in enumerate(speakers_seen[:2]):
            gender = speaker_to_gender[speaker_id]
            speaker_roles.append(gender.capitalize())
            speaker_to_idx[speaker_id] = i

        for speaker_id in speakers_seen[2:]:
            gender = speaker_to_gender[speaker_id]
            matching_idx = 0 if gender == speaker_to_gender[speakers_seen[0]] else 1
            speaker_to_idx[speaker_id] = matching_idx

    lines = []
    for turn in sorted(dialogue, key=lambda x: x["order"]):
        speaker_id = turn["speaker"]
        text = turn.get("text_en", "").strip()
        if text:
            idx = speaker_to_idx.get(speaker_id, 0)
            lines.append({"speaker": idx, "text": text})

    return {"speaker_roles": speaker_roles, "lines": lines}


async def test_audio_with_retry(max_retries=5, retry_delay=15):
    """
    Test audio generation with retry mechanism

    Args:
        max_retries: Number of retry attempts (default: 5)
        retry_delay: Delay between retries in seconds (default: 15)
    """
    print("=" * 80)
    print("🎙️ TEST AUDIO GENERATION WITH RETRY (15s delay)")
    print("=" * 80)
    print(f"Max retries: {max_retries}")
    print(f"Retry delay: {retry_delay}s")
    print()

    # Get first advanced conversation without audio
    db_manager = DBManager()
    conv = db_manager.db.conversation_library.find_one(
        {"level": "advanced", "has_audio": {"$ne": True}},
        sort=[("conversation_id", 1)],  # Get first one
    )

    if not conv:
        print("✅ No advanced conversations need audio!")
        return

    conversation_id = conv["conversation_id"]
    title = conv["title"]["en"]
    dialogue = conv.get("dialogue", [])

    print(f"📚 Conversation: {conversation_id}")
    print(f"   Title: {title}")
    print(f"   Dialogue turns: {len(dialogue)}")
    print()

    if not dialogue:
        print("❌ No dialogue found!")
        return

    # Build TTS script
    print("🔨 Building TTS script...")
    script = await build_tts_script(dialogue)
    print(f"   Speakers: {script['speaker_roles']}")
    print(f"   Lines: {len(script['lines'])}")
    print()

    # Initialize services
    print("🎙️ Initializing services...")
    tts_service = GoogleTTSService()
    r2_service = R2StorageService()
    print("   ✅ GoogleTTSService initialized")
    print("   ✅ R2StorageService initialized")
    print()

    # Get available voices
    print("🎵 Getting available voices...")
    all_voices = await tts_service.get_available_voices(language="en")
    male_voices = [v for v in all_voices if v["gender"] == "MALE"][:5]
    female_voices = [v for v in all_voices if v["gender"] == "FEMALE"][:5]
    print(f"   Available: {len(male_voices)} male, {len(female_voices)} female")
    print()

    # Select voices based on speaker roles
    voice_names = []
    for role in script["speaker_roles"]:
        if "male" in role.lower() and "female" not in role.lower():
            voice_names.append(male_voices[0]["name"] if male_voices else "Puck")
        else:
            voice_names.append(female_voices[0]["name"] if female_voices else "Kore")

    print(f"🎤 Selected voices: {voice_names}")
    print()

    # Retry loop for audio generation
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}")
            print(f"   Time: {time.strftime('%H:%M:%S')}")

            start_time = time.time()

            # Generate audio
            print("   📡 Calling Vertex AI TTS API...")
            audio_bytes, duration = await tts_service.generate_multi_speaker_audio(
                script=script,
                voice_names=voice_names,
                language="en",
                speaking_rate=1.0,
            )

            elapsed = time.time() - start_time

            print()
            print("   " + "=" * 76)
            print(f"   ✅ SUCCESS! Audio generated in {elapsed:.1f}s")
            print("   " + "=" * 76)
            print(f"   Size: {len(audio_bytes):,} bytes")
            print(f"   Duration: {duration.get('duration_seconds', 0)}s")
            print(f"   Model: {duration.get('model', 'N/A')}")
            print()

            # Upload to R2
            print("☁️  Uploading to R2...")
            r2_key = f"conversations/{conversation_id}.wav"

            upload_result = await r2_service.upload_file(
                file_content=audio_bytes, r2_key=r2_key, content_type="audio/wav"
            )

            audio_url = upload_result["public_url"]
            print(f"   ✅ URL: {audio_url}")
            print()

            # Update database
            print("💾 Updating database...")
            db_manager.db.conversation_library.update_one(
                {"conversation_id": conversation_id},
                {
                    "$set": {
                        "has_audio": True,
                        "audio_url": audio_url,
                        "audio_info": {
                            "r2_url": audio_url,
                            "r2_key": r2_key,
                            "duration": duration,
                            "format": "wav",
                            "voices_used": voice_names,
                            "api_latency_seconds": elapsed,
                        },
                    }
                },
            )
            print("   ✅ Database updated")
            print()

            print("=" * 80)
            print("🎉 TEST COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            return

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)

            elapsed = time.time() - start_time

            print()
            print("   " + "=" * 76)
            print(f"   ❌ FAILED after {elapsed:.1f}s")
            print("   " + "=" * 76)
            print(f"   Error Type: {error_type}")
            print(f"   Error: {error_msg[:200]}")
            print()

            if attempt < max_retries - 1:
                print(f"   ⏳ Waiting {retry_delay}s before retry...")
                await asyncio.sleep(retry_delay)
                print()
            else:
                print("=" * 80)
                print("❌ ALL RETRIES FAILED")
                print("=" * 80)
                print(f"Conversation: {conversation_id}")
                print(f"Total attempts: {max_retries}")
                print(f"Final error: {error_type} - {error_msg[:150]}")
                print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_audio_with_retry())
