#!/usr/bin/env python3
"""
Generate Audio for Advanced Conversations using Gemini Multi-Speaker TTS

Target: All advanced level conversations without audio
Strategy: Parallel generation with 5 concurrent tasks
Model: Vertex AI Gemini 2.5 Pro TTS

RUN:
    docker exec -d ai-chatbot-rag python crawler/generate_advanced_audio.py

CHECK PROGRESS:
    docker logs ai-chatbot-rag --tail 50 | grep "🎙️"
"""

import sys
import asyncio
import random
from typing import List, Dict
from datetime import datetime
from tqdm.asyncio import tqdm

sys.path.append("/app")

from src.database.db_manager import DBManager
from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService
from src.services.library_manager import LibraryManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def build_tts_script(dialogue: List[Dict]) -> Dict:
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

    if len(speakers_seen) == 1:
        speaker_id = speakers_seen[0]
        gender = speaker_to_gender[speaker_id]
        speaker_roles = [f"{gender.capitalize()} 1", f"{gender.capitalize()} 2"]
        speaker_to_idx[speaker_id] = 0

    elif len(speakers_seen) == 2:
        for i, speaker_id in enumerate(speakers_seen[:2]):
            gender = speaker_to_gender[speaker_id]
            speaker_roles.append(gender.capitalize())
            speaker_to_idx[speaker_id] = i

    else:
        for i, speaker_id in enumerate(speakers_seen[:2]):
            gender = speaker_to_gender[speaker_id]
            speaker_roles.append(gender.capitalize())
            speaker_to_idx[speaker_id] = i

        for speaker_id in speakers_seen[2:]:
            gender = speaker_to_gender[speaker_id]
            matching_idx = None

            for idx, role in enumerate(speaker_roles):
                if role.lower() == gender:
                    matching_idx = idx
                    break

            if matching_idx is None:
                matching_idx = 0

            speaker_to_idx[speaker_id] = matching_idx

    lines = []
    for turn in sorted(dialogue, key=lambda x: x["order"]):
        speaker_id = turn["speaker"]
        text = turn.get("text_en", "").strip()

        if text:
            idx = speaker_to_idx.get(speaker_id, 0)
            lines.append({"speaker": idx, "text": text})

    return {"speaker_roles": speaker_roles, "lines": lines}


async def select_voices_by_gender(
    speaker_roles: List[str], tts_service: GoogleTTSService
) -> List[str]:
    """
    Select voices based on gender in speaker roles

    CRITICAL: Ensure different voices for same-gender conversations
    - Male-Female: Random 1 male + 1 female from pool of 5 each
    - Male-Male: Random 2 DIFFERENT males from pool of 5
    - Female-Female: Random 2 DIFFERENT females from pool of 5

    Random selection ensures variety across conversations
    """

    available_voices = await tts_service.get_available_voices("en")
    male_voices = [v for v in available_voices if v.get("gender") == "MALE"][
        :5
    ]  # Top 5
    female_voices = [v for v in available_voices if v.get("gender") == "FEMALE"][
        :5
    ]  # Top 5

    # Count how many male/female speakers needed
    num_male = sum(
        1
        for role in speaker_roles
        if "male" in role.lower() and "female" not in role.lower()
    )
    num_female = sum(1 for role in speaker_roles if "female" in role.lower())

    # Randomly select required number of voices (ensuring uniqueness for same-gender)
    selected_male_voices = (
        random.sample(male_voices, min(num_male, len(male_voices)))
        if num_male > 0 and male_voices
        else []
    )
    selected_female_voices = (
        random.sample(female_voices, min(num_female, len(female_voices)))
        if num_female > 0 and female_voices
        else []
    )

    # Build final voice list matching speaker_roles order
    selected_voices = []
    male_idx = 0
    female_idx = 0

    for role in speaker_roles:
        role_lower = role.lower()

        if "male" in role_lower and "female" not in role_lower:
            # Male speaker
            if male_idx < len(selected_male_voices):
                selected_voices.append(selected_male_voices[male_idx]["name"])
                male_idx += 1
            else:
                selected_voices.append("Puck")  # Fallback

        elif "female" in role_lower:
            # Female speaker
            if female_idx < len(selected_female_voices):
                selected_voices.append(selected_female_voices[female_idx]["name"])
                female_idx += 1
            else:
                selected_voices.append("Kore")  # Fallback
        else:
            # Unknown - randomly pick
            if random.choice([True, False]) and male_voices:
                selected_voices.append(random.choice(male_voices)["name"])
            elif female_voices:
                selected_voices.append(random.choice(female_voices)["name"])
            else:
                selected_voices.append("Puck")

    return selected_voices


