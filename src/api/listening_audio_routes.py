"""
Listening Test Audio Management Routes
Endpoints for editing transcript and regenerating audio
"""

import logging
from typing import Optional
from datetime import datetime
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.middleware.auth import verify_firebase_token as require_auth
from src.services.online_test_utils import get_mongodb_service
from src.services.listening_test_generator_service import (
    get_listening_test_generator,
)

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/tests", tags=["Listening Audio Management"])


# ========== Request Models ==========


class UpdateTranscriptRequest(BaseModel):
    """Request to update transcript for a listening test section"""

    section_number: int = Field(..., ge=1, description="Audio section number to update")
    transcript: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="New transcript text (50-5000 characters)",
    )


class GenerateAudioFromTranscriptRequest(BaseModel):
    """Request to generate new audio from transcript"""

    section_number: int = Field(..., ge=1, description="Audio section number")
    voice_names: Optional[list[str]] = Field(
        None, description="Optional voice names (e.g., ['Aoede', 'Charon'])"
    )
    speaking_rate: float = Field(
        1.0, ge=0.5, le=2.0, description="Speaking rate (0.5-2.0)"
    )
    use_pro_model: bool = Field(False, description="Use pro TTS model")


class ApplyAudioRequest(BaseModel):
    """Request to apply a library audio file to test section"""

    section_number: int = Field(..., ge=1, description="Audio section number")
    library_file_id: str = Field(..., description="Library file ID from generate step")


# ========== Endpoints ==========


@router.patch("/{test_id}/transcript")
async def update_test_transcript(
    test_id: str,
    request: UpdateTranscriptRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Update transcript for a listening test audio section

    **Use Case:** User wants to edit transcript before regenerating audio

    **Flow:**
    1. Fetch test from DB
    2. Verify ownership
    3. Update transcript for specified section
    4. Save to DB

    **Example:**
    ```json
    {
      "section_number": 1,
      "transcript": "Speaker 1: Hello, how are you?\nSpeaker 2: I'm fine, thanks!"
    }
    ```
    """
    try:
        user_id = user_info["uid"]

        logger.info(f"📝 Update transcript request for test {test_id}")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Section: {request.section_number}")

        # Get test from DB
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test = collection.find_one({"_id": ObjectId(test_id)})
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify ownership
        if test.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can update transcript"
            )

        # Verify test type
        if test.get("test_type") != "listening":
            raise HTTPException(
                status_code=400,
                detail="This endpoint is only for listening tests",
            )

        # Find section
        audio_sections = test.get("audio_sections", [])
        section_found = False

        for section in audio_sections:
            if section.get("section_number") == request.section_number:
                section["transcript"] = request.transcript
                section["transcript_updated_at"] = datetime.now()
                section_found = True
                break

        if not section_found:
            raise HTTPException(
                status_code=404,
                detail=f"Audio section {request.section_number} not found",
            )

        # Update DB
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "audio_sections": audio_sections,
                    "updated_at": datetime.now(),
                }
            },
        )

        logger.info(f"✅ Transcript updated for section {request.section_number}")

        return {
            "success": True,
            "message": f"Transcript updated for section {request.section_number}",
            "section_number": request.section_number,
            "transcript": request.transcript,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update transcript: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{test_id}/audio/generate")
async def generate_audio_from_transcript(
    test_id: str,
    request: GenerateAudioFromTranscriptRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Generate new audio from transcript and save to Library

    **Use Case:** User edited transcript, wants to generate new audio

    **Flow:**
    1. Fetch test + transcript from DB
    2. Verify ownership
    3. Parse transcript to structured format
    4. Generate audio with TTS
    5. Upload to R2 + save to Library
    6. Return library_file_id (user can preview/download)

    **Note:** This does NOT update the test yet. Use PATCH /{test_id}/audio/apply
    to apply the new audio to the test.

    **Example:**
    ```json
    {
      "section_number": 1,
      "voice_names": ["Aoede", "Charon"],
      "speaking_rate": 1.0,
      "use_pro_model": false
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "library_file_id": "file_abc123",
      "audio_url": "https://r2.example.com/audio.wav",
      "duration_seconds": 45,
      "message": "Audio generated and saved to Library"
    }
    ```
    """
    try:
        user_id = user_info["uid"]

        logger.info(f"🎵 Generate audio request for test {test_id}")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Section: {request.section_number}")

        # Get test from DB
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test = collection.find_one({"_id": ObjectId(test_id)})
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify ownership
        if test.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can generate audio"
            )

        # Verify test type
        if test.get("test_type") != "listening":
            raise HTTPException(
                status_code=400,
                detail="This endpoint is only for listening tests",
            )

        # Find section
        audio_sections = test.get("audio_sections", [])
        target_section = None

        for section in audio_sections:
            if section.get("section_number") == request.section_number:
                target_section = section
                break

        if not target_section:
            raise HTTPException(
                status_code=404,
                detail=f"Audio section {request.section_number} not found",
            )

        # Get transcript
        transcript_text = target_section.get("transcript")
        if not transcript_text:
            raise HTTPException(
                status_code=400,
                detail=f"Section {request.section_number} has no transcript",
            )

        # Get language from test
        language = test.get("language", "en")

        # Detect number of speakers from transcript
        lines = transcript_text.strip().split("\n")
        num_speakers = 1
        if any(":" in line for line in lines):
            # Has speaker labels
            speakers = set()
            for line in lines:
                if ":" in line:
                    speaker = line.split(":", 1)[0].strip()
                    speakers.add(speaker)
            num_speakers = len(speakers)

        logger.info(f"   Detected {num_speakers} speaker(s) in transcript")

        # Initialize generator
        generator = get_listening_test_generator()

        # Parse transcript
        parsed_script = generator._parse_user_transcript(
            transcript_text=transcript_text,
            num_speakers=num_speakers,
            language=language,
        )

        logger.info(f"   Parsed: {len(parsed_script['lines'])} lines")

        # Auto-select voices if not provided
        voice_names = request.voice_names
        if not voice_names:
            voice_names = await generator._select_voices_by_gender(
                parsed_script.get("speaker_roles", []), language
            )
            logger.info(f"   🎙️ Auto-selected voices: {voice_names}")

        # Generate audio
        logger.info(f"   🔊 Generating audio with TTS...")
        audio_bytes, duration = await generator._generate_section_audio(
            script=parsed_script,
            voice_names=voice_names,
            language=language,
            speaking_rate=request.speaking_rate,
            use_pro_model=request.use_pro_model,
            force_num_speakers=num_speakers,
        )

        logger.info(f"   ✅ Audio generated: {len(audio_bytes)} bytes, ~{duration}s")

        # Upload to R2 and save to Library
        logger.info(f"   ☁️ Uploading to R2 + Library...")
        audio_url, library_file_id = await generator._upload_audio_to_r2(
            audio_bytes=audio_bytes,
            creator_id=user_id,
            test_id=test_id,
            section_num=request.section_number,
        )

        logger.info(f"   ✅ Saved to Library: {library_file_id}")

        return {
            "success": True,
            "library_file_id": library_file_id,
            "audio_url": audio_url,
            "duration_seconds": duration,
            "voice_names": voice_names,
            "num_speakers": num_speakers,
            "message": f"Audio generated and saved to Library. Use PATCH /{test_id}/audio/apply to apply it to the test.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{test_id}/audio/apply")
