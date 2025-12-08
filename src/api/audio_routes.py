"""
Standalone Audio API Routes
Endpoints for audio-related operations not tied to specific books/chapters
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Form, Query
from typing import Dict, Any, Optional
from src.middleware.firebase_auth import get_current_user
from src.services.google_tts_service import GoogleTTSService
from src.services.r2_storage_service import R2StorageService
import io
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger("chatbot")

router = APIRouter(
    prefix="/api/v1/audio",
    tags=["Audio"],
)

google_tts_service = GoogleTTSService()
r2_service = R2StorageService()


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
        audio_file = io.BytesIO(audio_content)
        audio_url = await r2_service.upload_file(
            file=audio_file, key=preview_key, content_type="audio/wav"
        )

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
