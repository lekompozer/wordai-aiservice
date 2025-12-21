"""
Slide Narration API Routes
2-step flow: Subtitles (2 points) → Audio (2 points)
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging
from bson import ObjectId
from typing import List

from src.models.slide_narration_models import (
    SubtitleGenerateRequest,
    SubtitleGenerateResponse,
    AudioGenerateRequest,
    AudioGenerateResponse,
    NarrationListResponse,
    NarrationVersion,
    SlideSubtitleData,
    AudioFile,
)
from src.services.slide_narration_service import get_slide_narration_service
from src.services.user_management_service import get_user_management_service
from src.models.user_management import UserInDB
from src.api.dependencies import get_current_user
from src.database import get_db

logger = logging.getLogger("chatbot")
router = APIRouter()

# Points cost for each step
POINTS_COST_SUBTITLE = 2
POINTS_COST_AUDIO = 2


@router.post(
    "/presentations/{presentation_id}/narration/generate-subtitles",
    response_model=SubtitleGenerateResponse,
    summary="Generate Subtitles for Presentation",
    description="""
    **STEP 1: Generate subtitles with timestamps**

    Uses Gemini 3 Pro to analyze slides and generate natural narration with accurate timing.

    **Cost:** 2 points (deducted before generation)

    **Features:**
    - Mode-aware narration (presentation: concise, academy: detailed)
    - Element reference tracking for animation sync
    - Automatic timestamp calculation
    - Version management (create new version each time)

    **Flow:**
    1. Check user has 2 points available
    2. Generate subtitles with Gemini 3 Pro
    3. Save to slide_narrations collection (status: 'subtitles_only')
    4. Deduct 2 points
    5. Return narration_id + subtitles

    Next step: Use narration_id to generate audio (Step 2)
    """,
)
async def generate_subtitles(
    presentation_id: str,
    request: SubtitleGenerateRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Generate subtitles for presentation slides"""
    try:
        logger.info(f"🎙️ Subtitle generation request: {presentation_id}")
        logger.info(
            f"   User: {current_user.email}, Mode: {request.mode}, Language: {request.language}"
        )

        # Validate presentation_id in request matches URL
        if request.presentation_id != presentation_id:
            raise HTTPException(400, "Presentation ID mismatch")

        # Get user service
        user_service = get_user_management_service()

        # Check points BEFORE generation
        user_points = await user_service.get_user_points(str(current_user.id))
        if user_points < POINTS_COST_SUBTITLE:
            logger.warning(
                f"❌ Insufficient points: {user_points} < {POINTS_COST_SUBTITLE}"
            )
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Need {POINTS_COST_SUBTITLE}, have {user_points}",
            )

        # Fetch presentation from database
        db = get_db()
        presentation = await db.presentations.find_one(
            {"_id": ObjectId(presentation_id)}
        )
        if not presentation:
            raise HTTPException(404, "Presentation not found")

        # Check ownership
        if str(presentation.get("user_id")) != str(current_user.id):
            raise HTTPException(403, "Not authorized to narrate this presentation")

        # Get slides data
        slides = presentation.get("slides", [])
        if not slides:
            raise HTTPException(400, "Presentation has no slides")

        # Get narration service
        narration_service = get_slide_narration_service()

        # Generate subtitles
        result = await narration_service.generate_subtitles(
            presentation_id=presentation_id,
            slides=slides,
            mode=request.mode,
            language=request.language,
            user_query=request.user_query,
            title=presentation.get("title", "Untitled"),
            topic=presentation.get("topic", ""),
            user_id=str(current_user.id),
        )

        # Calculate total duration
        total_duration = sum(slide["slide_duration"] for slide in result["slides"])

        # Save to database
        narration_doc = {
            "presentation_id": ObjectId(presentation_id),
            "user_id": ObjectId(current_user.id),
            "version": await _get_next_version(presentation_id),
            "status": "subtitles_only",
            "mode": request.mode,
            "language": request.language,
            "user_query": request.user_query,
            "slides": result["slides"],
            "audio_files": [],
            "total_duration": total_duration,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        insert_result = await db.slide_narrations.insert_one(narration_doc)
        narration_id = str(insert_result.inserted_id)

        # Deduct points AFTER successful generation
        await user_service.deduct_points(
            user_id=str(current_user.id),
            points=POINTS_COST_SUBTITLE,
            reason=f"slide_narration_subtitles:{narration_id}",
        )

        logger.info(
            f"✅ Subtitles generated: {narration_id}, {len(result['slides'])} slides, {total_duration:.1f}s"
        )

        return SubtitleGenerateResponse(
            success=True,
            narration_id=narration_id,
            version=narration_doc["version"],
            slides=result["slides"],
            total_duration=total_duration,
            processing_time_ms=result["processing_time_ms"],
            points_deducted=POINTS_COST_SUBTITLE,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Subtitle generation failed: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to generate subtitles: {str(e)}")


@router.post(
    "/presentations/{presentation_id}/narration/{narration_id}/generate-audio",
    response_model=AudioGenerateResponse,
    summary="Generate Audio from Subtitles",
    description="""
    **STEP 2: Generate audio from existing subtitles**

    Uses GoogleTTSService (same as Listening Test) to convert subtitles to MP3 audio.

    **Cost:** 2 points (deducted before generation)

    **Features:**
    - Multi-speaker support (future)
    - Premium voice models
    - Upload to library_audio collection
    - R2 CDN hosting

    **Flow:**
    1. Check user has 2 points available
    2. Fetch narration record with subtitles
    3. Generate audio for each slide
    4. Upload to R2 via library_audio
    5. Update narration status to 'completed'
    6. Deduct 2 points
    7. Return audio_files with CDN URLs

    Previous step: Generate subtitles first (Step 1)
    """,
)
async def generate_audio(
    presentation_id: str,
    narration_id: str,
    request: AudioGenerateRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """Generate audio from existing subtitles"""
    try:
        logger.info(f"🔊 Audio generation request: {narration_id}")
        logger.info(
            f"   User: {current_user.email}, Provider: {request.voice_config.provider}"
        )

        # Validate narration_id in request matches URL
        if request.narration_id != narration_id:
            raise HTTPException(400, "Narration ID mismatch")

        # Get user service
        user_service = get_user_management_service()

        # Check points BEFORE generation
        user_points = await user_service.get_user_points(str(current_user.id))
        if user_points < POINTS_COST_AUDIO:
            logger.warning(
                f"❌ Insufficient points: {user_points} < {POINTS_COST_AUDIO}"
            )
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient points. Need {POINTS_COST_AUDIO}, have {user_points}",
            )

        # Fetch narration from database
        db = get_db()
        narration = await db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != str(current_user.id):
            raise HTTPException(403, "Not authorized to access this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        # Check status
        if narration.get("status") == "completed":
            raise HTTPException(400, "Audio already generated for this narration")

        # Get slides with subtitles
        slides_with_subtitles = narration.get("slides", [])
        if not slides_with_subtitles:
            raise HTTPException(400, "No subtitles found in narration")

        # Get narration service
        narration_service = get_slide_narration_service()

        # Generate audio
        result = await narration_service.generate_audio(
            narration_id=narration_id,
            slides_with_subtitles=slides_with_subtitles,
            voice_config=request.voice_config.dict(),
            user_id=str(current_user.id),
        )

        # Calculate total duration
        total_duration = sum(audio["duration"] for audio in result["audio_files"])

        # Update narration record
        await db.slide_narrations.update_one(
            {"_id": ObjectId(narration_id)},
            {
                "$set": {
                    "status": "completed",
                    "audio_files": result["audio_files"],
                    "voice_config": request.voice_config.dict(),
                    "updated_at": datetime.now(),
                }
            },
        )

        # Deduct points AFTER successful generation
        await user_service.deduct_points(
            user_id=str(current_user.id),
            points=POINTS_COST_AUDIO,
            reason=f"slide_narration_audio:{narration_id}",
        )

        logger.info(
            f"✅ Audio generated: {len(result['audio_files'])} files, {total_duration:.1f}s"
        )

        return AudioGenerateResponse(
            success=True,
            narration_id=narration_id,
            audio_files=result["audio_files"],
            total_duration=total_duration,
            processing_time_ms=result["processing_time_ms"],
            points_deducted=POINTS_COST_AUDIO,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Audio generation failed: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to generate audio: {str(e)}")


@router.get(
    "/presentations/{presentation_id}/narrations",
    response_model=NarrationListResponse,
    summary="List Narration Versions",
    description="""
    **Get all narration versions for a presentation**

    Returns list of all narration versions with metadata.
    Useful for showing version history and allowing user to regenerate.

    **No points cost** (read-only operation)
    """,
)
async def list_narrations(
    presentation_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """List all narration versions for presentation"""
    try:
        db = get_db()

        # Check presentation exists and user owns it
        presentation = await db.presentations.find_one(
            {"_id": ObjectId(presentation_id)}
        )
        if not presentation:
            raise HTTPException(404, "Presentation not found")

        if str(presentation.get("user_id")) != str(current_user.id):
            raise HTTPException(403, "Not authorized to view this presentation")

        # Fetch all narrations
        cursor = db.slide_narrations.find(
            {
                "presentation_id": ObjectId(presentation_id),
                "user_id": ObjectId(current_user.id),
            }
        ).sort("created_at", -1)

        narrations = []
        async for doc in cursor:
            narrations.append(
                NarrationVersion(
                    narration_id=str(doc["_id"]),
                    version=doc.get("version", 1),
                    status=doc.get("status", "unknown"),
                    mode=doc.get("mode", "presentation"),
                    language=doc.get("language", "vi"),
                    total_duration=doc.get("total_duration", 0.0),
                    created_at=doc.get("created_at", datetime.now()),
                    audio_ready=(doc.get("status") == "completed"),
                )
            )

        return NarrationListResponse(
            success=True,
            narrations=narrations,
            total_count=len(narrations),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list narrations: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list narrations: {str(e)}")


# Helper functions


async def _get_next_version(presentation_id: str) -> int:
    """Get next version number for narration"""
    db = get_db()
    latest = await db.slide_narrations.find_one(
        {"presentation_id": ObjectId(presentation_id)}, sort=[("version", -1)]
    )
    return (latest.get("version", 0) + 1) if latest else 1
