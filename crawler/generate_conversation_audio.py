"""
Generate Audio for Conversations using Gemini Multi-Speaker TTS

Cấu trúc conversation trong DB:
- dialogue: [{speaker, gender, text_en, text_vi, order}]
- has_audio: false (cần update sau khi generate)
- audio_info: {url, duration, format, voices_used}

Quy trình:
1. Lấy conversations chưa có audio
2. Build script format cho TTS (speaker_roles + lines)
3. Gọi GoogleTTSService.generate_multi_speaker_audio()
4. Upload audio lên Cloud Storage
5. Update conversation với audio_info

Gender mapping:
- male → MALE voice (Puck, Charon, Fenrir, etc.)
- female → FEMALE voice (Kore, Leda, Aoede, etc.)
"""

import sys
import asyncio
import argparse
import random
from typing import List, Dict
from datetime import datetime

sys.path.append("/app")

from src.database.db_manager import DBManager
from src.services.google_tts_service import GoogleTTSService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def build_tts_script(dialogue: List[Dict]) -> Dict:
    """
    Convert conversation dialogue to TTS script format for Gemini TTS

    LIMITATION: Gemini TTS supports max 2 speakers
    STRATEGY: Map first 2 unique speakers to speaker 0 and 1
              If >2 speakers, merge remaining speakers into first 2 by gender

    Input (dialogue):
    [
        {speaker: 'A', gender: 'male', text_en: 'Hello', order: 1},
        {speaker: 'B', gender: 'female', text_en: 'Hi', order: 2},
        {speaker: 'C', gender: 'male', text_en: 'How are you?', order: 3}
    ]

    Output (TTS script):
    {
        'speaker_roles': ['Male', 'Female'],  # Max 2 roles
        'lines': [
            {'speaker': 0, 'text': 'Hello'},     # A (male) → speaker 0
            {'speaker': 1, 'text': 'Hi'},        # B (female) → speaker 1
            {'speaker': 0, 'text': 'How are you?'}  # C (male) → speaker 0 (merge with A)
        ]
    }
    """

    # Identify unique speakers in order of appearance
    speakers_seen = []
    speaker_to_gender = {}

    for turn in sorted(dialogue, key=lambda x: x["order"]):
        speaker_id = turn["speaker"]
        gender = turn.get("gender", "male").lower()

        if speaker_id not in speakers_seen:
            speakers_seen.append(speaker_id)
            speaker_to_gender[speaker_id] = gender

    # Map speakers to roles (max 2 speakers)
    speaker_to_idx = {}
    speaker_roles = []

    if len(speakers_seen) == 1:
        # Single speaker conversation - use 2 voices of same gender for variety
        speaker_id = speakers_seen[0]
        gender = speaker_to_gender[speaker_id]
        gender_cap = gender.capitalize()

        speaker_roles = [f"{gender_cap} 1", f"{gender_cap} 2"]
        speaker_to_idx[speaker_id] = 0  # Will alternate in lines

    elif len(speakers_seen) == 2:
        # 2 speakers - map directly
        for i, speaker_id in enumerate(speakers_seen[:2]):
            gender = speaker_to_gender[speaker_id]
            speaker_roles.append(gender.capitalize())
            speaker_to_idx[speaker_id] = i

    else:
        # >2 speakers - merge by gender
        # Map first 2 speakers directly
        for i, speaker_id in enumerate(speakers_seen[:2]):
            gender = speaker_to_gender[speaker_id]
            speaker_roles.append(gender.capitalize())
            speaker_to_idx[speaker_id] = i

        # Merge remaining speakers by gender into first 2
        speaker_0_gender = speaker_to_gender[speakers_seen[0]]
        speaker_1_gender = speaker_to_gender[speakers_seen[1]]

        for speaker_id in speakers_seen[2:]:
            gender = speaker_to_gender[speaker_id]
            # Merge with speaker that has same gender, or speaker 0 if no match
            if gender == speaker_0_gender:
                speaker_to_idx[speaker_id] = 0
            elif gender == speaker_1_gender:
                speaker_to_idx[speaker_id] = 1
            else:
                speaker_to_idx[speaker_id] = 0  # Default to speaker 0

    # Build lines array
    lines = []
    for turn in sorted(dialogue, key=lambda x: x["order"]):
        speaker_id = turn["speaker"]
        speaker_idx = speaker_to_idx.get(speaker_id, 0)

        lines.append(
            {
                "speaker": speaker_idx,  # Integer index (0 or 1)
                "text": turn["text_en"],  # Use English text
            }
        )

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
    conversation_id: str,
    dialogue: List[Dict],
    tts_service: GoogleTTSService,
    db_manager: DBManager,
) -> Dict:
    """
    Generate audio for one conversation

    Returns:
        Dict with audio info (url, duration, voices_used) or None if failed
    """

    logger.info(f"🎙️ Generating audio for: {conversation_id}")

    try:
        # Build TTS script
        script = await build_tts_script(dialogue)
        logger.info(f"   Speakers: {script['speaker_roles']}")
        logger.info(f"   Lines: {len(script['lines'])}")

        # Select voices based on gender
        voice_names = await select_voices_by_gender(
            script["speaker_roles"], tts_service
        )
        logger.info(f"   Voices: {voice_names}")

        # Generate multi-speaker audio
        audio_bytes, duration = await tts_service.generate_multi_speaker_audio(
            script=script, voice_names=voice_names, language="en", speaking_rate=1.0
        )

        logger.info(f"   ✅ Generated audio: {len(audio_bytes)} bytes, {duration}s")

        # Upload to R2 storage
        from src.services.r2_storage_service import R2StorageService
        from src.services.library_manager import LibraryManager

        r2_service = R2StorageService()
        library_manager = LibraryManager(db_manager.db)

        # Generate R2 key
        r2_key = f"conversations/{conversation_id}.wav"

        # Upload to R2
        upload_result = await r2_service.upload_file(
            file_content=audio_bytes,
            r2_key=r2_key,
            content_type="audio/wav",
        )

        audio_url = upload_result["public_url"]
        logger.info(f"   ☁️ Uploaded to R2: {r2_key}")

        # Save to library
        library_file = library_manager.save_library_file(
            user_id="system",  # System-generated
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
                "source_type": "ai_tts_conversation",
            },
        )

        logger.info(f"   📚 Saved to library: {library_file['library_id']}")

        # Update conversation in DB
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

        logger.info(f"   ✅ Updated DB for {conversation_id}")

        # Return audio info
        return {
            "audio_url": audio_url,
            "r2_key": r2_key,
            "library_file_id": library_file["library_id"],
            "duration": duration,
            "format": "wav",
            "voices_used": voice_names,
            "generated_at": datetime.utcnow(),
        }

    except Exception as e:
        logger.error(f"   ❌ Failed to generate audio: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_generate_audio(num_conversations: int = 2):
    """Test audio generation with first N conversations"""

    logger.info("=" * 80)
    logger.info(f"TEST AUDIO GENERATION FOR {num_conversations} CONVERSATIONS")
    logger.info("=" * 80)

    # Connect to DB
    db_manager = DBManager()
    logger.info(f"✅ Connected to MongoDB: {db_manager.db.name}")

    # Initialize TTS service
    tts_service = GoogleTTSService()
    logger.info("✅ Initialized GoogleTTSService")

    # Get conversations without audio
    conversations = list(
        db_manager.db.conversation_library.find({"has_audio": False}).limit(
            num_conversations
        )
    )

    logger.info(f"📊 Found {len(conversations)} conversations to process")
    print()

    # Generate audio for each
    success = 0
    failed = 0

    for conv in conversations:
        conv_id = conv["conversation_id"]
        dialogue = conv.get("dialogue", [])

        if not dialogue:
            logger.warning(f"⚠️ Skipping {conv_id}: No dialogue")
            continue

        # Generate audio
        audio_info = await generate_audio_for_conversation(
            conv_id, dialogue, tts_service, db_manager
        )

        if audio_info:
            success += 1

            # Update DB (set has_audio=True và audio_info)
            db_manager.db.conversation_library.update_one(
                {"conversation_id": conv_id},
                {
                    "$set": {
                        "has_audio": True,
                        "audio_info": {
                            "local_path": audio_info["local_path"],
                            "duration": audio_info["duration"],
                            "format": audio_info["format"],
                            "voices_used": audio_info["voices_used"],
                            "generated_at": audio_info["generated_at"],
                        },
                    }
                },
            )
            logger.info(f"   ✅ Updated DB for {conv_id}")
        else:
            failed += 1

        print()

    logger.info("=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"✅ Success: {success}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"📁 Audio files saved to: /tmp/conversation_audio/")
    logger.info("   Download with: scp root@SERVER:/tmp/conversation_audio/*.wav ./")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num", type=int, default=2, help="Number of conversations to test"
    )
    args = parser.parse_args()

    asyncio.run(test_generate_audio(args.num))
