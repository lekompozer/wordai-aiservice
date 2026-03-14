"""
Standalone Audio API Routes
Endpoints for audio-related operations not tied to specific books/chapters
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Form, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from src.middleware.firebase_auth import get_current_user
from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService
from src.database.db_manager import DBManager
from src.services.library_manager import LibraryManager
import io
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger("chatbot")

router = APIRouter(
    prefix="/api/v1/audio",
    tags=["Audio"],
)

ai_audio_router = APIRouter(
    prefix="/ai/audio",
    tags=["Audio AI"],
)

google_tts_service = GoogleTTSService()
r2_service = R2StorageService()

# Initialize DB + library (lazy-shared across requests)
_db_manager = DBManager()
_db = _db_manager.db
_library_manager = LibraryManager(_db, s3_client=r2_service.s3_client)


@router.get(
    "/voices",
    summary="Get available TTS voices",
    description="List available Google TTS voices, optionally filtered by language",
)
async def get_tts_voices(
    language: Optional[str] = Query(
        default=None,
        description="Language code (vi, en, zh, etc.) - leave empty for all languages",
    ),
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get list of available TTS voices

    **Authentication:** Required

    **Query Parameters:**
    - `language` (optional): Filter by 2-letter language code (vi, en, zh, ja, ko, etc.)
      - If not provided, returns all available voices

    **Returns:**
    - List of voices with name, gender, language, and sample rate
    - Grouped by language if no filter applied

    **Example Response:**
    ```json
    {
      "success": true,
      "language": "vi",
      "voice_count": 7,
      "voices": [
        {
          "name": "Despina",
          "language": "vi",
          "gender": "Female",
          "sample_rate": 24000
        }
      ]
    }
    ```
    """
    try:
        if language:
            # Fetch voices for specific language
            voices = await google_tts_service.get_available_voices(language)
            return {
                "success": True,
                "language": language,
                "voice_count": len(voices),
                "voices": voices,
            }
        else:
            # Fetch all voices grouped by language
            all_voices = {}
            supported_languages = [
                "vi",
                "en",
                "zh",
                "ja",
                "ko",
                "th",
                "fr",
                "de",
                "es",
                "it",
                "pt",
                "ru",
                "ar",
                "hi",
                "id",
                "ms",
                "tl",
            ]

            for lang in supported_languages:
                try:
                    voices = await google_tts_service.get_available_voices(lang)
                    if voices:
                        all_voices[lang] = voices
                except Exception as e:
                    logger.warning(f"Failed to fetch voices for {lang}: {e}")
                    continue

            total_count = sum(len(v) for v in all_voices.values())

            return {
                "success": True,
                "language": "all",
                "voice_count": total_count,
                "voices_by_language": all_voices,
            }

    except Exception as e:
        logger.error(f"❌ Failed to fetch voices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/preview",
    summary="Preview TTS voice without saving",
    description="Generate a preview audio sample with selected voice (FREE - no points cost)",
)
async def preview_tts_voice(
    text: str = Form(
        ..., description="Text to convert to speech (max 500 characters for preview)"
    ),
    language: str = Form(default="vi", description="Language code (vi, en, zh, etc.)"),
    voice_name: Optional[str] = Form(
        default=None, description="Voice name (Despina, Gacrux, Enceladus, etc.)"
    ),
    speaking_rate: float = Form(
        default=1.0, description="Speed of speech (0.25 to 4.0)"
    ),
    pitch: float = Form(default=0.0, description="Pitch adjustment (-20.0 to 20.0)"),
    prompt: Optional[str] = Form(
        default=None,
        description="Optional voice style prompt (e.g., 'Say in a curious way')",
    ),
    use_pro_model: bool = Form(
        default=False,
        description="Use gemini-2.5-pro-preview-tts (higher quality)",
    ),
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generate a preview audio sample (FREE - no points cost, no save)

    **Authentication:** Required

    **Purpose:**
    - Test different voices before generating full chapter audio
    - Preview voice characteristics
    - No points deducted
    - Audio not saved to library
    - Temporary URL expires in 15 minutes

    **Parameters:**
    - `text`: Preview text (max 500 characters)
    - `language`: Language code
    - `voice_name`: Voice name (optional, uses default for language)
    - `speaking_rate`: Speech speed (0.25 to 4.0)
    - `pitch`: Pitch adjustment (-20.0 to 20.0)
    - `prompt`: Optional style instruction
    - `use_pro_model`: Use premium model (higher quality)

    **Returns:**
    - Temporary audio URL (expires in 15 minutes)
    - Audio metadata (duration, format, voice)
    - No points charged

    **Example Response:**
    ```json
    {
      "success": true,
      "preview_url": "https://static.wordai.pro/audio/previews/temp_xxx.wav",
      "duration": 12.5,
      "format": "wav",
      "voice_name": "Despina",
      "expires_at": "2024-12-08T10:15:00Z",
      "message": "Preview generated (FREE - no points cost)"
    }
    ```
    """
    try:
        user_id = user["uid"]

        # Validate text length for preview
        if len(text) > 500:
            raise HTTPException(
                status_code=400,
                detail="Preview text too long. Maximum 500 characters.",
            )

        if not text or len(text.strip()) == 0:
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        logger.info(
            f"🎙️ Generating preview audio for user {user_id}, language={language}, voice={voice_name}"
        )

        # Generate audio using Google TTS
        audio_content, metadata = await google_tts_service.generate_audio(
            text=text,
            language=language,
            voice_name=voice_name,
            speaking_rate=speaking_rate,
            pitch=pitch,
            prompt=prompt,
            use_pro_model=use_pro_model,
        )

        # Upload to R2 in previews folder (temporary)
        preview_id = str(uuid.uuid4())
        preview_filename = f"preview_{user_id}_{preview_id}.wav"
        preview_key = f"audio/previews/{preview_filename}"

        # Upload audio to R2
        upload_result = await r2_service.upload_file(
            file_content=audio_content,
            r2_key=preview_key,
            content_type="audio/wav",
        )
        audio_url = upload_result.get("public_url") or upload_result.get("url")

        # Calculate expiration time (15 minutes)
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        logger.info(
            f"✅ Preview audio generated for user {user_id}, expires at {expires_at}"
        )

        return {
            "success": True,
            "preview_url": audio_url,
            "duration": metadata.get("duration", 0),
            "format": metadata.get("format", "wav"),
            "voice_name": metadata.get("voice_name"),
            "language": language,
            "expires_at": expires_at.isoformat() + "Z",
            "message": "Preview generated successfully (FREE - no points cost)",
            "metadata": metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate preview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# AI Audio router — prefix /api/ai/audio  (mounted in app.py with prefix /api)
# ---------------------------------------------------------------------------


class GenerateAudioRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    voice_names: Optional[str] = None  # comma-separated, first value used
    language: str = "vi"
    speed: float = 1.0
    speaking_rate: float = 1.0  # alias for speed
    use_pro_model: bool = False
    prompt: Optional[str] = None
    filename: Optional[str] = None


@ai_audio_router.post(
    "/generate",
    summary="Generate TTS audio and save to Library",
    description="Generate AI text-to-speech audio, upload to R2, and save to the user's Library Audio.",
)
async def generate_audio_to_library(
    body: GenerateAudioRequest,
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    text = body.text
    voice = body.voice
    voice_names = body.voice_names
    language = body.language
    speed = body.speed
    speaking_rate = body.speaking_rate
    use_pro_model = body.use_pro_model
    prompt = body.prompt
    filename = body.filename
    """
    Generate standalone TTS audio and save to Library Audio.

    **Authentication:** Required

    **Features:**
    - Converts text to speech using Gemini TTS
    - Saves audio file to user's Library Audio
    - Returns public URL + library metadata
    - Supports all Gemini voices (Algenib, Despina, Aoede, Enceladus, etc.)

    **Points:** Free (no points deducted)
    """
    try:
        user_id = user["uid"]

        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Resolve voice name: `voice` takes priority, then first of `voice_names`
        resolved_voice: Optional[str] = None
        if voice and voice.strip():
            resolved_voice = voice.strip()
        elif voice_names and voice_names.strip():
            resolved_voice = voice_names.split(",")[0].strip() or None

        # Use the higher of speed / speaking_rate (in case frontend sends one or both)
        effective_rate = max(speed, speaking_rate)

        logger.info(
            f"🎙️ Generate audio: user={user_id}, voice={resolved_voice}, "
            f"lang={language}, rate={effective_rate}, pro={use_pro_model}, "
            f"{len(text)} chars"
        )

        # Generate TTS audio
        audio_content, metadata = await google_tts_service.generate_audio(
            text=text,
            language=language,
            voice_name=resolved_voice,
            speaking_rate=effective_rate,
            prompt=prompt,
            use_pro_model=use_pro_model,
        )

        # Upload to R2
        audio_id = str(uuid.uuid4())
        r2_key = f"audio/library/{user_id}/{audio_id}.wav"
        upload_result = await r2_service.upload_file(
            file_content=audio_content,
            r2_key=r2_key,
            content_type="audio/wav",
        )
        audio_url: str = (
            upload_result.get("public_url") or upload_result.get("url") or audio_id
        )

        # Determine library filename
        text_preview = text.strip()[:40].replace("/", "-").replace("\\", "-")
        lib_filename = (
            filename.strip() if filename and filename.strip() else f"{text_preview}.wav"
        )

        # Save to library_audio collection
        library_doc = _library_manager.save_library_file(
            user_id=user_id,
            filename=lib_filename,
            file_type="audio",
            category="audio",
            r2_url=audio_url,
            r2_key=r2_key,
            file_size=len(audio_content),
            mime_type="audio/wav",
            metadata={
                "source_type": "tts_standalone",
                "voice_name": metadata.get("voice_name") or resolved_voice,
                "language": language,
                "speaking_rate": effective_rate,
                "use_pro_model": use_pro_model,
                "model": metadata.get("model"),
                "text_preview": text.strip()[:100],
                "word_count": metadata.get("word_count", 0),
                "duration": metadata.get("duration", 0),
            },
        )

        library_id = library_doc.get("library_id") or library_doc.get("file_id")

        logger.info(
            f"✅ Audio saved to library: {library_id} for user {user_id}, "
            f"voice={metadata.get('voice_name')}, ~{metadata.get('duration', 0):.1f}s"
        )

        return {
            "success": True,
            "audio_url": audio_url,
            "library_id": library_id,
            "filename": lib_filename,
            "duration": metadata.get("duration", 0),
            "format": "wav",
            "voice_name": metadata.get("voice_name") or resolved_voice,
            "language": language,
            "model": metadata.get("model"),
            "file_size": len(audio_content),
            "message": "Audio generated and saved to library",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
