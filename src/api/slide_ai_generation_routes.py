"""
Slide AI Generation Routes
API endpoints for AI-powered slide generation (2-step flow)
"""

import logging
import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from src.middleware.auth import verify_firebase_token as require_auth
from src.models.slide_ai_generation_models import (
    AnalyzeSlideRequest,
    AnalyzeSlideResponse,
    SlideOutlineItem,
    CreateSlideRequest,
    CreateSlideResponse,
    SlideGenerationStatus,
    SlideImageAttachment,
)
from src.services.slide_ai_generation_service import get_slide_ai_service
from src.services.points_service import get_points_service
from src.database.mongodb_service import get_mongodb_service
from src.services.document_manager import DocumentManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/slides/ai-generate", tags=["Slide AI Generation"])


# ============ STATUS POLLING ============


@router.get("/status/{document_id}", response_model=SlideGenerationStatus)
async def get_slide_generation_status(
    document_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    **Poll AI slide generation status**

    Returns current status of AI slide generation:
    - status: 'pending' | 'processing' | 'completed' | 'failed'
    - progress_percent: 0-100
    - error_message: If failed

    Frontend should poll this endpoint every 2-3 seconds until status is 'completed' or 'failed'.
    """
    try:
        mongo_service = get_mongodb_service()
        doc_manager = DocumentManager()

        # Get document (validates user owns it)
        document = doc_manager.get_document(document_id, user_info["uid"])

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if this is an AI-generated slide
        if document.get("document_type") != "slide":
            raise HTTPException(status_code=400, detail="Not a slide document")

        if "ai_analysis_id" not in document:
            raise HTTPException(
                status_code=400,
                detail="Not an AI-generated slide. This endpoint is only for AI slide generation status.",
            )

        # Return status
        return SlideGenerationStatus(
            document_id=document_id,
            status=document.get("ai_generation_status", "pending"),
            progress_percent=document.get("ai_progress_percent", 0),
            error_message=document.get("ai_error_message"),
            num_slides=document.get("ai_num_slides"),
            title=document.get("title"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get slide status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ STEP 1: ANALYSIS ============


@router.post("/analyze", response_model=AnalyzeSlideResponse)
async def analyze_slide_requirements(
    request: AnalyzeSlideRequest,
    user_info: dict = Depends(require_auth),
):
    """
    **STEP 1: Analyze slide requirements and generate structured outline**

    **Cost:** 2 points

    **Flow:**
    1. User provides: title, goal, type, slide range, language, content query
    2. AI (Gemini 2.0 Flash) analyzes and creates structured outline
    3. Returns outline with:
       - Optimal slide count (within range)
       - Title and content points for each slide
       - Image suggestions (user can add image URLs)
       - Visual element suggestions

    **User can then:**
    - Review the outline
    - Add image URLs to specific slides
    - Regenerate with new query (keeps params)
    - Proceed to Step 2 to generate HTML

    **Returns:**
    - analysis_id: Use this for Step 2
    - slides_outline: Review and optionally add image URLs
    """
    try:
        logger.info(f"📝 Slide analysis request from user {user_info['uid']}")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Type: {request.slide_type}")
        logger.info(
            f"   Range: {request.num_slides_range.min}-{request.num_slides_range.max}"
        )
        logger.info(f"   Language: {request.language}")

        # 1. Check points (2 points for analysis)
        points_service = get_points_service()
        points_available = await points_service.check_points(user_info["uid"])

        if points_available < 2:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để phân tích slide. Cần: 2, Còn: {points_available}",
                    "points_needed": 2,
                    "points_available": points_available,
                },
            )

        # 2. Call AI for analysis
        ai_service = get_slide_ai_service()
        start_time = datetime.now()

        analysis_result = await ai_service.analyze_slide_requirements(
            title=request.title,
            target_goal=request.target_goal,
            slide_type=request.slide_type,
            num_slides_range=request.num_slides_range.dict(),
            language=request.language,
            user_query=request.user_query,
        )

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        # 3. Save analysis to database
        mongo_service = get_mongodb_service()
        collection = mongo_service.db["slide_analyses"]

        # Convert slides to SlideOutlineItem models
        slides_outline = []
        for slide_data in analysis_result["slides"]:
            slides_outline.append(
                SlideOutlineItem(
                    slide_number=slide_data["slide_number"],
                    title=slide_data["title"],
                    content_points=slide_data.get("content_points", []),
                    suggested_visuals=slide_data.get("suggested_visuals", []),
                    image_suggestion=slide_data.get("image_suggestion"),
                    estimated_duration=slide_data.get("estimated_duration"),
                    image_url=None,  # User will add later
                )
            )

        analysis_doc = {
            "user_id": user_info["uid"],
            "title": request.title,
            "target_goal": request.target_goal,
            "slide_type": request.slide_type,
            "num_slides_range": request.num_slides_range.dict(),
            "language": request.language,
            "user_query": request.user_query,
            "presentation_summary": analysis_result.get("presentation_summary", ""),
            "num_slides": analysis_result["num_slides"],
            "slides_outline": [slide.dict() for slide in slides_outline],
            "status": "completed",
            "processing_time_ms": processing_time,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(analysis_doc)
        analysis_id = str(result.inserted_id)

        logger.info(f"✅ Analysis saved: {analysis_id} ({len(slides_outline)} slides)")

        # 4. Deduct points (only after success)
        await points_service.deduct_points(
            user_id=user_info["uid"],
            points=2,
            reason="Slide AI Analysis",
            metadata={
                "analysis_id": analysis_id,
                "num_slides": len(slides_outline),
                "slide_type": request.slide_type,
            },
        )

        logger.info(f"💰 Deducted 2 points from user {user_info['uid']}")

        # 5. Return response
        return AnalyzeSlideResponse(
            success=True,
            analysis_id=analysis_id,
            presentation_summary=analysis_result.get("presentation_summary", ""),
            num_slides=len(slides_outline),
            slides_outline=slides_outline,
            processing_time_ms=processing_time,
            points_deducted=2,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [BG] Slide generation failed: {document_id}, error: {e}")

        # Mark as failed
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "ai_generation_status": "failed",
                    "ai_error_message": str(e),
                    "updated_at": datetime.now(),
                }
            },
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ============ STEP 2: HTML GENERATION ============


@router.post("/create", response_model=CreateSlideResponse)
async def create_slides_from_analysis(
    request: CreateSlideRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_auth),
):
    """
    **STEP 2: Generate HTML content for slides (Async Background Job)**

    **Cost:** Variable based on slide count
    - 1-15 slides: 2 points (1 AI batch)
    - 16-30 slides: 4 points (2 AI batches)
    - 31-45 slides: 6 points (3 AI batches)

    **Formula:** Math.ceil(num_slides / 15) * 2 points

    **Flow:**
    1. Get analysis from Step 1
    2. User can optionally provide:
       - Logo URL (appears on all slides)
       - Creator name
       - Image URLs for specific slides (from outline suggestions)
       - Additional generation instructions
    3. Create document record with status='pending'
    4. Start async background job to generate HTML
    5. Return immediately with document_id
    6. Frontend polls `/api/documents/{id}/status` for progress

    **Processing:**
    - Slides generated in batches (15 per AI call)
    - Progress updated incrementally (0-100%)
    - Timeout: 15 minutes
    - Points deducted only after successful completion

    **Returns:**
    - document_id: New slide document (use for polling)
    - status: Always 'pending' initially
    - poll_url: URL to check generation status
    """
    try:
        logger.info(f"🎨 Slide creation request from user {user_info['uid']}")
        logger.info(f"   Analysis ID: {request.analysis_id}")
        logger.info(f"   Logo URL: {request.logo_url or '(none)'}")
        logger.info(f"   Slide images: {len(request.slide_images or [])} provided")

        # 1. Get analysis from database
        mongo_service = get_mongodb_service()
        analysis = mongo_service.db["slide_analyses"].find_one(
            {"_id": ObjectId(request.analysis_id), "user_id": user_info["uid"]}
        )

        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Analysis not found. Please run Step 1 first.",
            )

        # 2. Calculate points needed
        num_slides = analysis["num_slides"]
        batches_needed = (num_slides + 14) // 15  # Round up
        points_needed = batches_needed * 2

        logger.info(
            f"   Slides: {num_slides}, Batches: {batches_needed}, Points: {points_needed}"
        )

        # 3. Check points
        points_service = get_points_service()
        points_available = await points_service.check_points(user_info["uid"])

        if points_available < points_needed:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để tạo {num_slides} slides. Cần: {points_needed}, Còn: {points_available}",
                    "points_needed": points_needed,
                    "points_available": points_available,
                },
            )

        # 4. Validate creator_name if provided
        if request.creator_name:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            validate_creator_name(request.creator_name, user_email, user_info["uid"])

        # 5. Create slide document using DocumentManager (compatible with existing system)
        doc_manager = DocumentManager()
        document_id = doc_manager.create_document(
            user_id=user_info["uid"],
            title=analysis["title"],
            content_html="",  # Will be generated by AI
            content_text=analysis.get("presentation_summary", ""),
            source_type="created",
            document_type="slide",
        )

        # 6. Add AI generation metadata to document (stored in separate fields)
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    # AI Generation metadata
                    "ai_analysis_id": request.analysis_id,
                    "ai_slide_type": analysis["slide_type"],
                    "ai_language": analysis["language"],
                    "ai_num_slides": num_slides,
                    "ai_batches_needed": batches_needed,
                    "ai_points_needed": points_needed,
                    # Generation status
                    "ai_generation_status": "pending",
                    "ai_progress_percent": 0,
                    "ai_error_message": None,
                    # Slide-specific fields
                    "slide_elements": [],  # Empty initially (user adds overlay elements later)
                    "slide_backgrounds": [],  # Will be generated with defaults
                    # Creator info (optional)
                    "creator_name": request.creator_name or user_info.get("email", ""),
                    "logo_url": request.logo_url,
                }
            },
        )

        logger.info(f"✅ Slide document created: {document_id} (status=pending)")

        # 6. Prepare slide images dict
        slide_images_dict = {}
        if request.slide_images:
            for img in request.slide_images:
                slide_images_dict[img.slide_number] = img.image_url

        # 7. Start background job (non-blocking)
        background_tasks.add_task(
            generate_slide_html_background,
            document_id=document_id,
            analysis=analysis,
            logo_url=request.logo_url,
            slide_images=slide_images_dict,
            user_query=request.user_query,
            points_needed=points_needed,
            user_id=user_info["uid"],
        )

        logger.info(f"🚀 Background job queued for slide generation: {document_id}")

        # 8. Return immediately
        return CreateSlideResponse(
            success=True,
            document_id=document_id,
            status="pending",
            title=analysis["title"],
            num_slides=num_slides,
            batches_needed=batches_needed,
            points_needed=points_needed,
            created_at=datetime.now().isoformat(),
            message=f"Slide creation started. AI is generating HTML for {num_slides} slides in {batches_needed} batch(es)...",
            poll_url=f"/api/slides/ai-generate/status/{document_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Slide creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ BACKGROUND JOB ============


async def generate_slide_html_background(
    document_id: str,
    analysis: dict,
    logo_url: Optional[str],
    slide_images: Dict[int, str],
    user_query: Optional[str],
    points_needed: int,
    user_id: str,
):
    """
    Background task to generate slide HTML in batches.

    Updates document status as it progresses:
    - pending → processing → completed (or failed)
    - Updates ai_progress_percent (0-100%)
    - Deducts points only after successful completion
    """
    mongo_service = get_mongodb_service()
    ai_service = get_slide_ai_service()
    doc_manager = DocumentManager()

    try:
        logger.info(f"🎨 [BG] Starting slide HTML generation: {document_id}")

        # Update status to processing
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "ai_generation_status": "processing",
                    "updated_at": datetime.now(),
                }
            },
        )

        # Get slides from analysis
        slides_outline = analysis["slides_outline"]
        num_slides = len(slides_outline)
        total_batches = (num_slides + 14) // 15  # Max 15 slides per batch

        logger.info(
            f"📊 [BG] Generating {num_slides} slides in {total_batches} batch(es)"
        )

        # Generate HTML in batches
        all_slides_html = []
        for i in range(total_batches):
            start_idx = i * 15
            end_idx = min((i + 1) * 15, num_slides)
            batch_slides = slides_outline[start_idx:end_idx]

            logger.info(
                f"🔄 [BG] Batch {i+1}/{total_batches}: slides {start_idx+1}-{end_idx}"
            )

            # Call AI to generate HTML for this batch
            batch_html = await ai_service.generate_slide_html_batch(
                title=analysis["title"],
                slide_type=analysis["slide_type"],
                language=analysis["language"],
                slides_outline=batch_slides,
                slide_images=slide_images,
                logo_url=logo_url,
                user_query=user_query,
                batch_number=i + 1,
                total_batches=total_batches,
            )

            all_slides_html.extend(batch_html)

            # Update progress
            progress = int((i + 1) / total_batches * 100)
            mongo_service.db["documents"].update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "ai_progress_percent": progress,
                        "updated_at": datetime.now(),
                    }
                },
            )

            logger.info(f"✅ [BG] Batch {i+1}/{total_batches} completed ({progress}%)")

            # Small delay between batches
            if i < total_batches - 1:
                await asyncio.sleep(0.5)

        # Combine all slides into final HTML
        final_html = "\n\n".join(all_slides_html)

        # Create default backgrounds
        slide_backgrounds = _create_default_backgrounds(
            num_slides, analysis["slide_type"]
        )

        logger.info(f"✅ [BG] All slides generated. Total: {num_slides}")

        # Save final HTML to document using DocumentManager (compatible update)
        doc_manager.update_document(
            document_id=document_id,
            user_id=user_id,
            title=analysis["title"],
            content_html=final_html,
            content_text=analysis.get("presentation_summary", ""),
            slide_backgrounds=slide_backgrounds,
        )

        # Update AI generation status
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "ai_generation_status": "completed",
                    "ai_progress_percent": 100,
                    "updated_at": datetime.now(),
                }
            },
        )

        # Deduct points (only after successful completion)
        points_service = get_points_service()
        await points_service.deduct_points(
            user_id=user_id,
            points=points_needed,
            description=f"AI Slide Generation: {num_slides} slides ({total_batches} batches)",
        )

        logger.info(
            f"✅ [BG] Slide generation completed: {document_id}, deducted {points_needed} points"
        )

    except Exception as e:
        logger.error(f"❌ [BG] Slide generation failed: {document_id}, error: {e}")

        # Mark as failed
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "ai_generation_status": "failed",
                    "ai_error_message": str(e),
                    "updated_at": datetime.now(),
                }
            },
        )


# ============ HELPER FUNCTIONS ============


def _create_default_backgrounds(num_slides: int, slide_type: str) -> List[dict]:
    """Create default gradient backgrounds for slides"""

    # Color schemes based on slide type
    academy_gradients = [
        {
            "type": "gradient",
            "gradient": {
                "type": "linear",
                "colors": ["#667eea", "#764ba2"],
                "angle": 135,
            },
        },
        {
            "type": "gradient",
            "gradient": {
                "type": "linear",
                "colors": ["#f093fb", "#f5576c"],
                "angle": 135,
            },
        },
        {
            "type": "gradient",
            "gradient": {
                "type": "linear",
                "colors": ["#4facfe", "#00f2fe"],
                "angle": 135,
            },
        },
        {"type": "color", "value": "#ffffff"},
    ]

    business_gradients = [
        {
            "type": "gradient",
            "gradient": {
                "type": "linear",
                "colors": ["#0f2027", "#203a43", "#2c5364"],
                "angle": 135,
            },
        },
        {
            "type": "gradient",
            "gradient": {
                "type": "linear",
                "colors": ["#434343", "#000000"],
                "angle": 135,
            },
        },
        {
            "type": "gradient",
            "gradient": {
                "type": "linear",
                "colors": ["#1e3c72", "#2a5298"],
                "angle": 135,
            },
        },
        {"type": "color", "value": "#ffffff"},
    ]

    gradients = academy_gradients if slide_type == "academy" else business_gradients

    backgrounds = []
    for i in range(num_slides):
        backgrounds.append(
            {"slideIndex": i, "background": gradients[i % len(gradients)]}
        )

    return backgrounds
