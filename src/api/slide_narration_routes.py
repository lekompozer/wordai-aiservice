"""
Slide Narration API Routes
2-step flow: Subtitles (2 points) → Audio (2 points)
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging
from bson import ObjectId
from typing import List, Dict, Any, Optional

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
    # Job queue models
    CreateSubtitleJobResponse,
    SubtitleJobStatusResponse,
    SubtitleJobStatus,
    # Chunk management models
    AudioChunkInfo,
    ListAudioChunksResponse,
    RegenerateChunkRequest,
    RegenerateChunkResponse,
    MergeChunksResponse,
    # Presentation mode preference models
    SetDefaultVersionRequest,
    SetDefaultVersionResponse,
    LanguagePlayerData,
    GetPlayerDataResponse,
)
from src.models.video_export_models import (
    VideoExportRequest,
    VideoExportSettings,
    VideoExportCreateResponse,
    ExportStatus,
)
from src.services.slide_narration_service import get_slide_narration_service
from src.services.points_service import get_points_service
from src.middleware.firebase_auth import get_current_user
from src.services.document_manager import DocumentManager
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")
router = APIRouter(prefix="/api")

# Initialize database
db_manager = DBManager()
db = db_manager.db

logger.info("=" * 80)
logger.info("🎤 SLIDE NARRATION ROUTER INITIALIZED")
logger.info(f"   Prefix: /api")
logger.info(f"   Routes will be: /api/presentations/{{id}}/narration/*")
logger.info("=" * 80)


# Points cost for each step
POINTS_COST_SUBTITLE = 2
POINTS_COST_AUDIO = 3


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

        # Validate presentation_id if provided in body
        if request.presentation_id and request.presentation_id != presentation_id:
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
        doc_manager = DocumentManager(db)
        document = db.documents.find_one(
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

        insert_result = db.slide_narrations.insert_one(narration_doc)
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
    "/presentations/{presentation_id}/subtitles/generate",
    response_model=CreateSubtitleJobResponse,
    summary="Generate Subtitles (Async Job Queue)",
    description="""
    **STEP 1 (ASYNC): Generate subtitles with timestamps via background job**

    Enqueues subtitle generation job to Redis worker queue.
    Returns job_id immediately for status polling.

    **Cost:** 2 points (deducted after completion)

    **Features:**
    - Non-blocking API (returns immediately)
    - Poll job status with GET /subtitle-jobs/{job_id}
    - Mode-aware narration (presentation: concise, academy: detailed)
    - Element reference tracking for animation sync
    - Automatic timestamp calculation

    **Flow:**
    1. Validate presentation ownership
    2. Extract slides from document
    3. Create Redis job (status: pending)
    4. Return job_id immediately
    5. Worker processes in background
    6. Poll /subtitle-jobs/{job_id} for results

    **Job Status Values:**
    - pending: Queued, waiting for worker
    - processing: Worker is generating subtitles
    - completed: Success, subtitle_id available
    - failed: Error occurred

    Next step: Wait for completion, then generate audio (Step 2)
    """,
)
async def generate_subtitles_async(
    presentation_id: str,
    request: SubtitleGenerateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate subtitles for presentation (async job queue)"""
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "unknown")

        logger.info("=" * 80)
        logger.info(f"🎙️ ASYNC SUBTITLE GENERATION REQUEST")
        logger.info(
            f"📍 Endpoint: POST /api/presentations/{presentation_id}/subtitles/generate"
        )
        logger.info(f"👤 User: {user_email} ({user_id})")
        logger.info(
            f"🎛️ Mode: {request.mode}, Language: {request.language}, Scope: {request.scope}"
        )
        logger.info("=" * 80)

        # Validate presentation_id if provided in body
        if request.presentation_id and request.presentation_id != presentation_id:
            raise HTTPException(400, "Presentation ID mismatch")

        # Fetch document
        doc_manager = DocumentManager(db)
        document = db.documents.find_one(
            {"document_id": presentation_id, "document_type": "slide"}
        )

        if not document:
            raise HTTPException(404, "Slide document not found")

        # Check ownership
        if document.get("user_id") != user_id:
            raise HTTPException(403, "Not authorized to narrate this presentation")

        # Extract slides from HTML using BeautifulSoup (same as frontend)
        content_html = document.get("content_html", "")
        if not content_html:
            raise HTTPException(400, "Document has no content")

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content_html, "html.parser")

        # FIX: Check all 3 selectors and pick the one with MOST results (>1)
        # Priority: [data-slide-index] > .slide > section
        by_attr = soup.select("[data-slide-index]")
        by_class = soup.select(".slide")
        by_section = soup.select("section")

        logger.info(
            f"🔍 Selector results: [data-slide-index]={len(by_attr)}, .slide={len(by_class)}, section={len(by_section)}"
        )

        # Choose the selector with most elements (avoiding wrapper divs)
        slide_elements = (
            by_attr
            if len(by_attr) > 1
            else (by_class if len(by_class) > len(by_attr) else by_section)
        )

        # If still only 1 or 0, try fallback to any selector that has results
        if len(slide_elements) <= 1:
            if len(by_class) > len(slide_elements):
                slide_elements = by_class
            elif len(by_section) > len(slide_elements):
                slide_elements = by_section

        if not slide_elements:
            raise HTTPException(
                400, f"No slides found in document. Content length: {len(content_html)}"
            )

        logger.info(f"✅ Using selector with {len(slide_elements)} slide elements")

        # Prepare background lookup map (slideIndex -> background data)
        slide_backgrounds = document.get("slide_backgrounds", [])
        background_map = {
            int(bg.get("slideIndex")): bg
            for bg in slide_backgrounds
            if bg.get("slideIndex") is not None
        }

        # Build slides array
        slides = []
        for idx, element in enumerate(slide_elements):
            # Try to get index from attribute with safe conversion
            attr_index = element.get("data-slide-index")
            slide_index = idx  # Default to loop index
            
            if attr_index is not None:
                try:
                    # Ensure it's a string and try to convert to int
                    slide_index = int(str(attr_index).strip())
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Invalid data-slide-index '{attr_index}' at position {idx}, using index {idx}")
                    slide_index = idx

            # Extract ONLY text content (no HTML tags) for AI subtitle generation
            slide_text = element.get_text(separator=" ", strip=True)

            slides.append(
                {
                    "index": slide_index,
                    "html": slide_text,  # Changed: plain text only, not HTML
                    "elements": [],
                    "background": background_map.get(slide_index),
                }
            )

        logger.info(
            f"📄 Extracted {len(slides)} slides from document (text-only for subtitle generation)"
        )

        # Filter slides by scope
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

            slides = [slides[request.current_slide_index]]
            logger.info(
                f"🎯 Generating subtitles for slide {request.current_slide_index}"
            )
        else:
            logger.info(f"📊 Generating subtitles for all {len(slides)} slides")

        # Generate job ID
        import uuid

        job_id = str(uuid.uuid4())

        # Create task for queue
        from src.models.ai_queue_tasks import SlideNarrationSubtitleTask

        task = SlideNarrationSubtitleTask(
            task_id=job_id,
            job_id=job_id,
            user_id=user_id,
            presentation_id=presentation_id,
            slides=slides,
            mode=request.mode,
            language=request.language,
            user_query=request.user_query or "",
            title=document.get("title", "Untitled"),
            topic=document.get("metadata", {}).get("topic", ""),
            scope=request.scope,
            current_slide_index=request.current_slide_index,
        )

        # Get queue and enqueue
        from src.queue.queue_dependencies import get_slide_narration_subtitle_queue

        queue = await get_slide_narration_subtitle_queue()
        await queue.enqueue_generic_task(task)

        logger.info(f"✅ Subtitle job {job_id} enqueued")
        logger.info(
            f"   Slides: {len(slides)}, Mode: {request.mode}, Lang: {request.language}"
        )

        return CreateSubtitleJobResponse(
            job_id=job_id,
            status=SubtitleJobStatus.PENDING,
            message=f"Subtitle generation job created. Poll /subtitle-jobs/{job_id} for status.",
            estimated_time="30-90 seconds",
            presentation_id=presentation_id,
            slide_count=len(slides),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create subtitle job: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to create subtitle job: {str(e)}")


@router.get(
    "/subtitle-jobs/{job_id}",
    response_model=SubtitleJobStatusResponse,
    summary="Get Subtitle Job Status",
    description="""
    Poll subtitle generation job status.

    **Status Flow:**
    - pending → processing → completed (success)
    - pending → processing → failed (error)

    **When Completed:**
    - subtitle_id: Use this to generate audio
    - version: Subtitle version number
    - total_duration: Total duration in seconds

    **Polling Recommendation:**
    - Poll every 2-3 seconds during processing
    - Stop polling when status is 'completed' or 'failed'
    """,
)
async def get_subtitle_job_status(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get subtitle generation job status"""
    try:
        from src.queue.queue_dependencies import get_slide_narration_subtitle_queue
        from src.queue.queue_manager import get_job_status

        queue = await get_slide_narration_subtitle_queue()
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            raise HTTPException(404, f"Job {job_id} not found")

        # Check authorization (job must belong to current user)
        if job.get("user_id") != current_user["uid"]:
            raise HTTPException(403, "Not authorized to view this job")

        # Calculate processing time if started
        processing_time = None
        if job.get("started_at") and job.get("status") in ["completed", "failed"]:
            from datetime import datetime

            started = datetime.fromisoformat(job["started_at"])
            ended = datetime.utcnow()
            processing_time = (ended - started).total_seconds()

        return SubtitleJobStatusResponse(
            job_id=job_id,
            status=job.get("status", "pending"),
            created_at=job.get("created_at"),
            started_at=job.get("started_at"),
            processing_time_seconds=processing_time,
            presentation_id=job.get("presentation_id"),
            slide_count=job.get("slide_count"),
            subtitle_id=job.get("subtitle_id"),
            version=job.get("version"),
            total_duration=job.get("total_duration"),
            error=job.get("error"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get job status: {str(e)}")


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
        narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
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
        db.slide_narrations.update_one(
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
    "/presentations/{presentation_id}/narration/{narration_id}/audio-job-status",
    summary="Get Latest Audio Job Status",
    description="""
    **Get the latest audio generation job status for a narration**

    Use this endpoint when:
    - Opening a document to check if audio exists or is being generated
    - Opening the audio creation dialog to show appropriate UI
    - Checking if there's a pending/failed job that needs retry

    Returns:
    - has_job: false → No audio generation attempted yet (show "Generate" button)
    - status: completed → Audio ready to play
    - status: processing → Job in progress (start polling)
    - status: partial_success → Some chunks failed (show retry button)
    - status: failed → Complete failure (show retry button)
    """,
)
async def get_latest_audio_job_status(
    presentation_id: str,
    narration_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get latest audio job status for dialog/retry"""
    try:
        user_id = current_user["uid"]

        # Support both v1 (slide_narrations) and v2 (presentation_subtitles)
        # Try v2 first (current system)
        subtitle = db.presentation_subtitles.find_one({"_id": ObjectId(narration_id)})

        if not subtitle:
            # Fallback to v1
            subtitle = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})

        if not subtitle:
            raise HTTPException(404, "Subtitle/Narration not found")

        if str(subtitle.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to access this subtitle")

        # Find latest job for this subtitle/narration
        latest_job = db.narration_audio_jobs.find_one(
            {
                "presentation_id": presentation_id,
                "subtitle_id": narration_id,
                "user_id": user_id,
            },
            sort=[("created_at", -1)],  # Get most recent
        )

        if not latest_job:
            # No job exists yet
            return {
                "success": True,
                "has_job": False,
                "audio_ready": False,
                "message": "No audio generation job found. Click Generate to create.",
            }

        # Job exists - extract status info
        job_id = str(latest_job["_id"])
        status = latest_job.get("status", "unknown")

        response = {
            "success": True,
            "has_job": True,
            "job_id": job_id,
            "status": status,
            "audio_ready": status == "completed",
            "created_at": latest_job.get("created_at"),
            "updated_at": latest_job.get("updated_at"),
        }

        # Add status-specific fields
        if status == "completed":
            # Get audio file info
            audio_docs = list(
                db.presentation_audio.find(
                    {
                        "presentation_id": presentation_id,
                        "subtitle_id": narration_id,
                        "user_id": user_id,
                        "status": "ready",
                        "audio_type": "merged_presentation",  # Get final merged audio
                    }
                )
                .sort("created_at", -1)
                .limit(1)
            )

            if audio_docs:
                audio = audio_docs[0]
                response["audio_url"] = audio.get("audio_url")
                response["slide_timestamps"] = audio.get("slide_timestamps", [])

            # Count chunks for progress info
            all_chunks = list(
                db.presentation_audio.find(
                    {
                        "presentation_id": presentation_id,
                        "subtitle_id": narration_id,
                        "user_id": user_id,
                        "audio_type": "chunked",
                    }
                )
            )
            response["chunks_completed"] = len(all_chunks)
            response["chunks_total"] = len(all_chunks)

        elif status == "partial_success":
            response["error"] = latest_job.get("error", "Partial failure")
            response["retry_message"] = latest_job.get(
                "retry_message", "Retry to continue"
            )

            # Count completed chunks
            completed_chunks = list(
                db.presentation_audio.find(
                    {
                        "presentation_id": presentation_id,
                        "subtitle_id": narration_id,
                        "user_id": user_id,
                        "status": "ready",
                        "audio_type": "chunked",
                    }
                )
            )

            response["chunks_completed"] = len(completed_chunks)

            # Parse total chunks from error message (e.g., "2/6 chunks")
            error_msg = latest_job.get("error", "")
            import re

            match = re.search(r"(\d+)/(\d+) chunks", error_msg)
            if match:
                response["chunks_total"] = int(match.group(2))

                # Calculate failed chunks
                total = int(match.group(2))
                completed = len(completed_chunks)
                response["failed_chunks"] = list(range(completed, total))

        elif status == "processing" or status == "queued":
            response["message"] = "Audio generation in progress..."

            # Count completed chunks so far
            completed_chunks = list(
                db.presentation_audio.find(
                    {
                        "presentation_id": presentation_id,
                        "subtitle_id": narration_id,
                        "user_id": user_id,
                        "status": "ready",
                        "audio_type": "chunked",
                    }
                )
            )

            response["chunks_completed"] = len(completed_chunks)

            # Estimate total from job metadata if available
            if latest_job.get("total_chunks"):
                response["chunks_total"] = latest_job.get("total_chunks")

        elif status == "failed":
            response["error"] = latest_job.get("error", "Unknown error")
            response["retry_message"] = latest_job.get(
                "retry_message", "Please try again"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get audio job status: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get job status: {str(e)}")


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
        document = db.documents.find_one(
            {"document_id": presentation_id, "document_type": "slide"}
        )
        if not document:
            raise HTTPException(404, "Presentation not found")

        if document.get("user_id") != user_id:
            raise HTTPException(403, "Not authorized to view this presentation")

        # Fetch all narrations (presentation_id and user_id are strings)
        cursor = db.slide_narrations.find(
            {
                "presentation_id": presentation_id,
                "user_id": user_id,
            }
        ).sort("created_at", -1)

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
    latest = db.slide_narrations.find_one(
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
async def get_narration_detail(
    presentation_id: str,
    narration_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete narration version"""
    try:
        user_id = current_user["uid"]

        # Fetch narration
        narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
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
        narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
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
        db.slide_narrations.update_one(
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
        narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
        if not narration:
            raise HTTPException(404, "Narration not found")

        # Check ownership
        if str(narration.get("user_id")) != user_id:
            raise HTTPException(403, "Not authorized to delete this narration")

        # Check presentation_id matches
        if str(narration.get("presentation_id")) != presentation_id:
            raise HTTPException(400, "Narration does not belong to this presentation")

        # Delete associated audio files from library_audio
        # Note: Audio files are stored in presentation_audio collection
        # They will be orphaned when narration is deleted (acceptable for now)
        audio_files = narration.get("audio_files", [])
        if audio_files:
            # TODO: Implement audio file cleanup from R2 storage
            # from src.services.audio_service import AudioService
            # audio_service = AudioService()
            # for audio in audio_files:
            #     library_audio_id = audio.get("library_audio_id")
            #     if library_audio_id:
            #         try:
            #             await audio_service.delete_audio(library_audio_id)
            #             logger.info(f"   Deleted audio: {library_audio_id}")
            #         except Exception as e:
            #             logger.warning(f"   Failed to delete audio {library_audio_id}: {e}")
            logger.info(f"   Skipping audio file deletion ({len(audio_files)} files)")

        # Delete narration record
        db.slide_narrations.delete_one({"_id": ObjectId(narration_id)})

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
        total_count = db.library_audio.count_documents(query)

        # Fetch audio files with pagination
        cursor = (
            db.library_audio.find(query)
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
                        doc.get("created_at")
                        if doc.get("created_at")
                        else datetime.utcnow()
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
        narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
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
            audio_doc = db.library_audio.find_one({"_id": ObjectId(library_audio_id)})

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
        db.slide_narrations.update_one(
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
        narration = db.slide_narrations.find_one({"_id": ObjectId(narration_id)})
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
        db.slide_narrations.update_one(
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
    version: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate subtitles for specific language (multi-language system)
    Deducts 2 points from user

    Parameters:
    - version: Optional version number. If not provided, uses latest version.
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
    language: Optional[str] = None,
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
        cursor = db.presentation_subtitles.find(query).sort(
            [("language", 1), ("version", -1)]
        )

        subtitles = []
        for doc in cursor:
            # Convert ObjectId to string for Pydantic
            doc["_id"] = str(doc["_id"])

            # Populate audio_url from merged_audio_id if exists
            if doc.get("merged_audio_id"):
                try:
                    audio_doc = db.presentation_audio.find_one(
                        {"_id": ObjectId(doc["merged_audio_id"])}
                    )
                    if audio_doc and audio_doc.get("audio_url"):
                        # Add audio_url to subtitle document
                        doc["audio_url"] = audio_doc["audio_url"]
                        logger.info(
                            f"   ✅ Populated audio_url for subtitle {doc['_id']}: {audio_doc.get('audio_url')}"
                        )
                except Exception as e:
                    logger.warning(
                        f"   ⚠️ Failed to populate audio_url for subtitle {doc['_id']}: {e}"
                    )

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
    """Get specific subtitle document with audio information"""
    try:
        user_id = current_user["uid"]

        # Get subtitle
        subtitle = db.presentation_subtitles.find_one(
            {"_id": ObjectId(subtitle_id), "user_id": user_id}
        )

        if not subtitle:
            raise HTTPException(404, "Subtitle not found")

        subtitle["_id"] = str(subtitle["_id"])

        # Include audio info if available and populate audio_url in subtitle
        audio_info = None
        if subtitle.get("merged_audio_id"):
            audio_doc = db.presentation_audio.find_one(
                {"_id": ObjectId(subtitle["merged_audio_id"])}
            )
            if audio_doc:
                # Add audio_url directly to subtitle document for frontend
                if audio_doc.get("audio_url"):
                    subtitle["audio_url"] = audio_doc["audio_url"]

                audio_info = {
                    "audio_id": str(audio_doc["_id"]),
                    "audio_url": audio_doc.get("audio_url"),
                    "audio_type": audio_doc.get("audio_type"),
                    "duration_seconds": audio_doc.get("audio_metadata", {}).get(
                        "duration_seconds", 0
                    ),
                    "slide_count": audio_doc.get("slide_count", 0),
                    "slide_timestamps": audio_doc.get("slide_timestamps", []),
                    "status": audio_doc.get("status"),
                    "created_at": audio_doc.get("created_at"),
                }

        return {
            "success": True,
            "subtitle": PresentationSubtitle(**subtitle),
            "audio": audio_info,  # Include audio info
        }

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
        subtitle = db.presentation_subtitles.find_one(
            {"_id": ObjectId(subtitle_id), "user_id": user_id}
        )

        if not subtitle:
            raise HTTPException(404, "Subtitle not found")

        # Delete associated audio files
        db.presentation_audio.delete_many({"subtitle_id": subtitle_id})

        # Delete subtitle
        db.presentation_subtitles.delete_one({"_id": ObjectId(subtitle_id)})

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
    **Queue audio generation job for subtitle document**

    Returns job_id immediately for polling.
    Deducts 2 points from user.

    **Processing time:** ~30-60 seconds per slide (runs in background)
    """
    try:
        user_id = current_user["uid"]
        logger.info(f"📋 Queueing audio generation: subtitle={subtitle_id}")

        # Deduct points upfront
        points_service = get_points_service()
        await points_service.deduct_points(
            user_id=user_id,
            amount=2,
            service="slide_narration",
            resource_id=subtitle_id,
            description="Generate audio (queued)",
        )

        # Create job in MongoDB
        import uuid
        from src.queue.queue_dependencies import get_slide_narration_audio_queue
        from src.models.ai_queue_tasks import SlideNarrationAudioTask

        # Handle force regenerate: Delete existing chunks if requested
        if request.force_regenerate:
            deleted_count = db.presentation_audio.delete_many(
                {"subtitle_id": subtitle_id, "user_id": user_id}
            ).deleted_count
            logger.info(
                f"🔄 Force regenerate: Deleted {deleted_count} existing audio chunks"
            )

        job_id = str(uuid.uuid4())
        job_doc = {
            "_id": job_id,
            "user_id": user_id,
            "presentation_id": presentation_id,
            "subtitle_id": subtitle_id,
            "voice_config": request.voice_config.dict(),
            "force_regenerate": request.force_regenerate,
            "status": "queued",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        db.narration_audio_jobs.insert_one(job_doc)

        # Queue task
        task = SlideNarrationAudioTask(
            task_id=job_id,
            job_id=job_id,
            user_id=user_id,
            presentation_id=presentation_id,
            subtitle_id=subtitle_id,
            voice_config=request.voice_config.dict(),
            force_regenerate=request.force_regenerate,
        )

        queue = await get_slide_narration_audio_queue()
        success = await queue.enqueue_generic_task(task)

        if not success:
            raise HTTPException(500, "Failed to queue audio generation task")

        logger.info(f"✅ Audio job queued: {job_id}")

        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Audio generation queued. Use job_id to poll status.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to queue audio generation: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to queue audio: {str(e)}")


@router.get(
    "/presentations/{presentation_id}/subtitles/v2/{subtitle_id}/audio/status/{job_id}"
)
async def get_audio_generation_status(
    presentation_id: str,
    subtitle_id: str,
    job_id: str,
):
    """
    **Poll audio generation job status**

    Returns current status + audio files when completed.

    ⚠️ No authentication required - job_id acts as secure token (UUID random).
    This allows long-running jobs without Firebase token expiration issues.

    ✅ Checks Redis first (real-time worker updates), fallback to MongoDB (persistent storage)
    """
    try:
        from src.queue.queue_dependencies import get_slide_narration_audio_queue
        from src.queue.queue_manager import get_job_status

        # Get Redis queue manager
        queue = await get_slide_narration_audio_queue()

        # Check Redis first (real-time status from worker)
        # Worker uses set_job_status() → key pattern: job:{job_id}
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            # Fallback: Check MongoDB for persistent record (after Redis 24h TTL expires)
            job = db.narration_audio_jobs.find_one({"_id": job_id})

        if not job:
            raise HTTPException(404, "Job not found")

        status = job.get("status", "unknown")
        user_id = job.get("user_id")

        response = {
            "job_id": job_id,
            "status": status,
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
        }

        # If processing, include progress info
        if status == "processing":
            response["progress"] = {
                "total_slides": job.get("total_slides", 0),
                "completed_chunks": job.get("completed_chunks", 0),
                "failed_chunks": job.get("failed_chunks", []),
                "current_chunk": job.get("current_chunk"),
            }

        # If completed, include audio files
        elif status == "completed":
            audio_docs = list(
                db.presentation_audio.find(
                    {"subtitle_id": subtitle_id, "user_id": user_id}
                ).sort("slide_index", 1)
            )

            # Convert ObjectId to string for Pydantic validation
            for doc in audio_docs:
                if "_id" in doc and hasattr(doc["_id"], "__str__"):
                    doc["_id"] = str(doc["_id"])

            response["audio_files"] = [PresentationAudio(**doc) for doc in audio_docs]

        # If failed, include error
        elif status == "failed":
            response["error"] = job.get("error", "Unknown error")
            # Also include partial progress if any chunks succeeded
            if job.get("completed_chunks", 0) > 0:
                response["progress"] = {
                    "total_slides": job.get("total_slides", 0),
                    "completed_chunks": job.get("completed_chunks", 0),
                    "failed_chunks": job.get("failed_chunks", []),
                }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get status: {str(e)}")


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
    language: Optional[str] = None,
    version: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List audio files for presentation
    Optional filter by language and version
    """
    try:
        user_id = current_user["uid"]

        # Build query
        query = {
            "presentation_id": presentation_id,
            "user_id": user_id,
            "status": {"$ne": "obsolete_chunk"},  # Exclude obsolete chunks
        }
        if language:
            query["language"] = language
        if version:
            query["version"] = version

        # Get audio files
        cursor = db.presentation_audio.find(query).sort(
            [("language", 1), ("version", -1), ("slide_index", 1)]
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
        audio = db.presentation_audio.find_one(
            {"_id": ObjectId(audio_id), "user_id": user_id}
        )

        if not audio:
            raise HTTPException(404, "Audio not found")

        # Delete audio document
        db.presentation_audio.delete_one({"_id": ObjectId(audio_id)})

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


# ============================================================
# SHARING ENDPOINTS (alternative route for frontend compatibility)
# ============================================================


@router.get(
    "/presentations/sharing/{presentation_id}",
    response_model=UpdateSharingConfigResponse,
    summary="Get Sharing Config (Alternative Route)",
    description="""
    **Alternative route for frontend compatibility**

    Same as GET /presentations/{presentation_id}/sharing
    Returns sharing configuration for a presentation.
    """,
)
async def get_sharing_config_alt(
    presentation_id: str, current_user: dict = Depends(get_current_user)
):
    """Get sharing configuration (alternative route pattern)"""
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


@router.put(
    "/presentations/sharing/{presentation_id}",
    response_model=UpdateSharingConfigResponse,
    summary="Update Sharing Config (Alternative Route)",
    description="""
    **Alternative route for frontend compatibility**

    Same as PUT /presentations/{presentation_id}/sharing
    Updates sharing configuration for a presentation.
    """,
)
async def update_sharing_config_alt(
    presentation_id: str,
    request: UpdateSharingConfigRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update sharing configuration (alternative route pattern)"""
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


@router.delete("/presentations/sharing/{presentation_id}/users/{target_user_id}")
async def remove_user_share(
    presentation_id: str,
    target_user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove user from presentation sharing list"""
    try:
        user_id = current_user["uid"]
        from src.services.sharing_service import get_sharing_service

        sharing_service = get_sharing_service()

        # Remove user from shared_with list
        config = await sharing_service.remove_shared_user(
            presentation_id=presentation_id,
            owner_user_id=user_id,
            target_user_id=target_user_id,
        )

        return {"success": True, "message": "User removed from sharing list"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to remove user share: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to remove user share: {str(e)}")


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
        presentation = db.documents.find_one({"document_id": presentation_id})

        if not presentation:
            raise HTTPException(404, "Presentation not found")

        # Prepare presentation data based on sharing settings
        presentation_data = {
            "id": str(presentation["_id"]),
            "document_id": presentation.get(
                "document_id"
            ),  # Add document_id for video export
            "title": presentation.get("title", ""),
            "document_type": presentation.get("document_type", "slide"),
        }

        # Include content if enabled
        if sharing_settings.get("include_content", True):
            presentation_data["content_html"] = presentation.get("content_html", "")

            # Get slide_elements (main field with all slides)
            slide_elements = presentation.get("slide_elements")
            presentation_data["slide_elements"] = slide_elements

            # Keep slide_backgrounds for backward compatibility
            presentation_data["slide_backgrounds"] = presentation.get(
                "slide_backgrounds"
            )

        # Get subtitles for all allowed languages if enabled
        language_data_list = []
        allowed_languages = sharing_settings.get(
            "allowed_languages", [default_language]
        )

        if sharing_settings.get("include_subtitles", True):
            logger.info(f"   Loading subtitles for languages: {allowed_languages}")

            for lang in allowed_languages:
                # Get latest subtitle for this language
                subtitle_doc = db.presentation_subtitles.find_one(
                    {"presentation_id": presentation_id, "language": lang},
                    sort=[("version", -1)],
                )

                if not subtitle_doc:
                    logger.info(f"   ⚠️ No subtitle found for {lang}")
                    continue

                subtitle_doc["_id"] = str(subtitle_doc["_id"])
                subtitle = PresentationSubtitle(**subtitle_doc)

                # Get audio files if enabled - with fallback to older versions
                audio_files = []
                audio_url = None
                audio_id = None
                audio_status = subtitle_doc.get("audio_status")

                if sharing_settings.get("include_audio", True):
                    # Try to get audio from latest subtitle first
                    audio_subtitle_id = None
                    if subtitle_doc.get("merged_audio_id"):
                        audio_doc = db.presentation_audio.find_one(
                            {"_id": ObjectId(subtitle_doc["merged_audio_id"])}
                        )
                        if audio_doc and audio_doc.get("audio_url"):
                            audio_subtitle_id = str(subtitle_doc["_id"])
                            audio_url = audio_doc.get("audio_url")
                            audio_id = str(audio_doc["_id"])
                            logger.info(
                                f"      Audio found in {lang} version {subtitle_doc['version']}"
                            )

                    # If no audio in latest version, fallback to older versions
                    if not audio_subtitle_id:
                        logger.info(
                            f"      No audio in {lang} version {subtitle_doc['version']}, checking older versions..."
                        )
                        fallback_subtitles = db.presentation_subtitles.find(
                            {"presentation_id": presentation_id, "language": lang}
                        ).sort("version", -1)

                        for fallback_doc in fallback_subtitles:
                            # Skip if same as latest
                            if str(fallback_doc["_id"]) == str(subtitle_doc["_id"]):
                                continue

                            if fallback_doc.get("merged_audio_id"):
                                audio_doc = db.presentation_audio.find_one(
                                    {"_id": ObjectId(fallback_doc["merged_audio_id"])}
                                )
                                if audio_doc and audio_doc.get("audio_url"):
                                    audio_subtitle_id = str(fallback_doc["_id"])
                                    audio_url = audio_doc.get("audio_url")
                                    audio_id = str(audio_doc["_id"])
                                    audio_status = fallback_doc.get("audio_status")
                                    logger.info(
                                        f"      ✅ Fallback: Using {lang} audio from version {fallback_doc['version']}"
                                    )
                                    break

                    # Load audio files if found subtitle with audio
                    if audio_subtitle_id:
                        cursor = db.presentation_audio.find(
                            {
                                "presentation_id": presentation_id,
                                "subtitle_id": audio_subtitle_id,
                            }
                        ).sort("slide_index", 1)

                        for doc in cursor:
                            doc["_id"] = str(doc["_id"])
                            audio_files.append(PresentationAudio(**doc))
                    else:
                        logger.info(f"      ⚠️ No audio found in any version for {lang}")

                # Calculate total duration from slides or audio_metadata
                total_duration = 0
                if subtitle_doc.get("audio_metadata") and isinstance(
                    subtitle_doc["audio_metadata"], dict
                ):
                    total_duration = subtitle_doc["audio_metadata"].get(
                        "duration_seconds", 0
                    )

                # Build language data
                lang_data = {
                    "language": lang,
                    "subtitle": subtitle,  # Store full object for backward compatibility
                    "subtitle_id": str(subtitle.id),
                    "version": subtitle.version,
                    "is_default": (lang == default_language),
                    "slides": subtitle.slides,
                    "total_duration": total_duration,
                    "audio_url": audio_url,
                    "audio_id": audio_id,
                    "audio_status": audio_status,
                    "audio_files": audio_files,
                }
                language_data_list.append(lang_data)

            logger.info(f"   ✅ Loaded {len(language_data_list)} languages")

        # For backward compatibility, set subtitles to default language
        subtitles = None
        audio_files = []
        for lang_data in language_data_list:
            if lang_data["is_default"]:
                subtitles = lang_data["subtitle"]  # Use full parsed object
                audio_files = lang_data["audio_files"]
                break

        # Clean up language_data_list for JSON serialization
        # Remove subtitle object (already serialized), keep only flat fields
        cleaned_languages = []
        for lang_data in language_data_list:
            cleaned_lang = {
                "language": lang_data["language"],
                "subtitle_id": lang_data["subtitle_id"],
                "version": lang_data["version"],
                "is_default": lang_data["is_default"],
                "slides": lang_data["slides"],
                "total_duration": lang_data["total_duration"],
                "audio_url": lang_data["audio_url"],
                "audio_id": lang_data["audio_id"],
                "audio_status": lang_data["audio_status"],
                "audio_files": [
                    {
                        "_id": str(audio.id),
                        "slide_index": audio.slide_index,
                        "audio_url": audio.audio_url,
                        "duration": (
                            audio.audio_metadata.duration_seconds
                            if audio.audio_metadata
                            else 0
                        ),
                        "slide_timestamps": audio.slide_timestamps,  # For auto-advance slides
                        "audio_type": audio.audio_type,
                        "chunk_index": audio.chunk_index,
                        "total_chunks": audio.total_chunks,
                    }
                    for audio in lang_data["audio_files"]
                ],
            }
            cleaned_languages.append(cleaned_lang)

        # Increment access stats
        await sharing_service.increment_access_stats(config["_id"], unique_visitor=True)

        return PublicPresentationResponse(
            success=True,
            presentation=presentation_data,
            subtitles=subtitles,
            audio_files=audio_files,
            languages=cleaned_languages,
            sharing_settings=sharing_settings,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public presentation: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get public presentation: {str(e)}")


@router.get("/public/presentations/{public_token}/subtitles")
async def get_public_subtitles(
    public_token: str, language: Optional[str] = None, version: str = "latest"
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
            subtitle_doc = db.presentation_subtitles.find_one(
                query, sort=[("version", -1)]
            )
        else:
            query["version"] = int(version)
            subtitle_doc = db.presentation_subtitles.find_one(query)

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
    public_token: str, language: Optional[str] = None, version: str = "latest"
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
            subtitle = db.presentation_subtitles.find_one(query, sort=[("version", -1)])
        else:
            query["version"] = int(version)
            subtitle = db.presentation_subtitles.find_one(query)

        if not subtitle:
            raise HTTPException(404, "Subtitles not found for audio")

        # Get audio files
        cursor = db.presentation_audio.find(
            {
                "presentation_id": presentation_id,
                "subtitle_id": str(subtitle["_id"]),
            }
        ).sort("slide_index", 1)

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


# ============================================================
# CHUNK MANAGEMENT ENDPOINTS (debugging & regeneration)
# ============================================================


@router.get(
    "/presentations/{presentation_id}/audio/{subtitle_id}/chunks",
    response_model=ListAudioChunksResponse,
    summary="List All Audio Chunks for Debugging",
    description="""
    **List all audio chunks with detailed information for debugging**

    Returns all audio chunks for a subtitle document, including:
    - Chunk index and audio URL
    - Slides included in each chunk
    - Duration and file size
    - RMS level (audio quality indicator)
    - Creation timestamp

    Use this to:
    - Debug which chunks failed generation
    - Identify silent/corrupt audio chunks
    - Verify chunk splitting logic
    - Find chunks that need regeneration

    **Example use case:**
    If chunk 2 has RMS < 1000 while others have RMS > 2000, it likely failed.
    """,
)
async def list_audio_chunks(
    presentation_id: str,
    subtitle_id: str,
    user: dict = Depends(get_current_user),
):
    """List all audio chunks with detailed debug information"""
    try:
        # Verify user owns presentation
        doc_manager = DocumentManager(db)
        presentation = doc_manager.get_document(presentation_id, user["uid"])
        if not presentation:
            raise HTTPException(404, "Presentation not found")
        if presentation["userId"] != user["uid"]:
            raise HTTPException(403, "Not your presentation")

        # Get subtitle document
        subtitle = db.presentation_subtitles.find_one({"_id": ObjectId(subtitle_id)})
        if not subtitle:
            raise HTTPException(404, "Subtitle not found")
        if subtitle["presentation_id"] != presentation_id:
            raise HTTPException(400, "Subtitle not for this presentation")

        # Get all audio chunks
        cursor = db.presentation_audio.find(
            {"subtitle_id": subtitle_id, "chunk_index": {"$exists": True}}
        ).sort("chunk_index", 1)

        chunks = []
        for doc in cursor:
            # Extract slide info
            slides = doc.get("slides", [])
            slide_indices = [s["slide_index"] for s in slides]

            chunk_info = AudioChunkInfo(
                chunk_index=doc["chunk_index"],
                audio_id=str(doc["_id"]),
                audio_url=doc["audio_url"],
                slides=slides,
                slide_indices=slide_indices,
                duration=doc.get("duration", 0),
                file_size=doc.get("file_size", 0),
                rms=doc.get("rms"),
                status="ready" if doc.get("rms", 0) > 100 else "failed",
                created_at=doc.get("created_at", datetime.utcnow()),
            )
            chunks.append(chunk_info)

        return ListAudioChunksResponse(
            success=True,
            subtitle_id=subtitle_id,
            presentation_id=presentation_id,
            language=subtitle["language"],
            version=subtitle["version"],
            total_chunks=len(chunks),
            chunks=chunks,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list chunks: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list chunks: {str(e)}")


@router.post(
    "/presentations/{presentation_id}/audio/{subtitle_id}/chunks/{chunk_index}/regenerate",
    response_model=RegenerateChunkResponse,
    summary="Regenerate Specific Audio Chunk",
    description="""
    **Regenerate a specific failed audio chunk without redoing entire job**

    Use this when:
    - One or more chunks have silent/corrupt audio
    - You want to retry TTS generation for specific slides
    - Testing different voice configurations

    **Process:**
    1. Fetch chunk's slide data from subtitle document
    2. Generate new audio with TTS API
    3. Upload to R2 storage
    4. Update MongoDB with new audio URL and metadata

    **Note:** Does NOT automatically merge chunks. Use merge endpoint after.

    **Example workflow:**
    1. List chunks to find failed ones (RMS < 1000)
    2. Regenerate failed chunks one by one
    3. Merge all chunks into new audio file
    """,
)
async def regenerate_audio_chunk(
    presentation_id: str,
    subtitle_id: str,
    chunk_index: int,
    request: RegenerateChunkRequest,
    user: dict = Depends(get_current_user),
):
    """Regenerate a specific audio chunk"""
    try:
        # Verify user owns presentation
        doc_manager = DocumentManager(db)
        presentation = doc_manager.get_document(presentation_id, user["uid"])
        if not presentation:
            raise HTTPException(404, "Presentation not found")
        if presentation["userId"] != user["uid"]:
            raise HTTPException(403, "Not your presentation")

        # Get subtitle document
        subtitle = db.presentation_subtitles.find_one({"_id": ObjectId(subtitle_id)})
        if not subtitle:
            raise HTTPException(404, "Subtitle not found")

        # Get chunk document
        chunk_doc = db.presentation_audio.find_one(
            {"subtitle_id": subtitle_id, "chunk_index": chunk_index}
        )
        if not chunk_doc:
            raise HTTPException(404, f"Chunk {chunk_index} not found")

        # TODO: Implement chunk regeneration in service
        # For now, return info that regeneration needs to be implemented
        raise HTTPException(
            501,
            "Chunk regeneration not yet implemented. Please regenerate entire audio job.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to regenerate chunk: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to regenerate chunk: {str(e)}")


@router.post(
    "/presentations/{presentation_id}/audio/{subtitle_id}/merge",
    response_model=MergeChunksResponse,
    summary="Merge Audio Chunks into Single File",
    description="""
    **Merge all audio chunks into one complete audio file**

    Use this after:
    - Regenerating failed chunks
    - Verifying all chunks have valid audio
    - Ready to create final merged audio

    **Process:**
    1. Fetch all chunks in order (by chunk_index)
    2. Download audio files from R2
    3. Concatenate using pydub
    4. Upload merged file to R2
    5. Save as new audio document with slide_index=-1 (indicates merged file)
    6. Update subtitle document's audio_status

    **Note:** Creates NEW audio document. Original chunks remain unchanged.

    **Example:**
    After fixing chunk 2, call this to create final audio file for playback.
    """,
)
async def merge_audio_chunks(
    presentation_id: str,
    subtitle_id: str,
    user: dict = Depends(get_current_user),
):
    """Merge all audio chunks into single file"""
    try:
        # Verify user owns presentation
        doc_manager = DocumentManager(db)
        presentation = doc_manager.get_document(presentation_id, user["uid"])
        if not presentation:
            raise HTTPException(404, "Presentation not found")
        if presentation["userId"] != user["uid"]:
            raise HTTPException(403, "Not your presentation")

        # Get subtitle document
        subtitle = db.presentation_subtitles.find_one({"_id": ObjectId(subtitle_id)})
        if not subtitle:
            raise HTTPException(404, "Subtitle not found")

        # TODO: Implement manual merge in service
        # For now, return info that merge needs to be implemented
        raise HTTPException(
            501,
            "Manual chunk merging not yet implemented. Chunks are auto-merged during generation.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to merge chunks: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to merge chunks: {str(e)}")


# ============================================================
# PRESENTATION MODE ENDPOINTS (default version preferences)
# ============================================================


@router.put(
    "/presentations/{presentation_id}/preferences/{language}/default",
    response_model=SetDefaultVersionResponse,
    summary="Set Default Subtitle+Audio Version for Language",
    description="""
    **Set user's preferred default version for a language in presentation mode**

    When user has multiple subtitle versions for same language (e.g., version 1, 2, 3),
    they can choose which version to show by default in presentation mode.

    **Use cases:**
    - User generates version 2 but prefers version 1 narration style
    - Testing different subtitle iterations
    - Reverting to previous version after update

    **Storage:**
    - Saves to `presentation_preferences` collection
    - One document per presentation per user
    - Structure: {presentation_id, user_id, preferences: {vi: {subtitle_id, version}, en: {...}}}

    **Effect:**
    - GET /player-data will return this version instead of latest
    - Only affects this user's presentation mode view
    - Does not affect other users or public sharing

    **Validation:**
    - Subtitle must exist and belong to user
    - Subtitle must match the language parameter
    - Subtitle must belong to this presentation
    """,
)
async def set_default_version(
    presentation_id: str,
    language: str,
    request: SetDefaultVersionRequest,
    user: dict = Depends(get_current_user),
):
    """Set default subtitle+audio version for a language"""
    try:
        user_id = user["uid"]
        logger.info(
            f"Setting default version: presentation={presentation_id}, language={language}, subtitle={request.subtitle_id}"
        )

        # Verify subtitle exists and belongs to user
        subtitle = db.presentation_subtitles.find_one(
            {"_id": ObjectId(request.subtitle_id), "user_id": user_id}
        )
        if not subtitle:
            raise HTTPException(404, "Subtitle not found or not owned by you")

        # Verify subtitle belongs to this presentation
        if subtitle["presentation_id"] != presentation_id:
            raise HTTPException(400, "Subtitle does not belong to this presentation")

        # Verify language matches
        if subtitle["language"] != language:
            raise HTTPException(
                400,
                f"Subtitle language '{subtitle['language']}' does not match '{language}'",
            )

        version = subtitle["version"]

        # Upsert preference document
        preference_doc = {
            "presentation_id": presentation_id,
            "user_id": user_id,
            "updated_at": datetime.utcnow(),
        }

        # Build update: set preference for this language
        update = {
            "$set": {
                f"preferences.{language}.subtitle_id": request.subtitle_id,
                f"preferences.{language}.version": version,
                f"preferences.{language}.updated_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        }

        db.presentation_preferences.update_one(
            {"presentation_id": presentation_id, "user_id": user_id},
            update,
            upsert=True,
        )

        logger.info(
            f"✅ Set default: {language} → version {version} (subtitle {request.subtitle_id})"
        )

        return SetDefaultVersionResponse(
            message=f"Default version set for {language}",
            presentation_id=presentation_id,
            language=language,
            subtitle_id=request.subtitle_id,
            version=version,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to set default version: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to set default version: {str(e)}")


@router.get(
    "/presentations/{presentation_id}/player-data",
    response_model=GetPlayerDataResponse,
    summary="Get Complete Presentation Mode Data (All Languages)",
    description="""
    **Get subtitle + audio data for all languages in presentation mode**

    Returns complete data needed for presentation playback, including:
    - All available languages
    - For each language: subtitle slides + audio URL
    - Respects user's default version preferences
    - Falls back to latest version if no preference set

    **Version Selection Logic:**
    1. Check if user has set default version for this language → use that
    2. Otherwise → use latest version (highest version number)

    **Response includes:**
    - `languages`: Array of LanguagePlayerData (one per language)
      - `language`: Language code
      - `subtitle_id`: Which subtitle document
      - `version`: Which version
      - `is_default`: True if user explicitly set this as default
      - `is_latest`: True if this is latest version
      - `slides`: Subtitle content
      - `audio_url`: Merged audio file URL (if available)
      - `audio_status`: ready | processing | failed

    **Use cases:**
    - Load presentation player with all language options
    - Switch between languages in real-time
    - Show "Latest" or "Default" badge in UI

    **Performance:**
    - Single query per language
    - Populates audio URLs from presentation_audio
    - Returns only essential fields for playback
    """,
)
async def get_player_data(presentation_id: str, user: dict = Depends(get_current_user)):
    """Get complete presentation mode data for all languages"""
    try:
        user_id = user["uid"]
        logger.info(f"Getting player data: presentation={presentation_id}")

        # Get user preferences for this presentation
        preferences_doc = db.presentation_preferences.find_one(
            {"presentation_id": presentation_id, "user_id": user_id}
        )
        user_preferences = (
            preferences_doc.get("preferences", {}) if preferences_doc else {}
        )

        # Get all subtitles and normalize language codes
        # This handles old data with "en-US" and new data with "en"
        all_subtitles = list(
            db.presentation_subtitles.find(
                {"presentation_id": presentation_id, "user_id": user_id}
            ).sort("version", -1)
        )

        if not all_subtitles:
            return GetPlayerDataResponse(
                presentation_id=presentation_id,
                languages=[],
                available_languages=[],
                total_versions=0,
            )

        # Normalize language codes and group by normalized language
        # "en-US" → "en", "vi-VN" → "vi", etc.
        language_groups = {}
        for subtitle in all_subtitles:
            lang = subtitle["language"]
            normalized_lang = lang.split("-")[0] if "-" in lang else lang

            if normalized_lang not in language_groups:
                language_groups[normalized_lang] = []
            language_groups[normalized_lang].append(subtitle)

        available_languages = sorted(language_groups.keys())
        logger.info(
            f"   Found {len(available_languages)} normalized languages: {available_languages}"
        )

        # For each normalized language, get the appropriate version
        language_data_list = []
        total_versions = 0

        for normalized_lang in available_languages:
            subtitles_for_lang = language_groups[normalized_lang]

            # Sort by version descending to get latest
            subtitles_for_lang.sort(key=lambda x: x["version"], reverse=True)
            latest_subtitle = subtitles_for_lang[0]

            # Check if user has preference for this language (try both normalized and original)
            lang_pref = user_preferences.get(normalized_lang)
            if not lang_pref:
                # Try checking preferences with BCP-47 variants
                for variant in [
                    f"{normalized_lang}-US",
                    f"{normalized_lang}-{normalized_lang.upper()}",
                ]:
                    lang_pref = user_preferences.get(variant)
                    if lang_pref:
                        break

            if lang_pref and lang_pref.get("subtitle_id"):
                # User has set default version - use that
                subtitle_id = lang_pref["subtitle_id"]
                subtitle = db.presentation_subtitles.find_one(
                    {"_id": ObjectId(subtitle_id)}
                )
                if subtitle:
                    is_default = True
                    logger.info(
                        f"   Using user default for {normalized_lang}: version {subtitle.get('version')}"
                    )
                else:
                    # Preference invalid, fallback to latest
                    subtitle = latest_subtitle
                    is_default = False
                    logger.info(
                        f"   Preference invalid for {normalized_lang}, using latest: version {subtitle.get('version')}"
                    )
            else:
                # No preference - use latest version
                subtitle = latest_subtitle
                is_default = False
                logger.info(
                    f"   Using latest for {normalized_lang}: version {subtitle.get('version')}"
                )

            if not subtitle:
                logger.warning(f"   ⚠️ No subtitle found for {normalized_lang}")
                continue

            # Check if this is the latest version (already sorted, so first is latest)
            is_latest = str(subtitle["_id"]) == str(latest_subtitle["_id"])

            # Get audio info - fallback to older versions if latest has no audio
            audio_url = None
            audio_id = None
            slide_timestamps = None
            audio_status = subtitle.get("audio_status")

            # Try to get audio from selected subtitle first
            if subtitle.get("merged_audio_id"):
                audio_doc = db.presentation_audio.find_one(
                    {"_id": ObjectId(subtitle["merged_audio_id"])}
                )
                if audio_doc and audio_doc.get("audio_url"):
                    audio_url = audio_doc.get("audio_url")
                    audio_id = str(audio_doc["_id"])
                    slide_timestamps = audio_doc.get(
                        "slide_timestamps"
                    )  # ✅ Get timestamps
                    logger.info(f"      Audio found in version {subtitle['version']}")

            # If no audio in selected version, fallback to older versions
            if not audio_url:
                logger.info(
                    f"      No audio in version {subtitle['version']}, checking older versions..."
                )
                for fallback_subtitle in subtitles_for_lang:
                    # Skip if same as already checked
                    if str(fallback_subtitle["_id"]) == str(subtitle["_id"]):
                        continue

                    if fallback_subtitle.get("merged_audio_id"):
                        audio_doc = db.presentation_audio.find_one(
                            {"_id": ObjectId(fallback_subtitle["merged_audio_id"])}
                        )
                        if audio_doc and audio_doc.get("audio_url"):
                            audio_url = audio_doc.get("audio_url")
                            audio_id = str(audio_doc["_id"])
                            slide_timestamps = audio_doc.get(
                                "slide_timestamps"
                            )  # ✅ Get timestamps
                            audio_status = fallback_subtitle.get("audio_status")
                            logger.info(
                                f"      ✅ Fallback: Using audio from version {fallback_subtitle['version']}"
                            )
                            break

                if not audio_url:
                    logger.info(
                        f"      ⚠️ No audio found in any version for {normalized_lang}"
                    )

            # Build language data (use normalized language code)
            lang_data = LanguagePlayerData(
                language=normalized_lang,  # Use normalized code (en, vi, zh)
                subtitle_id=str(subtitle["_id"]),
                version=subtitle["version"],
                is_default=is_default,
                is_latest=is_latest,
                slides=subtitle.get("slides", []),
                total_duration=subtitle.get("total_duration", 0),
                audio_url=audio_url,
                audio_id=audio_id,
                audio_status=audio_status,
                slide_timestamps=slide_timestamps,  # ✅ Include timestamps
                created_at=subtitle.get("created_at", datetime.utcnow()),
                updated_at=subtitle.get("updated_at", datetime.utcnow()),
            )
            language_data_list.append(lang_data)
            total_versions += 1

        logger.info(
            f"✅ Player data: {len(language_data_list)} languages, {total_versions} total versions"
        )

        return GetPlayerDataResponse(
            presentation_id=presentation_id,
            languages=language_data_list,
            available_languages=available_languages,
            total_versions=total_versions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get player data: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get player data: {str(e)}")


# ============================================================================
# VIDEO EXPORT ENDPOINTS (Phase 1)
# ============================================================================


@router.post(
    "/presentations/{presentation_id}/export/video",
    summary="Export Presentation to MP4 Video",
    description="""
    **Export presentation to MP4 video file**

    Creates a background job to generate video from presentation slides with narration audio.
    Video is created as static slideshow with fade transitions (optimized file size: 50-100 MB).

    **Process:**
    1. Captures 1 screenshot per slide (Puppeteer)
    2. Creates slideshow with slide durations from audio timestamps (FFmpeg)
    3. Merges with audio narration
    4. Uploads to S3/R2 storage

    **File Size:** ~76 MB for 15 min (medium quality)
    **Format:** MP4 (H.264 video + AAC audio)
    **Resolution:** 1080p default (configurable)

    Returns job_id for status polling.

    **Authentication:** Required (must be system user). If presentation is public, any authenticated user can export.
    """,
)
async def export_presentation_video(
    presentation_id: str,
    request: VideoExportRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create video export job"""
    try:
        from src.models.ai_queue_tasks import VideoExportTask
        from src.queue.queue_manager import set_job_status
        from src.queue.queue_dependencies import get_video_export_queue
        import secrets

        user_id = current_user["uid"]

        logger.info(f"🎬 Creating video export job for presentation {presentation_id}")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Language: {request.language}")
        logger.info(f"   Export Mode: {request.export_mode}")
        logger.info(f"   Quality: {request.quality}")
        logger.info(f"   Resolution: {request.resolution}")

        # 1. Verify presentation exists
        presentation = db.documents.find_one({"document_id": presentation_id})
        if not presentation:
            raise HTTPException(404, "Presentation not found")

        # 2. Check sharing settings
        sharing_config = db.presentation_sharing_config.find_one(
            {"presentation_id": presentation_id}
        )

        is_public = sharing_config and sharing_config.get("is_public", False)
        is_owner = presentation.get("user_id") == user_id

        # Check if download is allowed (default: allow if no config)
        allow_download = True
        if sharing_config and "sharing_settings" in sharing_config:
            allow_download = sharing_config["sharing_settings"].get(
                "allow_download", True
            )

        # 3. Authorization check
        if not is_owner:
            # Not owner - check if public and download allowed
            if not is_public:
                raise HTTPException(
                    403, "Presentation is private. Only owner can export."
                )
            if not allow_download:
                raise HTTPException(
                    403, "Video download is not enabled for this presentation"
                )

            logger.info(
                f"   Public access: User {user_id} exporting public presentation"
            )

        # Verify document type
        if presentation.get("document_type") != "slide":
            raise HTTPException(400, "Document is not a slide presentation")

        # 4. Rate limiting: 3 minutes between exports per user
        from datetime import timedelta

        rate_limit_key = f"video_export_rate_limit:{user_id}"

        # Check Redis for last export time
        queue = await get_video_export_queue()
        last_export_time = await queue.redis_client.get(rate_limit_key)

        if last_export_time:
            # Calculate time since last export
            last_time = datetime.fromisoformat(last_export_time.decode())
            time_diff = datetime.utcnow() - last_time
            wait_seconds = 180 - int(
                time_diff.total_seconds()
            )  # 3 minutes = 180 seconds

            if wait_seconds > 0:
                raise HTTPException(
                    429,
                    f"Rate limit exceeded. Please wait {wait_seconds} seconds before creating another export.",
                )

        # 5. Check if narration exists for language
        subtitle = db.presentation_subtitles.find_one(
            {"presentation_id": presentation_id, "language": request.language},
            sort=[("version", -1)],  # Latest version
        )

        if not subtitle:
            raise HTTPException(
                404,
                f"No narration found for language '{request.language}'. Generate subtitles first.",
            )

        # Check if audio exists
        if not subtitle.get("merged_audio_id"):
            raise HTTPException(
                400,
                f"No audio found for language '{request.language}'. Generate audio first.",
            )

        # Verify audio URL exists
        audio = db.presentation_audio.find_one(
            {"_id": ObjectId(subtitle["merged_audio_id"])}
        )
        if not audio or not audio.get("audio_url"):
            raise HTTPException(400, "Audio file not found. Please regenerate audio.")

        # 3. Create export settings
        settings = VideoExportSettings.from_request(request)

        # 4. Calculate estimated file size based on mode
        audio_duration = audio.get("audio_metadata", {}).get(
            "duration_seconds", 900
        )  # Default 15 min
        estimated_size_mb = 48  # Default for optimized mode

        if request.export_mode == "optimized":
            # Static slideshow: ~48 MB for 15 min
            # Formula: (duration_minutes × 0.3 Mbps / 8) + (audio_minutes × 128 kbps / 8 / 1024)
            video_mb = (audio_duration / 60) * 0.3 / 8 * 1000
            audio_mb = (audio_duration / 60) * 128 / 8 / 1024 * 1000
            estimated_size_mb = int(video_mb + audio_mb)
        elif request.export_mode == "animated":
            # 5s animation per slide + freeze: ~61 MB for 15 min
            # Rough estimate based on slide count
            slide_count = len(presentation.get("slide_backgrounds", []))
            animation_seconds = slide_count * 5  # 5s per slide
            static_seconds = audio_duration - animation_seconds
            video_mb = (animation_seconds / 60) * 2 / 8 * 1000 + (
                static_seconds / 60
            ) * 0.1 / 8 * 1000
            audio_mb = (audio_duration / 60) * 128 / 8 / 1024 * 1000
            estimated_size_mb = int(video_mb + audio_mb)

        # 5. Estimate generation time
        slide_count = len(presentation.get("slide_backgrounds", []))
        if request.export_mode == "optimized":
            # 2s per slide + encoding
            estimated_time_seconds = (slide_count * 2) + 60
        else:
            # 14s per slide + encoding
            estimated_time_seconds = (slide_count * 14) + 60

        logger.info(f"   📊 Estimated size: {estimated_size_mb} MB")
        logger.info(f"   ⏱️  Estimated time: {estimated_time_seconds}s")

        # 6. Create job ID
        job_id = f"export_{secrets.token_urlsafe(12)}"

        # 7. Create job in MongoDB
        job_doc = {
            "_id": job_id,
            "job_id": job_id,
            "presentation_id": presentation_id,
            "user_id": user_id,
            "language": request.language,
            "export_mode": request.export_mode,
            "settings": settings.model_dump(),
            "estimated_size_mb": estimated_size_mb,
            "estimated_time_seconds": estimated_time_seconds,
            "status": "pending",
            "progress": 0,
            "current_phase": None,
            "output_url": None,
            "file_size": None,
            "duration": None,
            "error_message": None,
            "retry_count": 0,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "expires_at": None,  # Will be set when completed (7 days)
        }

        db.video_export_jobs.insert_one(job_doc)
        logger.info(f"✅ Created MongoDB job: {job_id}")

        # 8. Create job in Redis (for real-time polling)
        queue = await get_video_export_queue()

        await set_job_status(
            redis_client=queue.redis_client,
            job_id=job_id,
            status="pending",
            user_id=user_id,
            presentation_id=presentation_id,
            language=request.language,
            export_mode=request.export_mode,
            estimated_size_mb=estimated_size_mb,
            estimated_time_seconds=estimated_time_seconds,
            created_at=datetime.utcnow().isoformat(),
        )

        # 9. Enqueue task
        task = VideoExportTask(
            task_id=job_id,
            job_id=job_id,
            presentation_id=presentation_id,
            user_id=user_id,
            language=request.language,
            subtitle_id=str(subtitle["_id"]),
            audio_id=subtitle["merged_audio_id"],
            export_mode=request.export_mode,
            settings=settings.model_dump(),
        )

        await queue.enqueue_generic_task(task)
        logger.info(f"✅ Enqueued video export job: {job_id}")

        # 10. Set rate limit timestamp (3 minutes TTL)
        await queue.redis_client.setex(
            rate_limit_key, 180, datetime.utcnow().isoformat()  # 3 minutes in seconds
        )

        return VideoExportCreateResponse(
            job_id=job_id,
            status=ExportStatus.PENDING,
            message="Export job created successfully. Poll /api/export-jobs/{job_id} for status.",
            polling_url=f"/api/export-jobs/{job_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create export job: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to create export job: {str(e)}")


@router.get(
    "/export-jobs/{job_id}",
    summary="Get Video Export Job Status",
    description="""
    **Poll for video export job status**

    Returns real-time status from Redis (24h TTL) or MongoDB backup.

    **Status Values:**
    - `pending`: Waiting in queue
    - `processing`: Video generation in progress
    - `completed`: Video ready for download
    - `failed`: Export failed (see error field)

    **When completed:** Response includes `download_url` (24h expiration)
    """,
)
async def get_export_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get video export job status"""
    try:
        from src.models.video_export_models import VideoExportJobResponse, ExportStatus
        from src.queue.queue_manager import get_job_status
        from src.queue.queue_dependencies import get_video_export_queue

        user_id = current_user["uid"]

        # 1. Check Redis first (real-time status)
        queue = await get_video_export_queue()
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            # Fallback to MongoDB
            job_doc = db.video_export_jobs.find_one({"_id": job_id})

            if not job_doc:
                raise HTTPException(404, "Export job not found")

            # Convert MongoDB doc to dict
            job = {
                "job_id": job_doc["job_id"],
                "status": job_doc["status"],
                "progress": job_doc.get("progress", 0),
                "current_phase": job_doc.get("current_phase"),
                "user_id": job_doc["user_id"],
                "presentation_id": job_doc["presentation_id"],
                "language": job_doc["language"],
                "export_mode": job_doc.get("export_mode"),
                "estimated_size_mb": job_doc.get("estimated_size_mb"),
                "output_url": job_doc.get("output_url"),
                "library_video_id": job_doc.get("library_video_id"),
                "file_size": job_doc.get("file_size"),
                "duration": job_doc.get("duration"),
                "error": job_doc.get("error_message"),
                "created_at": job_doc["created_at"],
            }

        # 2. Verify ownership
        if job.get("user_id") != user_id:
            raise HTTPException(403, "Access denied")

        # 3. Calculate estimated time remaining
        estimated_time = None
        if job["status"] == "processing":
            progress = job.get("progress", 0)
            if progress > 0:
                # Use actual estimated time from job doc
                total_time = job.get("estimated_time_seconds", 60)
                elapsed_ratio = progress / 100
                elapsed = total_time * elapsed_ratio
                remaining = total_time - elapsed
                estimated_time = int(remaining)

        # 4. Return response
        return VideoExportJobResponse(
            job_id=job["job_id"],
            status=job["status"],
            progress=job.get("progress", 0),
            current_phase=job.get("current_phase"),
            download_url=job.get("output_url"),
            library_video_id=job.get("library_video_id"),
            file_size=job.get("file_size"),
            duration=job.get("duration"),
            error=job.get("error"),
            presentation_id=job["presentation_id"],
            language=job["language"],
            export_mode=job.get("export_mode"),
            estimated_size_mb=job.get("estimated_size_mb"),
            created_at=job["created_at"],
            estimated_time_remaining=estimated_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get job status: {str(e)}")