async def generate_audio_for_conversation(
    conversation: Dict,
    tts_service: GoogleTTSService,
    r2_service: R2StorageService,
    library_manager: LibraryManager,
    db_manager: DBManager,
    semaphore: asyncio.Semaphore,
) -> Dict:
    """Generate audio for one conversation with retry"""

    async with semaphore:
        conversation_id = conversation["conversation_id"]
        dialogue = conversation.get("dialogue", [])

        if not dialogue:
            logger.warning(f"   ⚠️ {conversation_id}: No dialogue")
            return None

        for attempt in range(3):
            try:
                # Build TTS script
                script = await build_tts_script(dialogue)

                # Select voices
                voice_names = await select_voices_by_gender(
                    script["speaker_roles"], tts_service
                )

                # Generate audio
                audio_bytes, duration = await tts_service.generate_multi_speaker_audio(
                    script=script,
                    voice_names=voice_names,
                    language="en",
                    speaking_rate=1.0,
                )

                # Upload to R2
                r2_key = f"conversations/{conversation_id}.wav"
                upload_result = await r2_service.upload_file(
                    file_content=audio_bytes,
                    r2_key=r2_key,
                    content_type="audio/wav",
                )

                audio_url = upload_result["public_url"]

                # Save to library
                library_file = library_manager.save_library_file(
                    user_id="system",
                    filename=f"{conversation_id}.wav",
                    file_type="audio",
                    category="conversation",
                    r2_url=audio_url,
                    r2_key=r2_key,
                    file_size=len(audio_bytes),
                    mime_type="audio/wav",
                    metadata={
                        "conversation_id": conversation_id,
                        "duration_seconds": duration.get("duration_seconds"),
                        "voice_names": voice_names,
                        "speaker_roles": script["speaker_roles"],
                        "num_lines": len(script["lines"]),
                        "model": duration.get("model"),
                        "source_type": "ai_tts_conversation_advanced",
                    },
                )

                # Update conversation
                db_manager.db.conversation_library.update_one(
                    {"conversation_id": conversation_id},
                    {
                        "$set": {
                            "has_audio": True,
                            "audio_url": audio_url,
                            "audio_file_id": library_file["library_id"],
                            "audio_info": {
                                "r2_url": audio_url,
                                "r2_key": r2_key,
                                "duration": duration,
                                "format": "wav",
                                "voices_used": voice_names,
                                "generated_at": datetime.utcnow(),
                            },
                        }
                    },
                )

                return {
                    "conversation_id": conversation_id,
                    "success": True,
                    "audio_url": audio_url,
                    "duration": duration.get("duration_seconds", 0),
                }

            except Exception as e:
                if attempt < 2:
                    backoff = 2**attempt
                    await asyncio.sleep(backoff)
                    continue
                else:
                    logger.error(f"   ❌ {conversation_id}: {e}")
                    return {
                        "conversation_id": conversation_id,
                        "success": False,
                        "error": str(e),
                    }


async def main():
    print("=" * 80)
    print("🎙️ GENERATE AUDIO FOR ADVANCED CONVERSATIONS")
    print("=" * 80)
    print()

    # Database
    db_manager = DBManager()
    print(f"✅ Connected to MongoDB: {db_manager.db.name}")

    # Services
    tts_service = GoogleTTSService()
    r2_service = R2StorageService()
    library_manager = LibraryManager(db_manager.db)
    print("✅ Initialized services (TTS, R2, Library)")
    print()

    # Get advanced conversations without audio
    conversations = list(
        db_manager.db.conversation_library.find(
            {"level": "advanced", "has_audio": {"$ne": True}}
        )
    )

    print(f"📊 Found {len(conversations)} advanced conversations without audio")
    print()

    if len(conversations) == 0:
        print("✅ All advanced conversations already have audio!")
        return

    # Generate audio in parallel (5 concurrent)
    semaphore = asyncio.Semaphore(5)
    tasks = []

    for conv in conversations:
        tasks.append(
            generate_audio_for_conversation(
                conv, tts_service, r2_service, library_manager, db_manager, semaphore
            )
        )

    print(f"🚀 Generating audio for {len(tasks)} conversations (5 parallel)...")
    print()

    # Execute with progress bar
    results = []
    for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Progress"):
        result = await coro
        if result:
            results.append(result)

    print()

    # Summary
    success_count = sum(1 for r in results if r.get("success"))
    failed_count = len(results) - success_count

    total_duration = sum(r.get("duration", 0) for r in results if r.get("success"))

    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"✅ Success: {success_count}/{len(results)}")
    print(f"❌ Failed: {failed_count}")
    print(
        f"⏱️  Total audio duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)"
    )
    print()

    # Check final status
    final_count = db_manager.db.conversation_library.count_documents(
        {"level": "advanced", "has_audio": True}
    )
    total_advanced = db_manager.db.conversation_library.count_documents(
        {"level": "advanced"}
    )

    print(f"✅ Advanced conversations with audio: {final_count}/{total_advanced}")
    print()

    if failed_count > 0:
        print("Failed conversations:")
        for r in results:
            if not r.get("success"):
                print(f"  • {r['conversation_id']}: {r.get('error', 'Unknown error')}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
