"""
Slide Narration API Routes
2-step flow: Subtitles (2 points) → Audio (2 points)
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging
from bson import ObjectId
from typing import List, Dict, Any, Dict, Any

from src.models.slide_narration_models import (
    SubtitleGenerateRequest,
    SubtitleGenerateResponse,
    AudioGenerateRequest,
    AudioGenerateResponse,
    NarrationListResponse,
    NarrationVersion,
    SlideSubtitleData,
    AudioFile,
    NarrationDetailResponse,
    UpdateSubtitlesRequest,
    UpdateSubtitlesResponse,
    DeleteNarrationResponse,
    VoiceConfig,
    LibraryAudioItem,
    AssignAudioRequest,
    AssignAudioResponse,
    LibraryAudioListRequest,
    LibraryAudioListResponse,
    # Multi-language models
    GenerateSubtitlesRequestV2,
    GenerateSubtitlesResponseV2,
    GenerateAudioRequestV2,
    GenerateAudioResponseV2,
    UploadAudioRequest,
    UploadAudioResponse,
    ListSubtitlesResponse,
    PresentationSubtitle,
    PresentationAudio,
    UpdateSharingConfigRequest,
    UpdateSharingConfigResponse,
    PresentationSharingConfig,
    PublicPresentationResponse,
)
from src.services.slide_narration_service import get_slide_narration_service
from src.services.points_service import get_points_service
from src.middleware.firebase_auth import get_current_user
from src.services.document_manager import DocumentManager
from src.services.online_test_utils import get_mongodb_service

logger = logging.getLogger("chatbot")
router = APIRouter(prefix="/api")

logger.info("=" * 80)
logger.info("🎤 SLIDE NARRATION ROUTER INITIALIZED")
logger.info(f"   Prefix: /api")
logger.info(f"   Routes will be: /api/presentations/{{id}}/narration/*")
logger.info("=" * 80)


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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate subtitles for presentation slides"""
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "unknown")

        logger.info("=" * 80)
        logger.info(f"🎙️ SUBTITLE GENERATION REQUEST RECEIVED")
        logger.info(
            f"📍 Endpoint: POST /api/presentations/{presentation_id}/narration/generate-subtitles"
        )
        logger.info(f"👤 User: {user_email} ({user_id})")
        logger.info(
            f"🎛️ Mode: {request.mode}, Language: {request.language}, Scope: {request.scope}"
        )
        if request.scope == "current":
            logger.info(f"🎯 Current slide index: {request.current_slide_index}")
        logger.info(
            f"💬 User query: {request.user_query[:100] if request.user_query else '(none)'}"
        )
        logger.info("=" * 80)

        # Validate presentation_id in request matches URL
        if request.presentation_id != presentation_id:
            logger.error(
                f"❌ Presentation ID mismatch: URL={presentation_id}, Body={request.presentation_id}"
            )
            raise HTTPException(400, "Presentation ID mismatch")

        # Get points service
        points_service = get_points_service()

        # Check points BEFORE generation
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=POINTS_COST_SUBTITLE,
            service="slide_narration_subtitles",
        )

        if not check["has_points"]:
            logger.warning(
                f"❌ Insufficient points: {check['points_available']} < {POINTS_COST_SUBTITLE}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ điểm. Cần: {POINTS_COST_SUBTITLE}, Còn: {check['points_available']}",
                    "points_needed": POINTS_COST_SUBTITLE,
                    "points_available": check["points_available"],
                },
            )

        # Fetch document from documents collection (where slides are stored)
        doc_manager = DocumentManager(get_mongodb_service().db)
        document = get_mongodb_service().db.documents.find_one(
            {"document_id": presentation_id, "document_type": "slide"}
        )

        if not document:
            raise HTTPException(404, "Slide document not found")

        # Check ownership
        if document.get("user_id") != user_id:
            raise HTTPException(403, "Not authorized to narrate this presentation")

        # Parse HTML content to extract slides
        content_html = document.get("content_html", "")
        if not content_html:
            raise HTTPException(400, "Document has no content")

        # Extract slides from HTML (split by slide divs)
        import re
        from html.parser import HTMLParser

        # Split slides by <div class="slide">
        slide_pattern = r'<div[^>]*class="slide"[^>]*data-slide-index="(\d+)"[^>]*>(.*?)</div>(?=\s*(?:<div[^>]*class="slide"|$))'
        slide_matches = re.findall(
            slide_pattern, content_html, re.DOTALL | re.IGNORECASE
        )

        if not slide_matches:
            # Fallback: split by any div with data-slide-index
            slide_pattern_simple = r'<div[^>]*data-slide-index="(\d+)"[^>]*>(.*?)</div>'
            slide_matches = re.findall(
                slide_pattern_simple, content_html, re.DOTALL | re.IGNORECASE
            )

        if not slide_matches:
            raise HTTPException(
                400, f"No slides found in document. Content length: {len(content_html)}"
            )

        # Build slides array with html content
        slides = []
        for idx, (slide_index, slide_html) in enumerate(slide_matches):
            slides.append(
                {
                    "index": int(slide_index),
                    "html": f'<div class="slide" data-slide-index="{slide_index}">{slide_html}</div>',
                    "elements": [],  # Will be populated by service if needed
                    "background": (
                        document.get("slide_backgrounds", [])[int(slide_index)]
                        if int(slide_index) < len(document.get("slide_backgrounds", []))
                        else None
                    ),
                }
            )

        logger.info(
            f"📄 Extracted {len(slides)} slides from document {presentation_id}"
        )

        # Filter slides based on scope
        if request.scope == "current":
            if request.current_slide_index is None:
                raise HTTPException(
                    400, "current_slide_index required when scope='current'"
                )

            if request.current_slide_index < 0 or request.current_slide_index >= len(
                slides
            ):
                raise HTTPException(
                    400,
                    f"Invalid slide index: {request.current_slide_index} (total: {len(slides)})",
                )

            # Generate for single slide only
            slides = [slides[request.current_slide_index]]
            logger.info(
                f"🎯 Generating subtitles for slide {request.current_slide_index} only"
            )
        else:
            logger.info(f"📊 Generating subtitles for all {len(slides)} slides")

        # Get narration service
        narration_service = get_slide_narration_service()

        # Generate subtitles
        result = await narration_service.generate_subtitles(
            presentation_id=presentation_id,
            slides=slides,
            mode=request.mode,
            language=request.language,
            user_query=request.user_query,
            title=document.get("title", "Untitled"),
            topic=document.get("metadata", {}).get("topic", ""),
            user_id=user_id,
        )

        # Calculate total duration
        total_duration = sum(slide["slide_duration"] for slide in result["slides"])

        # Save to database
        narration_doc = {
            "presentation_id": presentation_id,  # String document_id, NOT ObjectId
            "user_id": user_id,  # String Firebase UID, NOT ObjectId
            "version": _get_next_version(presentation_id),
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

        insert_result = get_mongodb_service().db.slide_narrations.insert_one(
            narration_doc
        )
        narration_id = str(insert_result.inserted_id)

        # Deduct points AFTER successful generation
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_SUBTITLE,
            service="slide_narration",
            resource_id=narration_id,
            description=f"Subtitle generation for presentation {presentation_id}",
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate audio from existing subtitles"""
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "unknown")

        logger.info(f"🔊 Audio generation request: {narration_id}")
        logger.info(f"   User: {user_email}, Provider: {request.voice_config.provider}")

        # Validate narration_id in request matches URL
        if request.narration_id != narration_id:
            raise HTTPException(400, "Narration ID mismatch")

        # Get points service
        points_service = get_points_service()

        # Check points BEFORE generation
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=POINTS_COST_AUDIO,
            service="slide_narration_audio",
        )

        if not check["has_points"]:
            logger.warning(
                f"❌ Insufficient points: {check['points_available']} < {POINTS_COST_AUDIO}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ điểm. Cần: {POINTS_COST_AUDIO}, Còn: {check['points_available']}",
                    "points_needed": POINTS_COST_AUDIO,
                    "points_available": check["points_available"],
                },
            )

        # Fetch narration from database
        narration = get_mongodb_service().db.slide_narrations.find_one(
            {"_id": ObjectId(narration_id)}
        )
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to modify this narration")

        # Check has subtitles
        if narration.get("status") == "completed":
            raise HTTPException(400, "Audio already generated for this narration")

        if not narration.get("slides"):
            raise HTTPException(400, "Narration has no subtitles")

        # Get narration service
        narration_service = get_slide_narration_service()

        # Generate audio
        result = await narration_service.generate_audio(
            narration_id=narration_id,
            slides_with_subtitles=narration["slides"],
            voice_config=request.voice_config.dict(),
            user_id=user_id,
        )

        # Update database with audio files
        get_mongodb_service().db.slide_narrations.update_one(
            {"_id": ObjectId(narration_id)},
            {
                "$set": {
                    "audio_files": result["audio_files"],
                    "voice_config": request.voice_config.dict(),
                    "status": "completed",
                    "updated_at": datetime.now(),
                }
            },
        )

        # Deduct points AFTER successful generation
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_AUDIO,
            service="slide_narration_audio",
            resource_id=narration_id,
            description=f"Audio generation for narration {narration_id}",
        )

        logger.info(
            f"✅ Audio generated: {narration_id}, {len(result['audio_files'])} files, {result['total_duration']:.1f}s"
        )

        return AudioGenerateResponse(
            success=True,
            narration_id=narration_id,
            audio_files=result["audio_files"],
            total_duration=result["total_duration"],
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all narration versions for presentation"""
    try:
        user_id = current_user["uid"]

        # Check document exists (using document_id string, not ObjectId)
        document = get_mongodb_service().db.documents.find_one(
            {"document_id": presentation_id, "document_type": "slide"}
        )
        if not document:
            raise HTTPException(404, "Presentation not found")

        if document.get("user_id") != user_id:
            raise HTTPException(403, "Not authorized to view this presentation")

        # Fetch all narrations (presentation_id and user_id are strings)
        cursor = (
            get_mongodb_service()
            .db.slide_narrations.find(
                {
                    "presentation_id": presentation_id,
                    "user_id": user_id,
                }
            )
            .sort("created_at", -1)
        )

        narrations = []
        for doc in cursor:  # PyMongo sync cursor - use regular for, not async for
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


def _get_next_version(presentation_id: str) -> int:
    """Get next version number for narration"""
    latest = get_mongodb_service().db.slide_narrations.find_one(
        {"presentation_id": presentation_id}, sort=[("version", -1)]
    )
    return (latest.get("version", 0) + 1) if latest else 1


@router.get(
    "/presentations/{presentation_id}/narration/{narration_id}",
    response_model=NarrationDetailResponse,
    summary="Get Narration by ID",
    description="""
    **Get detailed narration data by ID**

    Returns complete narration record including:
    - All subtitles with timestamps
    - Audio files (if generated)
    - Voice configuration (if audio generated)
    - Version and status information

    **No points cost** (read-only operation)

    Use this to:
    - Preview subtitles before audio generation
    - Review/edit subtitles
    - Check audio generation status
    """,
)
async def delete_narration(
    presentation_id: str,
    narration_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete narration version"""
    try:
        user_id = current_user["uid"]

        # Fetch narration
        narration = get_mongodb_service().db.slide_narrations.find_one(
            {"_id": ObjectId(narration_id)}
        )
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to access this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        return NarrationDetailResponse(
            success=True,
            narration_id=str(narration["_id"]),
            presentation_id=str(narration.get("presentation_id")),
            version=narration.get("version", 1),
            status=narration.get("status", "unknown"),
            mode=narration.get("mode", "presentation"),
            language=narration.get("language", "vi"),
            user_query=narration.get("user_query", ""),
            slides=narration.get("slides", []),
            audio_files=narration.get("audio_files", []),
            voice_config=narration.get("voice_config"),
            total_duration=narration.get("total_duration", 0.0),
            created_at=narration.get("created_at", datetime.now()),
            updated_at=narration.get("updated_at", datetime.now()),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get narration: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get narration: {str(e)}")


@router.put(
    "/presentations/{presentation_id}/narration/{narration_id}",
    response_model=UpdateSubtitlesResponse,
    summary="Update Subtitles",
    description="""
    **Update/edit subtitles before audio generation**

    Allows manual editing of:
    - Subtitle text
    - Timestamps (start_time, end_time, duration)
    - Speaker assignments
    - Element references
    - Slide duration and auto-advance settings

    **No points cost** (editing only)

    **Requirements:**
    - Narration must be in 'subtitles_only' status
    - Cannot edit after audio is generated
    - Timestamps must not overlap

    Use this to:
    - Fix AI-generated subtitle errors
    - Adjust timing for better sync
    - Customize narration before audio generation
    """,
)
async def update_subtitles(
    presentation_id: str,
    narration_id: str,
    request: UpdateSubtitlesRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update subtitles before audio generation"""
    try:
        user_id = current_user["uid"]
        logger.info(f"📝 Updating subtitles for narration {narration_id}")

        # Fetch narration
        narration = get_mongodb_service().db.slide_narrations.find_one(
            {"_id": ObjectId(narration_id)}
        )
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to edit this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        # Check status - can only edit before audio generation
        if narration.get("status") == "completed":
            raise HTTPException(
                400,
                "Cannot edit subtitles after audio has been generated. Create a new version instead.",
            )

        # Validate timestamps don't overlap
        for slide in request.slides:
            subtitles = slide.subtitles
            for i in range(len(subtitles) - 1):
                current = subtitles[i]
                next_sub = subtitles[i + 1]
                if current.end_time > next_sub.start_time:
                    raise HTTPException(
                        400,
                        f"Overlapping timestamps in slide {slide.slide_index}: "
                        f"subtitle {current.subtitle_index} ends at {current.end_time}s, "
                        f"but subtitle {next_sub.subtitle_index} starts at {next_sub.start_time}s",
                    )

        # Calculate new total duration
        total_duration = sum(slide.slide_duration for slide in request.slides)

        # Update in database
        updated_at = datetime.now()
        get_mongodb_service().db.slide_narrations.update_one(
            {"_id": ObjectId(narration_id)},
            {
                "$set": {
                    "slides": [slide.dict() for slide in request.slides],
                    "total_duration": total_duration,
                    "updated_at": updated_at,
                }
            },
        )

        logger.info(
            f"✅ Updated subtitles for {len(request.slides)} slides, total: {total_duration:.1f}s"
        )

        return UpdateSubtitlesResponse(
            success=True,
            narration_id=narration_id,
            slides=request.slides,
            total_duration=total_duration,
            updated_at=updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update subtitles: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to update subtitles: {str(e)}")


@router.delete(
    "/presentations/{presentation_id}/narration/{narration_id}",
    response_model=DeleteNarrationResponse,
    summary="Delete Narration",
    description="""
    **Delete a narration version**

    Permanently deletes:
    - Narration record with all subtitles
    - Associated audio files from R2 (if generated)
    - Library audio records

    **No points cost** (deletion)

    **Warning:** This action cannot be undone!

    Use this to:
    - Remove unwanted narration versions
    - Clean up test data
    - Free up storage space
    """,
)
async def delete_narration(
    presentation_id: str,
    narration_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete narration and associated audio files"""
    try:
        user_id = current_user["uid"]
        logger.info(f"🗑️ Deleting narration {narration_id}")

        # Fetch narration
        narration = get_mongodb_service().db.slide_narrations.find_one(
            {"_id": ObjectId(narration_id)}
        )
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to delete this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        # Delete associated audio files from library_audio
        audio_files = narration.get("audio_files", [])
        if audio_files:
            from src.services.library_audio_service import LibraryAudioService

            audio_service = LibraryAudioService()
            for audio in audio_files:
                library_audio_id = audio.get("library_audio_id")
                if library_audio_id:
                    try:
                        # Delete from R2 and database
                        await audio_service.delete_audio(library_audio_id)
                        logger.info(f"   Deleted audio: {library_audio_id}")
                    except Exception as e:
                        logger.warning(
                            f"   Failed to delete audio {library_audio_id}: {e}"
                        )

        # Delete narration record
        get_mongodb_service().db.slide_narrations.delete_one(
            {"_id": ObjectId(narration_id)}
        )

        logger.info(
            f"✅ Deleted narration {narration_id} with {len(audio_files)} audio files"
        )

        return DeleteNarrationResponse(
            success=True,
            narration_id=narration_id,
            message=f"Narration version {narration.get('version', 1)} deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete narration: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to delete narration: {str(e)}")


# ============================================================
# LIBRARY AUDIO INTEGRATION
# ============================================================


@router.get(
    "/library-audio",
    response_model=LibraryAudioListResponse,
    summary="List Library Audio Files",
    description="""
    **Browse/search library audio files**

    Returns list of audio files from library_audio collection.

    **Filters:**
    - source_type: Filter by source (slide_narration, listening_test, upload)
    - search_query: Search in file names
    - limit: Max results per page (1-100)
    - offset: Pagination offset

    **No points cost** (read-only)

    Use this to:
    - Browse available audio files
    - Search for specific audio
    - Select audio for slide assignment
    - Preview audio before assigning
    """,
)
async def list_library_audio(
    request: LibraryAudioListRequest = Depends(),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Browse and search library audio files"""
    try:
        user_id = current_user["uid"]

        # Build query filter
        query = {"user_id": user_id}

        if request.source_type:
            query["source_type"] = request.source_type

        if request.search_query:
            query["file_name"] = {"$regex": request.search_query, "$options": "i"}

        # Get total count
        total_count = get_mongodb_service().db.library_audio.count_documents(query)

        # Fetch audio files with pagination
        cursor = (
            get_mongodb_service()
            .db.library_audio.find(query)
            .sort("created_at", -1)
            .skip(request.offset)
            .limit(request.limit)
        )

        audio_files = []
        for doc in cursor:  # PyMongo sync cursor - use regular for, not async for
            audio_files.append(
                LibraryAudioItem(
                    audio_id=str(doc["_id"]),
                    file_name=doc.get("file_name", ""),
                    r2_url=doc.get("r2_url", ""),
                    duration=doc.get("duration", 0),
                    file_size=doc.get("file_size", 0),
                    format=doc.get("format", "mp3"),
                    source_type=doc.get("source_type", "unknown"),
                    created_at=(
                        doc.get("created_at").isoformat()
                        if doc.get("created_at")
                        else ""
                    ),
                    metadata=doc.get("metadata", {}),
                )
            )

        return LibraryAudioListResponse(
            success=True,
            audio_files=audio_files,
            total_count=total_count,
            has_more=(request.offset + request.limit) < total_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list library audio: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list library audio: {str(e)}")


@router.post(
    "/presentations/{presentation_id}/narration/{narration_id}/assign-audio",
    response_model=AssignAudioResponse,
    summary="Assign Library Audio to Slides",
    description="""
    **Assign existing library audio to slides**

    Allows selecting audio files from library_audio collection and assigning them to slides.

    **Features:**
    - Assign different audio to each slide
    - Replace existing audio assignments
    - Use pre-recorded/uploaded audio instead of TTS
    - No points cost (just assignment)

    **Requirements:**
    - Narration must exist
    - Audio files must belong to current user
    - Can assign to narrations in any status

    **Use Cases:**
    - Use custom recorded narration
    - Reuse audio from other presentations
    - Mix TTS with custom audio
    - Replace TTS audio with professional recording
    """,
)
async def assign_library_audio(
    presentation_id: str,
    narration_id: str,
    request: AssignAudioRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Assign library audio files to slides"""
    try:
        user_id = current_user["uid"]
        logger.info(f"🎵 Assigning library audio to narration {narration_id}")

        # Fetch narration
        narration = get_mongodb_service().db.slide_narrations.find_one(
            {"_id": ObjectId(narration_id)}
        )
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to edit this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        # Build audio_files array
        audio_files = []

        for assignment in request.audio_assignments:
            slide_index = assignment.get("slide_index")
            library_audio_id = assignment.get("library_audio_id")

            # Fetch audio from library
            audio_doc = get_mongodb_service().db.library_audio.find_one(
                {"_id": ObjectId(library_audio_id)}
            )

            if not audio_doc:
                raise HTTPException(404, f"Audio not found: {library_audio_id}")

            # Verify ownership
            if str(audio_doc.get("user_id")) != user_id:
                raise HTTPException(
                    403, f"Not authorized to use audio: {library_audio_id}"
                )

            # Add to audio_files array
            audio_files.append(
                {
                    "slide_index": slide_index,
                    "audio_url": audio_doc.get("r2_url", ""),
                    "library_audio_id": str(audio_doc["_id"]),
                    "file_size": audio_doc.get("file_size", 0),
                    "format": audio_doc.get("format", "mp3"),
                    "duration": audio_doc.get("metadata", {}).get(
                        "duration_seconds", 0
                    ),
                    "speaker_count": 1,
                }
            )

        # Update narration with assigned audio
        get_mongodb_service().db.slide_narrations.update_one(
            {"_id": ObjectId(narration_id)},
            {
                "$set": {
                    "audio_files": audio_files,
                    "status": "completed",  # Mark as completed
                    "updated_at": datetime.now(),
                }
            },
        )

        logger.info(f"✅ Assigned {len(audio_files)} audio files to narration")

        return AssignAudioResponse(
            success=True,
            narration_id=narration_id,
            audio_files=audio_files,
            message=f"Successfully assigned {len(audio_files)} audio files",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to assign audio: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to assign audio: {str(e)}")


@router.delete(
    "/presentations/{presentation_id}/narration/{narration_id}/audio/{slide_index}",
    summary="Remove Audio from Slide",
    description="""
    **Remove audio assignment from specific slide**

    Removes audio file assignment from a single slide.
    Does NOT delete the audio from library_audio (just removes assignment).

    **No points cost**

    Use this to:
    - Remove unwanted audio from slide
    - Clear audio before reassigning
    - Revert to subtitle-only mode for specific slide
    """,
)
async def remove_slide_audio(
    presentation_id: str,
    narration_id: str,
    slide_index: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Remove audio assignment from specific slide"""
    try:
        user_id = current_user["uid"]
        logger.info(
            f"🗑️ Removing audio from slide {slide_index} in narration {narration_id}"
        )

        # Fetch narration
        narration = get_mongodb_service().db.slide_narrations.find_one(
            {"_id": ObjectId(narration_id)}
        )
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to edit this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        # Remove audio for specified slide
        audio_files = narration.get("audio_files", [])
        updated_audio_files = [
            audio for audio in audio_files if audio.get("slide_index") != slide_index
        ]

        # Determine new status
        new_status = "completed" if updated_audio_files else "subtitles_only"

        # Update narration
        get_mongodb_service().db.slide_narrations.update_one(
            {"_id": ObjectId(narration_id)},
            {
                "$set": {
                    "audio_files": updated_audio_files,
                    "status": new_status,
                    "updated_at": datetime.now(),
                }
            },
        )

        logger.info(f"✅ Removed audio from slide {slide_index}")

        return {
            "success": True,
            "narration_id": narration_id,
            "slide_index": slide_index,
            "message": f"Audio removed from slide {slide_index}",
            "remaining_audio_count": len(updated_audio_files),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to remove audio: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to remove audio: {str(e)}")


# ============================================================
# MULTI-LANGUAGE NARRATION SYSTEM (V2)
# ============================================================


@router.post("/presentations/{presentation_id}/subtitles/v2")
async def generate_subtitles_v2(
    presentation_id: str,
    request: GenerateSubtitlesRequestV2,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate subtitles for specific language (multi-language system)
    Deducts 2 points from user
    """
    try:
        user_id = current_user["uid"]
        logger.info(
            f"Generating subtitles V2: presentation={presentation_id}, language={request.language}"
        )

        # Deduct points
        points_service = get_points_service()
        await points_service.deduct_points(
            user_id=user_id,
            amount=2,
            service="slide_narration",
            resource_id=presentation_id,
            description=f"Generate subtitles ({request.language})",
        )

        # Generate subtitles
        narration_service = get_slide_narration_service()
        subtitle_doc = await narration_service.generate_subtitles_v2(
            presentation_id=presentation_id,
            language=request.language,
            mode=request.mode,
            user_id=user_id,
            user_query=request.user_query or "",
        )

        return GenerateSubtitlesResponseV2(
            success=True,
            subtitle=PresentationSubtitle(**subtitle_doc),
            points_deducted=2,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate subtitles V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to generate subtitles: {str(e)}")


@router.get("/presentations/{presentation_id}/subtitles/v2")
async def list_subtitles_v2(
    presentation_id: str,
    language: str = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List all subtitle versions for presentation
    Optional filter by language
    """
    try:
        user_id = current_user["uid"]
        logger.info(
            f"Listing subtitles V2: presentation={presentation_id}, language={language}"
        )

        # Build query
        query = {"presentation_id": presentation_id, "user_id": user_id}
        if language:
            query["language"] = language

        # Get subtitles
        cursor = (
            get_mongodb_service()
            .db.presentation_subtitles.find(query)
            .sort([("language", 1), ("version", -1)])
        )

        subtitles = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            subtitles.append(PresentationSubtitle(**doc))

        return ListSubtitlesResponse(
            success=True, subtitles=subtitles, total_count=len(subtitles)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list subtitles V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list subtitles: {str(e)}")


@router.get("/presentations/{presentation_id}/subtitles/v2/{subtitle_id}")
async def get_subtitle_v2(
    presentation_id: str,
    subtitle_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get specific subtitle document"""
    try:
        user_id = current_user["uid"]

        # Get subtitle
        subtitle = get_mongodb_service().db.presentation_subtitles.find_one(
            {"_id": ObjectId(subtitle_id), "user_id": user_id}
        )

        if not subtitle:
            raise HTTPException(404, "Subtitle not found")

        subtitle["_id"] = str(subtitle["_id"])
        return {"success": True, "subtitle": PresentationSubtitle(**subtitle)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get subtitle V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get subtitle: {str(e)}")


@router.delete("/presentations/{presentation_id}/subtitles/v2/{subtitle_id}")
async def delete_subtitle_v2(
    presentation_id: str,
    subtitle_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete subtitle document and associated audio files
    """
    try:
        user_id = current_user["uid"]
        logger.info(f"Deleting subtitle V2: {subtitle_id}")

        # Get subtitle to verify ownership
        subtitle = get_mongodb_service().db.presentation_subtitles.find_one(
            {"_id": ObjectId(subtitle_id), "user_id": user_id}
        )

        if not subtitle:
            raise HTTPException(404, "Subtitle not found")

        # Delete associated audio files
        get_mongodb_service().db.presentation_audio.delete_many(
            {"subtitle_id": subtitle_id}
        )

        # Delete subtitle
        get_mongodb_service().db.presentation_subtitles.delete_one(
            {"_id": ObjectId(subtitle_id)}
        )

        logger.info(f"✅ Deleted subtitle {subtitle_id}")

        return {"success": True, "message": "Subtitle and audio deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete subtitle V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to delete subtitle: {str(e)}")


@router.post("/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio")
async def generate_audio_v2(
    presentation_id: str,
    subtitle_id: str,
    request: GenerateAudioRequestV2,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate audio for subtitle document
    Deducts 2 points from user
    """
    try:
        user_id = current_user["uid"]
        logger.info(f"Generating audio V2: subtitle={subtitle_id}")

        # Deduct points
        points_service = get_points_service()
        await points_service.deduct_points(
            user_id=user_id,
            amount=2,
            service="slide_narration",
            resource_id=subtitle_id,
            description="Generate audio",
        )

        # Generate audio
        narration_service = get_slide_narration_service()
        audio_docs = await narration_service.generate_audio_v2(
            subtitle_id=subtitle_id,
            voice_config=request.voice_config.dict(),
            user_id=user_id,
        )

        # Convert to response models
        audio_files = [PresentationAudio(**doc) for doc in audio_docs]

        return GenerateAudioResponseV2(
            success=True, audio_files=audio_files, points_deducted=2
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate audio V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to generate audio: {str(e)}")


@router.post("/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio/upload")
async def upload_audio_v2(
    presentation_id: str,
    subtitle_id: str,
    request: UploadAudioRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Upload user-provided audio file for slide
    No points deduction
    """
    try:
        user_id = current_user["uid"]
        logger.info(
            f"Uploading audio V2: subtitle={subtitle_id}, slide={request.slide_index}"
        )

        # Decode base64 audio file
        import base64

        audio_data = base64.b64decode(request.audio_file)

        # Upload audio
        narration_service = get_slide_narration_service()
        audio_doc = await narration_service.upload_audio(
            subtitle_id=subtitle_id,
            slide_index=request.slide_index,
            audio_file_data=audio_data,
            audio_metadata=request.audio_metadata.dict(),
            user_id=user_id,
        )

        return UploadAudioResponse(success=True, audio=PresentationAudio(**audio_doc))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to upload audio V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to upload audio: {str(e)}")


@router.get("/presentations/{presentation_id}/audio/v2")
async def list_audio_v2(
    presentation_id: str,
    language: str = None,
    version: int = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List audio files for presentation
    Optional filter by language and version
    """
    try:
        user_id = current_user["uid"]

        # Build query
        query = {"presentation_id": presentation_id, "user_id": user_id}
        if language:
            query["language"] = language
        if version:
            query["version"] = version

        # Get audio files
        cursor = (
            get_mongodb_service()
            .db.presentation_audio.find(query)
            .sort([("language", 1), ("version", -1), ("slide_index", 1)])
        )

        audio_files = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            audio_files.append(PresentationAudio(**doc))

        return {
            "success": True,
            "audio_files": audio_files,
            "total_count": len(audio_files),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list audio V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list audio: {str(e)}")


@router.delete("/presentations/{presentation_id}/audio/v2/{audio_id}")
async def delete_audio_v2(
    presentation_id: str,
    audio_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete audio file"""
    try:
        user_id = current_user["uid"]

        # Get audio to verify ownership
        audio = get_mongodb_service().db.presentation_audio.find_one(
            {"_id": ObjectId(audio_id), "user_id": user_id}
        )

        if not audio:
            raise HTTPException(404, "Audio not found")

        # Delete audio document
        get_mongodb_service().db.presentation_audio.delete_one(
            {"_id": ObjectId(audio_id)}
        )

        logger.info(f"✅ Deleted audio {audio_id}")

        return {"success": True, "message": "Audio deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete audio V2: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to delete audio: {str(e)}")


# ============================================================
# SHARING CONFIGURATION
# ============================================================


@router.get("/presentations/{presentation_id}/sharing")
async def get_sharing_config(
    presentation_id: str, current_user: dict = Depends(get_current_user)
):
    """Get sharing configuration for presentation"""
    try:
        user_id = current_user["uid"]
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()
        config = await sharing_service.get_or_create_config(
            presentation_id=presentation_id, user_id=user_id
        )

        return {"success": True, "config": PresentationSharingConfig(**config)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get sharing config: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get sharing config: {str(e)}")


@router.put("/presentations/{presentation_id}/sharing")
async def update_sharing_config(
    presentation_id: str,
    request: UpdateSharingConfigRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update sharing configuration"""
    try:
        user_id = current_user["uid"]
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()

        # Prepare sharing_settings dict
        sharing_settings = None
        if request.sharing_settings:
            sharing_settings = request.sharing_settings.dict()

        config = await sharing_service.update_config(
            presentation_id=presentation_id,
            user_id=user_id,
            is_public=request.is_public,
            sharing_settings=sharing_settings,
        )

        return UpdateSharingConfigResponse(
            success=True, config=PresentationSharingConfig(**config)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update sharing config: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to update sharing config: {str(e)}")


@router.post("/presentations/{presentation_id}/sharing/users")
async def share_with_user(
    presentation_id: str,
    target_user_id: str,
    permission: str = "view",
    current_user: dict = Depends(get_current_user),
):
    """Share presentation with specific user"""
    try:
        user_id = current_user["uid"]
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()
        config = await sharing_service.share_with_user(
            presentation_id=presentation_id,
            owner_user_id=user_id,
            target_user_id=target_user_id,
            permission=permission,
        )

        return {"success": True, "message": "User added to sharing list"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to share with user: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to share with user: {str(e)}")


# ============================================================
# PUBLIC VIEW (NO AUTHENTICATION)
# ============================================================


@router.get("/public/presentations/{public_token}")
async def get_public_presentation(public_token: str):
    """
    Get public presentation (no authentication required)
    Returns presentation content, latest subtitles, and audio based on sharing settings
    """
    try:
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()
        logger.info(f"Public access: token={public_token}")

        # Get sharing config by token
        config = await sharing_service.get_public_presentation(public_token)

        if not config:
            raise HTTPException(404, "Presentation not found or not public")

        presentation_id = config["presentation_id"]
        sharing_settings = config["sharing_settings"]
        default_language = sharing_settings.get("default_language", "vi")

        # Get presentation document
        presentation = get_mongodb_service().db.documents.find_one(
            {"_id": ObjectId(presentation_id)}
        )

        if not presentation:
            raise HTTPException(404, "Presentation not found")

        # Prepare presentation data based on sharing settings
        presentation_data = {
            "id": str(presentation["_id"]),
            "title": presentation.get("title", ""),
            "document_type": presentation.get("document_type", "slide"),
        }

        # Include content if enabled
        if sharing_settings.get("include_content", True):
            presentation_data["content_html"] = presentation.get("content_html", "")
            presentation_data["slide_elements"] = presentation.get("slide_elements")
            presentation_data["slide_backgrounds"] = presentation.get(
                "slide_backgrounds"
            )

        # Get latest subtitle for default language if enabled
        subtitles = None
        if sharing_settings.get("include_subtitles", True):
            subtitle_doc = get_mongodb_service().db.presentation_subtitles.find_one(
                {"presentation_id": presentation_id, "language": default_language},
                sort=[("version", -1)],
            )
            if subtitle_doc:
                subtitle_doc["_id"] = str(subtitle_doc["_id"])
                subtitles = PresentationSubtitle(**subtitle_doc)

        # Get audio files if enabled
        audio_files = []
        if sharing_settings.get("include_audio", True) and subtitles:
            cursor = (
                get_mongodb_service()
                .db.presentation_audio.find(
                    {
                        "presentation_id": presentation_id,
                        "subtitle_id": str(subtitles.id),
                    }
                )
                .sort("slide_index", 1)
            )

            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                audio_files.append(PresentationAudio(**doc))

        # Increment access stats
        await sharing_service.increment_access_stats(config["_id"], unique_visitor=True)

        return PublicPresentationResponse(
            success=True,
            presentation=presentation_data,
            subtitles=subtitles,
            audio_files=audio_files,
            sharing_settings=sharing_settings,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public presentation: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get public presentation: {str(e)}")


@router.get("/public/presentations/{public_token}/subtitles")
async def get_public_subtitles(
    public_token: str, language: str = None, version: str = "latest"
):
    """Get public subtitles (no authentication required)"""
    try:
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()

        # Get sharing config
        config = await sharing_service.get_public_presentation(public_token)

        if not config:
            raise HTTPException(404, "Presentation not found or not public")

        if not config["sharing_settings"].get("include_subtitles", True):
            raise HTTPException(403, "Subtitles not shared")

        presentation_id = config["presentation_id"]
        default_language = config["sharing_settings"].get("default_language", "vi")
        language = language or default_language

        # Check allowed languages
        allowed_languages = config["sharing_settings"].get("allowed_languages", [])
        if allowed_languages and language not in allowed_languages:
            raise HTTPException(403, f"Language {language} not allowed")

        # Get subtitle
        query = {"presentation_id": presentation_id, "language": language}

        if version == "latest":
            subtitle_doc = get_mongodb_service().db.presentation_subtitles.find_one(
                query, sort=[("version", -1)]
            )
        else:
            query["version"] = int(version)
            subtitle_doc = get_mongodb_service().db.presentation_subtitles.find_one(
                query
            )

        if not subtitle_doc:
            raise HTTPException(404, "Subtitles not found")

        subtitle_doc["_id"] = str(subtitle_doc["_id"])
        return {"success": True, "subtitle": PresentationSubtitle(**subtitle_doc)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public subtitles: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get public subtitles: {str(e)}")


@router.get("/public/presentations/{public_token}/audio")
async def get_public_audio(
    public_token: str, language: str = None, version: str = "latest"
):
    """Get public audio files (no authentication required)"""
    try:
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()

        # Get sharing config
        config = await sharing_service.get_public_presentation(public_token)

        if not config:
            raise HTTPException(404, "Presentation not found or not public")

        if not config["sharing_settings"].get("include_audio", True):
            raise HTTPException(403, "Audio not shared")

        presentation_id = config["presentation_id"]
        default_language = config["sharing_settings"].get("default_language", "vi")
        language = language or default_language

        # Check allowed languages
        allowed_languages = config["sharing_settings"].get("allowed_languages", [])
        if allowed_languages and language not in allowed_languages:
            raise HTTPException(403, f"Language {language} not allowed")

        # Get subtitle to find version
        query = {"presentation_id": presentation_id, "language": language}

        if version == "latest":
            subtitle = get_mongodb_service().db.presentation_subtitles.find_one(
                query, sort=[("version", -1)]
            )
        else:
            query["version"] = int(version)
            subtitle = get_mongodb_service().db.presentation_subtitles.find_one(query)

        if not subtitle:
            raise HTTPException(404, "Subtitles not found for audio")

        # Get audio files
        cursor = (
            get_mongodb_service()
            .db.presentation_audio.find(
                {
                    "presentation_id": presentation_id,
                    "subtitle_id": str(subtitle["_id"]),
                }
            )
            .sort("slide_index", 1)
        )

        audio_files = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            audio_files.append(PresentationAudio(**doc))

        return {"success": True, "audio_files": audio_files}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public audio: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get public audio: {str(e)}")
