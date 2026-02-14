#!/usr/bin/env python3
"""
Test audio generation for a single advanced conversation
"""

import sys
import asyncio

sys.path.append("/app")

from src.database.db_manager import DBManager
from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService


async def build_tts_script(dialogue):
    """Convert dialogue to TTS script"""
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


async def test_single_audio():
    print("=" * 80)
    print("🎙️ TEST SINGLE ADVANCED CONVERSATION AUDIO")
    print("=" * 80)

    # Get first advanced conversation without audio
    db_manager = DBManager()
    conv = db_manager.db.conversation_library.find_one(
        {"level": "advanced", "has_audio": {"$ne": True}}
    )

    if not conv:
        print("✅ No advanced conversations need audio!")
        return

    conversation_id = conv["conversation_id"]
    title = conv["title"]["en"]
    dialogue = conv.get("dialogue", [])

    print(f"\n📚 Conversation: {conversation_id}")
    print(f"   Title: {title}")
    print(f"   Dialogue turns: {len(dialogue)}")

    if not dialogue:
        print("❌ No dialogue found!")
        return

    # Build TTS script
    print("\n🔨 Building TTS script...")
    script = await build_tts_script(dialogue)
    print(f"   Speakers: {script['speaker_roles']}")
    print(f"   Lines: {len(script['lines'])}")

    # Initialize services
    print("\n🎙️ Initializing TTS service...")
    tts_service = GoogleTTSService()

    print("\n🎵 Generating audio...")
    try:
        # Get available voices
        all_voices = await tts_service.get_available_voices(language="en")
        male_voices = [v for v in all_voices if v["gender"] == "MALE"]
        female_voices = [v for v in all_voices if v["gender"] == "FEMALE"]

        print(
            f"   Available voices: {len(male_voices)} male, {len(female_voices)} female"
        )

        voice_names = []
        for role in script["speaker_roles"]:
            if "male" in role.lower():
                voice_names.append(male_voices[0]["name"] if male_voices else "Puck")
            else:
                voice_names.append(
                    female_voices[0]["name"] if female_voices else "Kore"
                )

        print(f"   Voices: {voice_names}")

        # Generate audio
        audio_bytes, duration = await tts_service.generate_multi_speaker_audio(
            script=script,
            voice_names=voice_names,
            language="en",
            speaking_rate=1.0,
        )

        print(f"\n✅ Audio generated successfully!")
        print(f"   Size: {len(audio_bytes)} bytes")
        print(f"   Duration: {duration.get('duration_seconds', 0)} seconds")

        # Upload to R2
        print("\n☁️  Uploading to R2...")
        r2_service = R2StorageService()
        r2_key = f"conversations/{conversation_id}.wav"

        upload_result = await r2_service.upload_file(
            file_content=audio_bytes, r2_key=r2_key, content_type="audio/wav"
        )

        audio_url = upload_result["public_url"]
        print(f"   URL: {audio_url}")

        # Update database
        print("\n💾 Updating database...")
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
                    },
                }
            },
        )

        print("✅ Test complete!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_single_audio())
