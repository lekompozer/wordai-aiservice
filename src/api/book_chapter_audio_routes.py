"""
Book Chapter Audio Routes
API endpoints for managing audio narration for book chapters
"""

import logging
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
)
from typing import Dict, Any, Optional
from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.services.audio_service import AudioService
from src.services.r2_storage_service import R2StorageService
from src.services.library_manager import LibraryManager
from src.services.book_manager import UserBookManager
from src.services.book_permission_manager import BookPermissionManager
from src.services.google_tts_service import GoogleTTSService
from src.services.subscription_manager import SubscriptionManager

logger = logging.getLogger("chatbot")

router = APIRouter(
    prefix="/api/v1/books/{book_id}/chapters/{chapter_id}/audio",
    tags=["Chapter Audio"],
)

# Initialize services
db_manager = DBManager()
db = db_manager.db

r2_service = R2StorageService()
library_manager = LibraryManager(db, s3_client=r2_service.s3_client)
audio_service = AudioService(
    db=db, r2_service=r2_service, library_manager=library_manager
)
book_manager = UserBookManager(db)
permission_manager = BookPermissionManager(db)
google_tts_service = GoogleTTSService()
subscription_manager = SubscriptionManager(db)


def get_audio_service() -> AudioService:
    """Get audio service instance"""
    return audio_service


def get_permission_manager() -> BookPermissionManager:
    """Get permission manager instance"""
    return permission_manager


@router.post("/upload", status_code=200, summary="Upload audio file for chapter")
async def upload_audio(
    book_id: str,
    chapter_id: str,
    audio_file: UploadFile = File(..., description="Audio file (MP3, WAV, M4A, OGG)"),
    language: Optional[str] = Form(
        None, description="Language code for translation audio"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
    audio_svc: AudioService = Depends(get_audio_service),
    perm_manager: BookPermissionManager = Depends(get_permission_manager),
):
    """
    **Upload audio file for chapter (Owner only)**

    Uploads audio narration file and saves to chapter config.

    **Authentication:** Required (Owner only)

    **Request:**
    - Multipart form-data with audio file
    - Optional language code for translation

    **Supported Formats:**
    - MP3 (recommended)
    - WAV
    - M4A
    - OGG

    **Max Size:** 50MB

    **Points Cost:** FREE (0 points)

    **Returns:**
    - 200: Audio uploaded successfully
    - 400: Invalid file format or size
    - 403: Not book owner
    - 404: Book or chapter not found
    """
    try:
        user_id = current_user["uid"]

        # Check ownership
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only book owner can upload audio"
            )

        # Get chapter
        chapter = db.book_chapters.find_one(
            {"chapter_id": chapter_id, "book_id": book_id}
        )
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Read file content
        file_content = await audio_file.read()

        # Upload audio
        audio_info = await audio_svc.upload_audio_file(
            user_id=user_id,
            book_id=book_id,
            chapter_id=chapter_id,
            file_content=file_content,
            filename=audio_file.filename,
            content_type=audio_file.content_type,
            language=language,
        )

        # Save to chapter
        audio_svc.save_audio_to_chapter(
            chapter_id=chapter_id,
            audio_url=audio_info["audio_url"],
            audio_file_id=audio_info["audio_file_id"],
            file_size_bytes=audio_info["file_size_bytes"],
            audio_format=audio_info["format"],
            source_type="user_upload",
            language=language,
            generated_by_user_id=user_id,
        )

        logger.info(
            f"✅ User {user_id} uploaded audio for chapter {chapter_id}, lang={language or 'default'}"
        )

        return {
            "success": True,
            "audio_url": audio_info["audio_url"],
            "audio_file_id": audio_info["audio_file_id"],
            "file_size_bytes": audio_info["file_size_bytes"],
            "format": audio_info["format"],
            "source_type": "user_upload",
            "message": "Audio uploaded successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to upload audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", status_code=200, summary="Get chapter audio")
