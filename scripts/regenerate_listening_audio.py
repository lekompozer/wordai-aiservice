"""
Script to regenerate audio for listening test section
Run on production server to fix corrupted audio file
"""

import asyncio
import sys
import os
from pymongo import MongoClient
from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService
from src.services.library_manager import LibraryManager
import uuid

# Test ID
TEST_ID = "6936d221a11e73fd977f2629"
SECTION_NUMBER = 1


async def regenerate_audio():
    """Regenerate audio for listening test section"""

    print(f"🎙️ Starting audio regeneration for test {TEST_ID}, section {SECTION_NUMBER}")

    # 1. Connect to MongoDB (use authenticated connection)
    mongo_uri = os.getenv(
        "MONGODB_URI_AUTH",
        "mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin",
    )
    client = MongoClient(mongo_uri)
    db = client.ai_service_db  # Use correct database name

    print("✅ Connected to MongoDB")  # 2. Get test data
    test = db.online_tests.find_one({"test_id": TEST_ID})
    if not test:
        # Try with ObjectId
        from bson import ObjectId

        try:
            test = db.online_tests.find_one({"_id": ObjectId(TEST_ID)})
        except:
            pass

    if not test:
        print(f"❌ Test {TEST_ID} not found")
        return

    print(f"✅ Found test: {test.get('title')}")

    # 3. Get audio section
    audio_sections = test.get("audio_sections", [])
    if not audio_sections or len(audio_sections) < SECTION_NUMBER:
        print(f"❌ Audio section {SECTION_NUMBER} not found")
        return

    section = audio_sections[SECTION_NUMBER - 1]
    script = section.get("script", {})
    speaker_roles = script.get("speaker_roles", [])
    lines = script.get("lines", [])
    voice_config = section.get("voice_config", {})

    print(f"✅ Audio section found: {section.get('section_title')}")
    print(f"   - Speakers: {speaker_roles}")
    print(f"   - Lines: {len(lines)}")
    print(f"   - Voice names: {voice_config.get('voice_names', [])}")

    # 4. Initialize services
    tts_service = GoogleTTSService()
    r2_service = R2StorageService()
    library_manager = LibraryManager(db, s3_client=r2_service.s3_client)

    print("✅ Services initialized")

    # 5. Generate audio using TTS
    print("🎙️ Generating audio with Gemini TTS...")

    voice_names = voice_config.get("voice_names", ["Aoede", "Charon"])
    language = test.get("language", "en")
    use_pro_model = False  # Use flash model for faster generation

    num_speakers = len(speaker_roles)
    print(f"   Speakers: {num_speakers} - {speaker_roles}")
    print(f"   Voices: {voice_names}")
    print(f"   Lines: {len(lines)}")

    try:
        if num_speakers > 1:
            # Use multi-speaker TTS
            audio_content, metadata = await tts_service.generate_multi_speaker_audio(
                script={"speaker_roles": speaker_roles, "lines": lines},
                voice_names=voice_names,
                language=language,
                speaking_rate=1.0,
                use_pro_model=use_pro_model,
            )
            print(f"✅ Multi-speaker audio generated successfully")
        else:
            # Use single-speaker TTS
            full_text = ""
            for line in lines:
                speaker_idx = line["speaker"]
                speaker_role = speaker_roles[speaker_idx]
                text = line["text"]
                full_text += f"{speaker_role}: {text}\n\n"

            voice_name = voice_names[0] if voice_names else None

            audio_content, metadata = await tts_service.generate_audio(
                text=full_text,
                language=language,
                voice_name=voice_name,
                speaking_rate=1.0,
                use_pro_model=use_pro_model,
            )
            print(f"✅ Single-speaker audio generated successfully")

        print(f"   - Duration: {metadata.get('duration_seconds', 0):.1f}s")
        print(f"   - Model: {metadata.get('model')}")
        print(f"   - Size: {len(audio_content) / 1024 / 1024:.2f} MB")

    except Exception as e:
        print(f"❌ Failed to generate audio: {e}")
        import traceback

        traceback.print_exc()
        return

    # 6. Archive old audio file
    old_audio_file_id = section.get("audio_file_id")
    if old_audio_file_id:
        print(f"📦 Old audio file: {old_audio_file_id} (will be replaced)")

    # 7. Upload new audio to R2
    print("☁️ Uploading to R2...")

    creator_id = test.get("creator_id")
    file_id = str(uuid.uuid4())
    r2_key = (
        f"listening-tests/{creator_id}/{TEST_ID}/section_{SECTION_NUMBER}_{file_id}.wav"
    )

    try:
        await r2_service.upload_file(
            file_content=audio_content, r2_key=r2_key, content_type="audio/wav"
        )
        audio_url = r2_service.get_public_url(r2_key)
        print(f"✅ Uploaded to R2: {r2_key}")
        print(f"   - URL: {audio_url}")

    except Exception as e:
        print(f"❌ Failed to upload to R2: {e}")
        import traceback

        traceback.print_exc()
        return

    # 8. Save to library
    print("💾 Saving to library...")

    try:
        library_file = library_manager.save_library_file(
            user_id=creator_id,
            filename=f"section_{SECTION_NUMBER}_regenerated.wav",
            file_type="audio",
            category="audio",
            r2_url=audio_url,
            r2_key=r2_key,
            file_size=len(audio_content),
            mime_type="audio/wav",
            metadata={
                "test_id": TEST_ID,
                "audio_section": SECTION_NUMBER,
                "source_type": "ai_tts_regenerated",
                "audio_format": "wav",
                "duration_seconds": metadata.get("duration_seconds"),
                "voice_names": voice_names,
                "model": metadata.get("model"),
            },
        )

        new_audio_file_id = str(library_file["_id"])
        print(f"✅ Saved to library: {new_audio_file_id}")

    except Exception as e:
        print(f"❌ Failed to save to library: {e}")
        import traceback

        traceback.print_exc()
        return

    # 9. Update test document
    print("💾 Updating test document...")

    section["audio_url"] = audio_url
    section["audio_file_id"] = new_audio_file_id
    section["duration_seconds"] = metadata.get("duration_seconds")
    section["has_audio"] = True

    try:
        db.online_tests.update_one(
            {"test_id": TEST_ID},
            {"$set": {f"audio_sections.{SECTION_NUMBER - 1}": section}},
        )
        print(f"✅ Updated test document")

    except Exception as e:
        print(f"❌ Failed to update test: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n🎉 Audio regeneration completed successfully!")
    print(f"   - New audio URL: {audio_url}")
    print(f"   - Duration: {metadata.get('duration_seconds', 0):.1f}s")
    print(f"   - Test URL: https://wordai.pro/online-test/{TEST_ID}")


if __name__ == "__main__":
    asyncio.run(regenerate_audio())
