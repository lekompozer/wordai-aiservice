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
    AnalyzeSlideFromPdfRequest,
    AnalyzeSlideResponse,
    SlideOutlineItem,
    CreateSlideRequest,
    CreateSlideResponse,
    SlideGenerationStatus,
    SlideImageAttachment,
    CreateBasicSlideRequest,
    CreateBasicSlideResponse,
    UpdateOutlineRequest,
    UpdateOutlineResponse,
)
from src.services.slide_ai_generation_service import get_slide_ai_service
from src.services.points_service import get_points_service
from src.services.online_test_utils import get_mongodb_service
from src.services.document_manager import DocumentManager
from src.queue.queue_manager import get_job_status
from src.queue.queue_dependencies import get_slide_generation_queue
from src.queue.queue_dependencies import get_slide_generation_queue
from src.models.ai_queue_tasks import SlideGenerationTask

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

    Returns current status of AI slide generation FROM REDIS:
    - status: 'pending' | 'processing' | 'completed' | 'failed'
    - progress_percent: 0-100
    - error_message: If failed

    Frontend should poll this endpoint every 2-3 seconds until status is 'completed' or 'failed'.

    **IMPORTANT:** Status is tracked in Redis, not MongoDB. MongoDB only stores final content.
    """
    try:
        # Get Redis queue
        queue = await get_slide_generation_queue()

        # Query Redis for job status (NOT MongoDB)
        job = await get_job_status(queue.redis_client, document_id)

        if not job:
            # Job not found in Redis - might be very old or never created
            raise HTTPException(
                status_code=404,
                detail="Job status not found in Redis. It may have expired (24h TTL) or was never created.",
            )

        # Validate user owns this job
        if job.get("user_id") != user_info["uid"]:
            raise HTTPException(
                status_code=403, detail="Not authorized to view this job"
            )

        # Extract status from Redis
        status = job.get("status", "pending")
        progress = job.get("progress_percent", 0)
        num_slides = job.get("total_slides") or job.get("slides_generated")
        error_msg = job.get("error")
        slides_generated = job.get("slides_generated")
        slides_expected = job.get("slides_expected")

        # Build status message
        if status == "pending":
            message = "Slide generation is starting..."
        elif status == "processing":
            batches_done = job.get("batches_completed", 0)
            total_batches = job.get("total_batches", 1)
            message = f"Generating slides... ({progress}% complete, batch {batches_done}/{total_batches})"
        elif status == "completed":
            message = f"Successfully generated {num_slides} slides!"
        elif status == "partial":
            message = f"Generated {slides_generated}/{slides_expected} slides. You can use what's available or retry for complete presentation."
        elif status == "failed":
            message = f"Slide generation failed: {error_msg or 'Unknown error'}"
        else:
            message = "Unknown status"

        # Return status from Redis
        return SlideGenerationStatus(
            document_id=document_id,
            status=status,
            progress_percent=int(progress) if progress else 0,
            error_message=error_msg,
            num_slides=num_slides,
            title=job.get("title"),  # May not be in Redis
            created_at=job.get("created_at", datetime.utcnow().isoformat()),
            updated_at=job.get("updated_at", datetime.utcnow().isoformat()),
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get slide status from Redis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ RETRY: GET OUTLINE ============


@router.get("/documents/{document_id}/outline")
async def get_slide_outline(
    document_id: str,
    user_info: dict = Depends(require_auth),
):
    """
    **Get saved slide outline for retry**

    When slide generation fails partially, the outline is saved in MongoDB.
    Frontend can use this endpoint to:
    1. Check if outline exists for retry
    2. Display partial progress (e.g., "13/23 slides generated")
    3. Provide retry button to regenerate from saved outline

    **Returns:**
    - slides_outline: Array of slide outline objects
    - slides_generated: Number of slides currently saved
    - slides_expected: Total slides expected from outline
    - can_retry: Boolean flag
    """
    try:
        # Get document from MongoDB
        db_service = get_mongodb_service()
        doc_manager = DocumentManager(db_service.db)

        doc = doc_manager.documents.find_one(
            {
                "document_id": document_id,
                "user_id": user_info["uid"],
                "is_deleted": False,
            }
        )

        if not doc:
            raise HTTPException(
                status_code=404, detail="Document not found or you don't have access"
            )

        # Check if outline exists
        slides_outline = doc.get("slides_outline")
        if not slides_outline:
            raise HTTPException(
                status_code=404,
                detail="No outline found for this document. It may have been created before outline saving was implemented.",
            )

        # Count current slides in content_html
        content_html = doc.get("content_html", "")
        import re

        slide_matches = re.findall(r'<div class="slide"', content_html)
        slides_generated = len(slide_matches)
        slides_expected = len(slides_outline)

        logger.info(
            f"📋 Outline retrieved: document={document_id}, "
            f"slides={slides_generated}/{slides_expected}"
        )

        return {
            "document_id": document_id,
            "slides_outline": slides_outline,
            "slides_generated": slides_generated,
            "slides_expected": slides_expected,
            "can_retry": slides_generated < slides_expected,
            "title": doc.get("title", "Untitled Presentation"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get outline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/documents/{document_id}/outline", response_model=UpdateOutlineResponse)
async def update_slide_outline(
    document_id: str,
    request: UpdateOutlineRequest,
    user_info: dict = Depends(require_auth),
):
    """
    **Update slide outline (for editing before retry)**

    Allows user to edit the saved outline before regenerating slides.

    **Validations:**
    - User must own the document
    - Cannot edit if generation is currently in progress
    - Must maintain same slide count (can't add/remove slides)
    - Slide numbers must be sequential (1, 2, 3, ...)

    **Use Cases:**
    1. Fix outline after partial generation failure
    2. Improve content before retry
    3. Adjust slide structure

    **Returns:**
    - success: true/false
    - slides_count: Number of slides in updated outline
    - updated_at: Timestamp
    """
    try:
        # Get document from MongoDB
        db_service = get_mongodb_service()
        doc_manager = DocumentManager(db_service.db)

        doc = doc_manager.documents.find_one({
            "document_id": document_id,
            "user_id": user_info["uid"],
            "is_deleted": False
        })

        if not doc:
            raise HTTPException(
                status_code=404,
                detail="Document not found or you don't have access"
            )

        # Check if outline exists
        current_outline = doc.get("slides_outline")
        if not current_outline:
            raise HTTPException(
                status_code=404,
                detail="No outline found for this document"
            )

        # Check if generation is in progress
        queue = await get_slide_generation_queue()
        job = await get_job_status(queue.redis_client, document_id)

        if job and job.get("status") == "processing":
            raise HTTPException(
                status_code=400,
                detail="Cannot edit outline while generation is in progress. Please wait for completion or cancellation."
            )

        # Validate slide count matches
        new_outline = [slide.dict() for slide in request.slides_outline]

        if len(new_outline) != len(current_outline):
            raise HTTPException(
                status_code=400,
                detail=f"Slide count mismatch. Current: {len(current_outline)}, New: {len(new_outline)}. Cannot add or remove slides."
            )

        # Update outline in MongoDB
        now = datetime.utcnow()
        result = doc_manager.documents.update_one(
            {"document_id": document_id, "user_id": user_info["uid"]},
            {
                "$set": {
                    "slides_outline": new_outline,
                    "outline_updated_at": now,
                    "last_saved_at": now
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update outline"
            )

        logger.info(
            f"✅ Outline updated: document={document_id}, "
            f"user={user_info['uid']}, slides={len(new_outline)}"
        )

        return UpdateOutlineResponse(
            success=True,
            document_id=document_id,
            slides_count=len(new_outline),
            updated_at=now.isoformat(),
            message=f"Outline updated successfully ({len(new_outline)} slides)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update outline: {e}", exc_info=True)
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
        points_check = await points_service.check_sufficient_points(
            user_id=user_info["uid"], points_needed=2, service="slide_ai_analysis"
        )

        if not points_check["has_points"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để phân tích slide. Cần: 2, Còn: {points_check['points_available']}",
                    "points_needed": 2,
                    "points_available": points_check["points_available"],
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
            amount=2,
            service="slide_ai_analysis",
            resource_id=analysis_id,
            description=f"Slide AI Analysis: {request.title}",
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
        logger.error(f"❌ Slide analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ============ STEP 1B: ANALYSIS FROM PDF ============


@router.post("/analyze-from-pdf", response_model=AnalyzeSlideResponse)
async def analyze_slide_from_pdf(
    request: AnalyzeSlideFromPdfRequest,
    user_info: dict = Depends(require_auth),
):
    """
    **STEP 1 (PDF): Analyze PDF content and generate structured slide outline**

    **Cost:** 2 points (same as regular analysis)

    **Difference from regular analyze:**
    - Accepts `file_id` instead of relying only on user_query
    - Extracts content from PDF file (max 20MB)
    - AI generates outline based on PDF content + user instructions

    **Flow:**
    1. User uploads PDF via `/api/files/upload` → gets `file_id`
    2. User provides: title, goal, type, slide range, language, user_query
    3. Backend downloads PDF from R2 storage
    4. Backend uploads PDF to Gemini Files API
    5. AI analyzes PDF content + user instructions
    6. Returns outline with slide structure

    **Returns:**
    - Same as `/analyze` endpoint
    - analysis_id for Step 2
    - slides_outline (user can add image URLs before Step 2)
    """
    try:
        import os
        import time
        import json
        import google.generativeai as genai
        from src.core.config import APP_CONFIG
        from src.services.file_download_service import FileDownloadService

        logger.info(f"📄 PDF slide analysis request from user {user_info['uid']}")
        logger.info(f"   File ID: {request.file_id}")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Type: {request.slide_type}")
        logger.info(
            f"   Range: {request.num_slides_range.min}-{request.num_slides_range.max}"
        )

        # 1. Check points
        points_service = get_points_service()
        points_check = await points_service.check_sufficient_points(
            user_id=user_info["uid"], points_needed=2, service="slide_ai_analysis_pdf"
        )

        if not points_check["has_points"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để phân tích slide từ PDF. Cần: 2, Còn: {points_check['points_available']}",
                    "points_needed": 2,
                    "points_available": points_check["points_available"],
                },
            )

        # 2. Get file from database
        mongo_service = get_mongodb_service()
        files_collection = mongo_service.db["files"]

        file_doc = files_collection.find_one(
            {"file_id": request.file_id, "user_id": user_info["uid"]}
        )

        if not file_doc:
            raise HTTPException(
                status_code=404,
                detail="File not found. Please upload file first via /api/files/upload",
            )

        # Validate file type
        file_type = file_doc.get("file_type", "").lower()
        if file_type != ".pdf":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file_type}. Only PDF files are supported.",
            )

        # Check file size (max 20MB)
        file_size = file_doc.get("file_size_bytes", 0)
        max_size = 20 * 1024 * 1024  # 20MB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"PDF file too large: {file_size / 1024 / 1024:.1f}MB. Maximum: 20MB",
            )

        # 3. Download PDF from R2
        r2_key = file_doc.get("r2_key")
        if not r2_key:
            raise HTTPException(status_code=500, detail="File R2 key not found")

        logger.info(f"📥 Downloading PDF from R2: {r2_key}")

        temp_pdf_path = await FileDownloadService._download_file_from_r2_with_boto3(
            r2_key=r2_key, file_type="pdf"
        )

        if not temp_pdf_path:
            raise HTTPException(
                status_code=500, detail="Failed to download PDF from R2"
            )

        logger.info(f"✅ PDF downloaded to: {temp_pdf_path}")

        # 4. Upload PDF to Gemini Files API
        uploaded_file = None
        try:
            genai.configure(api_key=APP_CONFIG["gemini_api_key"])

            logger.info(f"📤 Uploading PDF to Gemini Files API...")
            uploaded_file = genai.upload_file(temp_pdf_path)
            logger.info(f"✅ PDF uploaded: {uploaded_file.uri}")

            # Wait for file processing
            while uploaded_file.state.name == "PROCESSING":
                logger.info("⏳ Waiting for PDF processing...")
                time.sleep(2)
                uploaded_file = genai.get_file(uploaded_file.name)

            if uploaded_file.state.name == "FAILED":
                raise Exception("PDF processing failed in Gemini")

            logger.info(f"✅ PDF ready: {uploaded_file.state.name}")

        except Exception as e:
            logger.error(f"❌ Failed to upload PDF to Gemini: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to process PDF: {str(e)}"
            )
        finally:
            # Cleanup temp file
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                    logger.info(f"🗑️ Cleaned up temp file: {temp_pdf_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to cleanup temp file: {e}")

        # 5. Call AI for analysis with PDF
        ai_service = get_slide_ai_service()
        start_time = datetime.now()

        # Build prompt for PDF-based analysis
        pdf_analysis_prompt = f"""Analyze this PDF document and create a structured slide presentation outline.

**User Requirements:**
- Title: {request.title}
- Goal: {request.target_goal}
- Type: {request.slide_type}
- Slides: {request.num_slides_range.min}-{request.num_slides_range.max}
- Language: {request.language}
- Additional Instructions: {request.user_query}

**Your Task:**
1. Read and understand the PDF content thoroughly
2. Extract key information, main topics, and supporting details
3. Create a logical slide structure that covers the content
4. Generate {request.num_slides_range.min}-{request.num_slides_range.max} slides

**Output Format (JSON):**
{{
  "presentation_summary": "Brief overview of the presentation...",
  "num_slides": <number between min and max>,
  "slides": [
    {{
      "slide_number": 1,
      "title": "Slide title",
      "content_points": ["Point 1", "Point 2", "Point 3"],
      "suggested_visuals": ["Visual 1", "Visual 2"],
      "image_suggestion": "Description of suggested image",
      "estimated_duration": "2-3 minutes"
    }}
  ]
}}

**IMPORTANT:**
- Content MUST come from the PDF document
- Follow user instructions: {request.user_query}
- Adapt to {request.slide_type} style (academy = educational, business = professional)
- Use {request.language} language for all text
- Return ONLY valid JSON, no markdown"""

        # Call Gemini with PDF
        try:
            model = genai.GenerativeModel("gemini-3-pro-preview")

            response = model.generate_content(
                [uploaded_file, pdf_analysis_prompt],
                generation_config={
                    "temperature": 0.7,
                    "response_mime_type": "application/json",
                },
            )

            # Parse AI response
            analysis_result = json.loads(response.text)

            # Validate response structure
            if "slides" not in analysis_result or "num_slides" not in analysis_result:
                raise ValueError("Invalid AI response format")

        except Exception as e:
            logger.error(f"❌ AI analysis failed: {e}")
            raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")
        finally:
            # Delete file from Gemini after processing
            if uploaded_file:
                try:
                    genai.delete_file(uploaded_file.name)
                    logger.info(f"🗑️ Deleted file from Gemini: {uploaded_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete Gemini file: {e}")

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        # 6. Save analysis to database (same as regular)
        collection = mongo_service.db["slide_analyses"]

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
                    image_url=None,
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
            # PDF-specific metadata
            "source": "pdf",
            "source_file_id": request.file_id,
            "source_file_name": file_doc.get("original_file_name", ""),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        result = collection.insert_one(analysis_doc)
        analysis_id = str(result.inserted_id)

        logger.info(
            f"✅ PDF analysis saved: {analysis_id} ({len(slides_outline)} slides)"
        )

        # 7. Deduct points (only after success)
        await points_service.deduct_points(
            user_id=user_info["uid"],
            amount=2,
            service="slide_ai_analysis_pdf",
            resource_id=analysis_id,
            description=f"Slide AI Analysis from PDF: {request.title}",
        )

        logger.info(f"💰 Deducted 2 points from user {user_info['uid']}")

        # 8. Return response (same format)
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
        logger.error(f"❌ PDF slide analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ STEP 2: HTML GENERATION ============


@router.post("/create", response_model=CreateSlideResponse)
async def create_slides_from_analysis(
    request: CreateSlideRequest,
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
        points_check = await points_service.check_sufficient_points(
            user_id=user_info["uid"],
            points_needed=points_needed,
            service="slide_ai_generation",
        )

        if not points_check["has_points"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để tạo {num_slides} slides. Cần: {points_needed}, Còn: {points_check['points_available']}",
                    "points_needed": points_needed,
                    "points_available": points_check["points_available"],
                },
            )

        # 4. Validate creator_name if provided
        if request.creator_name:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            validate_creator_name(request.creator_name, user_email, user_info["uid"])

        # 5. Create slide document using DocumentManager (compatible with existing system)
        doc_manager = DocumentManager(mongo_service.db)
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

        # 7. Enqueue task to Redis (replaces BackgroundTasks)
        import json

        queue = await get_slide_generation_queue()

        task = SlideGenerationTask(
            task_id=document_id,
            document_id=document_id,
            user_id=user_info["uid"],
            step=2,  # HTML generation step
            analysis_id=request.analysis_id,
        )

        # Store additional data in document for worker to use
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "slide_generation_data": {
                        "logo_url": request.logo_url,
                        "slide_images": slide_images_dict,
                        "user_query": request.user_query,
                        "points_needed": points_needed,
                    }
                }
            },
        )

        success = await queue.enqueue_generic_task(task)

        if not success:
            # Rollback: Delete document
            mongo_service.db["documents"].delete_one({"document_id": document_id})
            raise HTTPException(
                status_code=500, detail="Failed to enqueue slide generation task"
            )

        logger.info(f"🚀 Slide generation task enqueued to Redis: {document_id}")

        # 8. Return immediately with full document metadata for frontend
        return CreateSlideResponse(
            success=True,
            document_id=document_id,
            status="pending",
            title=analysis["title"],
            num_slides=num_slides,
            batches_needed=batches_needed,
            points_needed=points_needed,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            message=f"Slide creation started. AI is generating HTML for {num_slides} slides in {batches_needed} batch(es)...",
            poll_url=f"/api/slides/ai-generate/status/{document_id}",
            document_type="slide",
            creator_name=request.creator_name,
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
    doc_manager = DocumentManager(mongo_service.db)

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
            amount=points_needed,
            service="slide_ai_generation",
            resource_id=document_id,
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


# ============ BASIC SLIDE CREATION (NO AI) ============


@router.post("/create-basic", response_model=CreateBasicSlideResponse)
async def create_basic_slide_from_analysis(
    request: CreateBasicSlideRequest,
    user_info: dict = Depends(require_auth),
):
    """
    **Create basic slide from analysis outline (NO AI generation)**

    **Cost:** FREE (0 points)

    **Purpose:**
    - Save the outline from Step 1 as a slide document
    - User can manually edit slides later (add content, images, backgrounds)
    - No AI HTML generation - just creates empty slides with titles and bullet points

    **Flow:**
    1. Get analysis from Step 1 (analysis_id)
    2. Create slide document with basic HTML structure
    3. Each slide has: title + content points as bullet list
    4. User can edit everything in the slide editor

    **Returns:**
    - document_id: New slide document (ready to edit)
    - No background job, no polling needed
    """
    try:
        logger.info(f"📄 Basic slide creation from analysis {request.analysis_id}")

        mongo_service = get_mongodb_service()

        # 1. Get analysis from database
        analysis = mongo_service.db["slide_analyses"].find_one(
            {"_id": ObjectId(request.analysis_id), "user_id": user_info["uid"]}
        )

        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="Analysis not found. Please run Step 1 first.",
            )

        # 2. Validate creator_name if provided
        if request.creator_name:
            from src.services.creator_name_validator import validate_creator_name

            user_email = user_info.get("email", "")
            validate_creator_name(request.creator_name, user_email, user_info["uid"])

        # 3. Build basic HTML from outline
        slides_outline = analysis["slides_outline"]
        num_slides = len(slides_outline)

        slides_html = []
        for slide_data in slides_outline:
            slide_num = slide_data["slide_number"]
            title = slide_data["title"]
            points = slide_data.get("content_points", [])

            # Create simple HTML for each slide
            points_html = "".join([f"<li>{point}</li>" for point in points])

            slide_html = f"""<div class="slide" data-slide-number="{slide_num}">
  <div class="slide-content">
    <h1>{title}</h1>
    <ul>
{points_html}
    </ul>
  </div>
</div>"""
            slides_html.append(slide_html)

        final_html = "\n\n".join(slides_html)

        # 4. Create default backgrounds
        slide_backgrounds = _create_default_backgrounds(
            num_slides, analysis["slide_type"]
        )

        # 5. Create slide document
        doc_manager = DocumentManager(mongo_service.db)
        document_id = doc_manager.create_document(
            user_id=user_info["uid"],
            title=analysis["title"],
            content_html=final_html,
            content_text=analysis.get("presentation_summary", ""),
            source_type="created",
            document_type="slide",
        )

        # 6. Add metadata
        mongo_service.db["documents"].update_one(
            {"document_id": document_id},
            {
                "$set": {
                    # Link to analysis
                    "ai_analysis_id": request.analysis_id,
                    "ai_slide_type": analysis["slide_type"],
                    "ai_language": analysis["language"],
                    "ai_num_slides": num_slides,
                    # Mark as basic (not AI generated)
                    "ai_generation_type": "basic",
                    # Slide data
                    "slide_elements": [],
                    "slide_backgrounds": slide_backgrounds,
                    # Creator info
                    "creator_name": request.creator_name or user_info.get("email", ""),
                }
            },
        )

        logger.info(
            f"✅ Basic slide created: {document_id} ({num_slides} slides, 0 points)"
        )

        return CreateBasicSlideResponse(
            success=True,
            document_id=document_id,
            title=analysis["title"],
            num_slides=num_slides,
            created_at=datetime.now().isoformat(),
            message=f"Slide outline saved successfully. {num_slides} slides ready to edit.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Basic slide creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