async def get_chapter_audio(
    book_id: str,
    chapter_id: str,
    language: Optional[str] = Query(None, description="Language code"),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    audio_svc: AudioService = Depends(get_audio_service),
    perm_manager: BookPermissionManager = Depends(get_permission_manager),
):
    """
    **Get audio for chapter**

    Returns audio URL for playback. Respects book permissions.

    **Priority:**
    1. Owner's audio (from chapter.audio_config)
    2. User's audio (from user's library)
    3. No audio available

    **Authentication:** Optional (required for premium books)

    **Query Parameters:**
    - `language`: Get audio for specific language

    **Returns:**
    - 200: Audio info with URL
    - 404: No audio available
    - 403: Purchase required (premium books)
    """
    try:
        user_id = current_user["uid"] if current_user else None

        # Get book
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        # Get chapter
        chapter = db.book_chapters.find_one(
            {"chapter_id": chapter_id, "book_id": book_id}
        )
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Check permissions
        is_owner = user_id and book.get("user_id") == user_id
        is_public = book.get("is_published") and chapter.get("is_published")
        is_preview = chapter.get("is_preview_free")

        if not is_owner:
            if not is_public and not is_preview:
                # Premium chapter - check purchase
                if not user_id:
                    raise HTTPException(
                        status_code=401, detail="Authentication required"
                    )

                has_access = perm_manager.check_user_book_access(user_id, book_id)
                if not has_access:
                    raise HTTPException(
                        status_code=403, detail="Purchase required to access audio"
                    )

        # Priority 1: Owner's audio
        owner_audio = audio_svc.get_chapter_audio(chapter_id, language)
        if owner_audio:
            return {
                "audio_available": True,
                "audio_url": owner_audio.get("audio_url"),
                "duration_seconds": owner_audio.get("duration_seconds"),
                "format": owner_audio.get("format"),
                "source_type": owner_audio.get("source_type"),
                "voice_settings": owner_audio.get("voice_settings"),
                "source": "owner",
            }

        # Priority 2: User's audio (if authenticated)
        if user_id:
            user_audio = audio_svc.get_user_audio_for_chapter(
                user_id, chapter_id, language
            )
            if user_audio:
                metadata = user_audio.get("metadata", {})
                return {
                    "audio_available": True,
                    "audio_url": user_audio.get("r2_url"),
                    "duration_seconds": metadata.get("duration_seconds"),
                    "format": metadata.get("audio_format"),
                    "source_type": metadata.get("source_type"),
                    "voice_settings": metadata.get("voice_settings"),
                    "source": "user_library",
                }

        # No audio available
        raise HTTPException(
            status_code=404,
            detail={
                "audio_available": False,
                "message": "No audio attached to this chapter",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("", status_code=200, summary="Delete chapter audio")
async def delete_chapter_audio(
    book_id: str,
    chapter_id: str,
    language: Optional[str] = Query(None, description="Language code"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    audio_svc: AudioService = Depends(get_audio_service),
):
    """
    **Delete audio from chapter (Owner only)**

    Removes audio config from chapter. Audio file remains in library as archived.

    **Authentication:** Required (Owner only)

    **Query Parameters:**
    - `language`: Delete translation audio

    **Returns:**
    - 200: Audio deleted successfully
    - 403: Not book owner
    - 404: Book or chapter not found
    """
    try:
        user_id = current_user["uid"]

        # Check ownership
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only book owner can delete audio"
            )

        # Delete audio
        success = audio_svc.delete_chapter_audio(chapter_id, language)

        if success:
            logger.info(
                f"✅ User {user_id} deleted audio for chapter {chapter_id}, lang={language or 'default'}"
            )
            return {
                "success": True,
                "message": "Audio removed from chapter (archived in library)",
            }
        else:
            raise HTTPException(status_code=404, detail="Audio not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Google Cloud TTS Endpoints
# ==========================================


@router.get(
    "/voices",
    summary="Get available TTS voices",
    description="List available Google TTS voices for a language",
)
async def get_tts_voices(
    language: str = Query(default="vi", description="Language code (vi, en, zh, etc.)"),
    user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get list of available TTS voices for a language

    - **language**: 2-letter language code (vi, en, zh, ja, ko, etc.)

    Returns list of voices with name, gender, and sample rate.
    """
    try:
        voices = await google_tts_service.get_available_voices(language)

        return {
            "success": True,
            "language": language,
            "voice_count": len(voices),
            "voices": voices,
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch voices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/generate",
    summary="Generate audio from text using AI",
    description="Generate chapter audio using Google Cloud TTS (costs 2 points)",
)
async def generate_audio_from_text(
    book_id: str,
    chapter_id: str,
    text: str = Form(..., description="Text to convert to speech (max 8000 bytes)"),
    language: str = Form(default="vi", description="Language code (vi, en, zh, etc.)"),
    voice_name: Optional[str] = Form(
        default=None, description="Voice name (Despina, Gacrux, Enceladus, etc.)"
    ),
    speaking_rate: float = Form(
        default=1.0, description="Speed of speech (0.25 to 4.0) - compatibility only"
    ),
    pitch: float = Form(default=0.0, description="Pitch adjustment - compatibility only"),
    prompt: Optional[str] = Form(
        default=None, description="Optional voice style prompt (e.g., 'Say in a curious way')"
    ),
    use_pro_model: bool = Form(
        default=False, description="Use gemini-2.5-pro-preview-tts (higher quality, slower)"
    ),
    use_chapter_content: bool = Form(
        default=False, description="Use chapter HTML content instead of text"
    ),
    user: Dict = Depends(get_current_user),
    audio_svc: AudioService = Depends(get_audio_service),
    perm_mgr: BookPermissionManager = Depends(get_permission_manager),
) -> Dict[str, Any]:
    """
    Generate audio from text using Gemini TTS

    Costs **2 points** per generation.

    **Parameters:**
    - **text**: Text to convert (max 8000 bytes)
    - **language**: Language code (vi, en, zh, ja, ko, th, fr, de, es, it, pt, ru, ar, hi, id, ms, tl)
    - **voice_name**: Vietnamese (Despina, Gacrux, Leda, Sulafat, Enceladus, Orus, Alnilam) or English (Kore, Aoede, Charon, Puck, Fenrir)
    - **prompt**: Optional style (e.g., "Say in a curious way", "Đọc đoạn thơ truyền cảm")
    - **use_pro_model**: True for gemini-2.5-pro (higher quality), False for flash (faster)
    - **use_chapter_content**: If true, extract text from chapter HTML

    **Returns:**
    - Audio file URL (WAV format)
    - Audio metadata (duration, format, voice, model)
    - Remaining points balance
    """
    try:
        user_id = user["uid"]

        # 1. Check book and chapter ownership
        book = book_manager.get_book_detail(book_id, user_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        chapter = db.book_chapters.find_one({"_id": chapter_id})
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        # Only book owner can generate audio
        if book.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="Only book owner can generate audio"
            )

        # 2. Check user points (2 points required)
        AUDIO_GENERATION_COST = 2
        user_data = db.users.find_one({"uid": user_id})
        current_points = user_data.get("points", 0) if user_data else 0

        if current_points < AUDIO_GENERATION_COST:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Need {AUDIO_GENERATION_COST} points, you have {current_points}",
            )

        # 3. Generate audio using Google TTS
        logger.info(f"🎙️ Generating audio for chapter {chapter_id}, language={language}")

        if use_chapter_content:
            # Extract text from chapter content
            content = chapter.get("content") or ""
            if not content:
                raise HTTPException(
                    status_code=400, detail="Chapter has no content to convert"
                )

            audio_content, metadata = await google_tts_service.generate_audio_from_html(
                html_content=content,
                language=language,
                voice_name=voice_name,
                speaking_rate=speaking_rate,
                pitch=pitch,
                prompt=prompt,
                use_pro_model=use_pro_model,
            )
        else:
            # Use provided text
            if not text or len(text.strip()) == 0:
                raise HTTPException(status_code=400, detail="Text cannot be empty")

            audio_content, metadata = await google_tts_service.generate_audio(
                text=text,
                language=language,
                voice_name=voice_name,
                speaking_rate=speaking_rate,
                pitch=pitch,
                prompt=prompt,
                use_pro_model=use_pro_model,
            )

        # 4. Upload audio to R2 and save to library
        # Create in-memory file
        import io

        audio_file = io.BytesIO(audio_content)
        # WAV format from Gemini TTS
        audio_file.name = f"chapter_{chapter_id}_{language}_generated.wav"

        # Upload using audio service
        library_file = audio_svc.upload_audio_file(
            audio_file=audio_file,
            user_id=user_id,
            book_id=book_id,
            chapter_id=chapter_id,
            language=language,
            metadata={
                "generated": True,
                "source": "google_tts",
                **metadata,
            },
        )

        # 5. Save audio config to chapter
        audio_config = {
            "enabled": True,
            "audio_file_id": library_file["_id"],
            "audio_url": library_file["url"],
            "duration": metadata.get("duration", 0),
            "format": metadata.get("format", "wav"),
            "voice_settings": {
                "voice_name": voice_name or metadata.get("voice_name"),
                "language_code": metadata.get("language_code"),
                "model": metadata.get("model"),
                "prompt": prompt,
            },
            "generated": True,
            "source": "gemini_tts",
        }

        audio_svc.save_audio_to_chapter(chapter_id, audio_config, language)

        # 6. Deduct points
        subscription_manager.deduct_user_points(user_id, AUDIO_GENERATION_COST)

        # Get updated balance
        user_data = db.users.find_one({"uid": user_id})
        remaining_points = user_data.get("points", 0) if user_data else 0

        logger.info(
            f"✅ Audio generated for chapter {chapter_id}, cost={AUDIO_GENERATION_COST} points, remaining={remaining_points}"
        )

        return {
            "success": True,
            "message": f"Audio generated successfully (cost: {AUDIO_GENERATION_COST} points)",
            "audio": {
                "file_id": library_file["_id"],
                "url": library_file["url"],
                "duration": metadata.get("duration"),
                "format": "mp3",
                "voice_name": metadata.get("voice_name"),
                "language": language,
            },
            "metadata": metadata,
            "points": {
                "cost": AUDIO_GENERATION_COST,
                "remaining": remaining_points,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