async def apply_audio_to_test(
    test_id: str,
    request: ApplyAudioRequest,
    user_info: dict = Depends(require_auth),
):
    """
    Apply a library audio file to a test section

    **Use Case:** User generated audio with POST /audio/generate, now wants to
    apply it to the test (replace old audio URL)

    **Flow:**
    1. Fetch test from DB
    2. Verify ownership
    3. Fetch audio file from Library
    4. Update test section with new audio_url + audio_file_id
    5. Save to DB

    **Example:**
    ```json
    {
      "section_number": 1,
      "library_file_id": "file_abc123"
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "message": "Audio applied to section 1",
      "section_number": 1,
      "audio_url": "https://r2.example.com/audio.wav"
    }
    ```
    """
    try:
        user_id = user_info["uid"]

        logger.info(f"🎵 Apply audio request for test {test_id}")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Section: {request.section_number}")
        logger.info(f"   Library File: {request.library_file_id}")

        # Get test from DB
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["online_tests"]

        test = collection.find_one({"_id": ObjectId(test_id)})
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Verify ownership
        if test.get("creator_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only test owner can apply audio"
            )

        # Verify test type
        if test.get("test_type") != "listening":
            raise HTTPException(
                status_code=400,
                detail="This endpoint is only for listening tests",
            )

        # Get library file
        library_collection = mongo_service.db["library"]
        library_file = library_collection.find_one(
            {
                "$or": [
                    {"library_id": request.library_file_id},
                    {"file_id": request.library_file_id},
                ]
            }
        )

        if not library_file:
            raise HTTPException(
                status_code=404,
                detail=f"Library file {request.library_file_id} not found",
            )

        # Verify file ownership
        if library_file.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Library file does not belong to you"
            )

        # Get audio URL
        audio_url = library_file.get("r2_url")
        if not audio_url:
            raise HTTPException(status_code=400, detail="Library file has no audio URL")

        # Find section and update
        audio_sections = test.get("audio_sections", [])
        section_found = False

        for section in audio_sections:
            if section.get("section_number") == request.section_number:
                section["audio_url"] = audio_url
                section["audio_file_id"] = request.library_file_id
                section["audio_updated_at"] = datetime.now()
                section_found = True
                break

        if not section_found:
            raise HTTPException(
                status_code=404,
                detail=f"Audio section {request.section_number} not found",
            )

        # Update DB
        collection.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "audio_sections": audio_sections,
                    "updated_at": datetime.now(),
                }
            },
        )

        logger.info(
            f"✅ Audio applied to section {request.section_number}: {audio_url}"
        )

        return {
            "success": True,
            "message": f"Audio applied to section {request.section_number}",
            "section_number": request.section_number,
            "audio_url": audio_url,
            "audio_file_id": request.library_file_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to apply audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
