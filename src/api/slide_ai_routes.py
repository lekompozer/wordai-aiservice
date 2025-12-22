"""
Slide AI Routes
API endpoints for AI-powered slide formatting and editing
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging
import uuid

from src.middleware.firebase_auth import get_current_user
from src.services.points_service import get_points_service
from src.queue.queue_dependencies import get_slide_format_queue
from src.models.ai_queue_tasks import SlideFormatTask
from src.models.slide_format_job_models import (
    CreateSlideFormatJobResponse,
    SlideFormatJobStatusResponse,
    SlideFormatJobStatus,
)
from src.models.slide_ai_models import SlideAIFormatRequest
from src.services.online_test_utils import get_mongodb_service

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/slides", tags=["Slide AI"])

# Points cost
POINTS_COST_FORMAT = 2  # Layout optimization with Claude Sonnet 4.5
POINTS_COST_EDIT = 2  # Content rewriting with Gemini 3 Pro


@router.post(
    "/ai-format",
    response_model=CreateSlideFormatJobResponse,
    summary="Format slide with AI assistance (async job)",
)
async def ai_format_slide(
    request: SlideAIFormatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Format slide with AI to improve layout, typography, and visual hierarchy

    **⚠️ BREAKING CHANGE: Now returns job_id for async processing**

    **Authentication:** Required

    **Cost:**
    - Format (improve layout/design): 2 points
    - Edit (rewrite content): 2 points

    **Processing time**: 30-120 seconds

    **Returns:** Job ID for polling status at GET /api/slides/jobs/{job_id}

    **Request Body:**
    - slide_index: Slide index to format
    - current_html: Current slide HTML content
    - elements: Current slide elements (shapes, images)
    - background: Current slide background
    - user_instruction: Optional instruction (e.g., "Make it more professional")
    - format_type: "format" or "edit"

    **Example:**
    ```json
    {
      "slide_index": 0,
      "current_html": "<h1>My Title</h1><p>Some content</p>",
      "elements": [...],
      "background": {...},
      "user_instruction": "Make it more modern and professional",
      "format_type": "format"
    }
    ```
    """
    try:
        user_id = current_user["uid"]

        # Determine points cost based on format type
        points_cost = (
            POINTS_COST_FORMAT if request.format_type == "format" else POINTS_COST_EDIT
        )

        # Check points
        points_service = get_points_service()
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=points_cost,
            service="slide_ai_formatting",
        )

        if not check["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để format slide. Cần: {points_cost}, Còn: {check['points_available']}",
                    "points_needed": points_cost,
                    "points_available": check["points_available"],
                },
            )

        logger.info(f"🎨 User {user_id} formatting slide {request.slide_index}")
        logger.info(f"   Format type: {request.format_type}")
        logger.info(f"   Points cost: {points_cost}")

        # Deduct points BEFORE queueing
        await points_service.deduct_points(
            user_id=user_id,
            amount=points_cost,
            service="slide_ai_formatting",
            resource_id=f"slide_{request.slide_index}",
            description=f"AI {request.format_type}: {request.user_instruction or 'Auto format'}",
        )

        logger.info(f"💸 Deducted {points_cost} points for slide AI format")

        # Enqueue task to Redis
        task_id = str(uuid.uuid4())
        queue = await get_slide_format_queue()

        task = SlideFormatTask(
            task_id=task_id,
            job_id=task_id,
            user_id=user_id,
            slide_index=request.slide_index,
            current_html=request.current_html,
            elements=request.elements,
            background=request.background,
            user_instruction=request.user_instruction,
            format_type=request.format_type,
        )

        success = await queue.enqueue_generic_task(task)

        if not success:
            logger.error(f"❌ Failed to enqueue task {task_id}")
            raise HTTPException(
                status_code=500, detail="Failed to enqueue task to Redis"
            )

        logger.info(f"✅ Task {task_id} enqueued to Redis slide_format queue")

        return CreateSlideFormatJobResponse(
            job_id=task_id,
            status=SlideFormatJobStatus.PENDING,
            message="Slide format job queued. Poll /api/slides/jobs/{job_id} for status.",
            estimated_time="30-120 seconds",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to queue slide format: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/jobs/{job_id}",
    response_model=SlideFormatJobStatusResponse,
    summary="Get slide format job status",
)
async def get_slide_format_job_status(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Poll slide format job status

    **Returns:**
    - pending: Job in queue
    - processing: AI is working
    - completed: Done (check formatted_html, suggested_elements, etc.)
    - failed: Error (check error field)
    """
    try:
        user_id = current_user["uid"]
        mongo_service = get_mongodb_service()
        jobs_collection = mongo_service.db["slide_format_jobs"]

        job = jobs_collection.find_one({"job_id": job_id})

        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found. It may not have started processing yet.",
            )

        # Verify ownership
        if job.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have access to this job"
            )

        return SlideFormatJobStatusResponse(
            job_id=job["job_id"],
            status=SlideFormatJobStatus(job["status"]),
            created_at=(
                job.get("created_at", "").isoformat() if job.get("created_at") else None
            ),
            started_at=(
                job.get("started_at", "").isoformat() if job.get("started_at") else None
            ),
            completed_at=(
                job.get("completed_at", "").isoformat()
                if job.get("completed_at")
                else None
            ),
            processing_time_seconds=job.get("processing_time_seconds"),
            formatted_html=job.get("formatted_html"),
            suggested_elements=job.get("suggested_elements"),
            suggested_background=job.get("suggested_background"),
            ai_explanation=job.get("ai_explanation"),
            error=job.get("error"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
