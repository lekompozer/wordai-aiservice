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
from src.queue.queue_manager import set_job_status, get_job_status
from src.models.ai_queue_tasks import SlideFormatTask
from src.models.slide_format_job_models import (
    CreateSlideFormatJobResponse,
    SlideFormatJobStatusResponse,
    SlideFormatJobStatus,
)
from src.models.slide_ai_models import SlideAIFormatRequest

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
    Format slide(s) with AI to improve layout, typography, and visual hierarchy

    **⚠️ BREAKING CHANGE: Now returns job_id for async processing**

    **3 Processing Modes:**

    **Mode 1: Single Slide** (backward compatible)
    ```json
    {
      "slide_index": 2,
      "current_html": "<h1>Title</h1>",
      "elements": [...],
      "background": {...},
      "format_type": "format"
    }
    ```

    **Mode 2: Multiple Specific Slides**
    ```json
    {
      "slides_data": [
        {"slide_index": 0, "current_html": "...", "elements": [], "background": null},
        {"slide_index": 2, "current_html": "...", "elements": [], "background": null},
        {"slide_index": 5, "current_html": "...", "elements": [], "background": null}
      ],
      "format_type": "format"
    }
    ```

    **Mode 3: Entire Document** (all slides)
    ```json
    {
      "process_all_slides": true,
      "slides_data": [
        {"slide_index": 0, "current_html": "...", "elements": [], "background": null},
        {"slide_index": 1, "current_html": "...", "elements": [], "background": null},
        ...all slides...
      ],
      "format_type": "format"
    }
    ```

    **Authentication:** Required

    **Cost:**
    - Format (improve layout/design): 2 points **per slide**
    - Edit (rewrite content): 2 points **per slide**
    - Batch: Total cost = number of slides × 2 points

    **Processing time**:
    - Single slide: 30-120 seconds
    - Multiple slides: 30-120 seconds × number of slides (parallel processing)

    **Returns:** Job ID for polling status at GET /api/slides/jobs/{job_id}
    """
    try:
        user_id = current_user["uid"]

        # Validate request and determine mode
        is_batch = False
        slides_to_process = []

        # Mode detection
        if request.slides_data:
            # Mode 2 or 3: Batch processing
            is_batch = True
            slides_to_process = request.slides_data

            if request.process_all_slides:
                logger.info(
                    f"📋 Mode 3: Processing ALL {len(slides_to_process)} slides"
                )
            else:
                logger.info(
                    f"📋 Mode 2: Processing {len(slides_to_process)} specific slides"
                )

        elif request.slide_index is not None and request.current_html:
            # Mode 1: Single slide (backward compatible)
            logger.info(f"📄 Mode 1: Processing single slide {request.slide_index}")
            from src.models.slide_ai_models import SlideData

            slides_to_process = [
                SlideData(
                    slide_index=request.slide_index,
                    current_html=request.current_html,
                    elements=request.elements or [],
                    background=request.background,
                )
            ]
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid request. Provide either: (slide_index + current_html) OR slides_data array",
            )

        # Calculate points cost
        num_slides = len(slides_to_process)
        points_per_slide = (
            POINTS_COST_FORMAT if request.format_type == "format" else POINTS_COST_EDIT
        )
        total_points_cost = num_slides * points_per_slide

        # Calculate points cost
        num_slides = len(slides_to_process)
        points_per_slide = (
            POINTS_COST_FORMAT if request.format_type == "format" else POINTS_COST_EDIT
        )
        total_points_cost = num_slides * points_per_slide

        # Check points
        points_service = get_points_service()
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=total_points_cost,
            service="slide_ai_formatting",
        )

        if not check["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để format {num_slides} slide(s). Cần: {total_points_cost}, Còn: {check['points_available']}",
                    "points_needed": total_points_cost,
                    "points_available": check["points_available"],
                    "slides_count": num_slides,
                },
            )

        logger.info(f"🎨 User {user_id} formatting {num_slides} slide(s)")
        logger.info(f"   Format type: {request.format_type}")
        logger.info(
            f"   Total points cost: {total_points_cost} ({num_slides} × {points_per_slide})"
        )

        # Deduct points BEFORE queueing
        await points_service.deduct_points(
            user_id=user_id,
            amount=total_points_cost,
            service="slide_ai_formatting",
            resource_id=f"slides_batch_{num_slides}",
            description=f"AI {request.format_type}: {num_slides} slide(s) - {request.user_instruction or 'Auto format'}",
        )

        logger.info(f"💸 Deducted {total_points_cost} points for {num_slides} slide(s)")

        # Create batch job or single job
        batch_job_id = str(uuid.uuid4())
        queue = await get_slide_format_queue()

        if is_batch:
            # Create parent batch job in Redis
            await set_job_status(
                redis_client=queue.redis_client,
                job_id=batch_job_id,
                status="pending",
                user_id=user_id,
                is_batch=True,
                total_slides=num_slides,
                completed_slides=0,
                failed_slides=0,
                slides_results=[],
                format_type=request.format_type,
            )

            # Enqueue individual tasks for each slide
            for i, slide_data in enumerate(slides_to_process):
                task_id = f"{batch_job_id}_slide_{slide_data.slide_index}"

                task = SlideFormatTask(
                    task_id=task_id,
                    job_id=task_id,  # Each slide has its own sub-job
                    user_id=user_id,
                    slide_index=slide_data.slide_index,
                    current_html=slide_data.current_html,
                    elements=slide_data.elements or [],
                    background=(
                        slide_data.background.dict() if slide_data.background else {}
                    ),
                    user_instruction=request.user_instruction,
                    format_type=request.format_type,
                    is_batch=True,
                    batch_job_id=batch_job_id,
                    total_slides=num_slides,
                    slide_position=i,
                )

                success = await queue.enqueue_generic_task(task)
                if not success:
                    logger.error(f"❌ Failed to enqueue task {task_id}")

            logger.info(f"✅ Batch job {batch_job_id}: Enqueued {num_slides} tasks")

            return CreateSlideFormatJobResponse(
                job_id=batch_job_id,
                status=SlideFormatJobStatus.PENDING,
                message=f"Batch job queued: {num_slides} slide(s). Poll /api/slides/jobs/{{{batch_job_id}}} for status.",
                estimated_time=f"{num_slides * 30}-{num_slides * 120} seconds",
            )

        else:
            # Single slide (Mode 1)
            slide_data = slides_to_process[0]
            task_id = batch_job_id

            # Create job in Redis
            await set_job_status(
                redis_client=queue.redis_client,
                job_id=task_id,
                status="pending",
                user_id=user_id,
                slide_index=slide_data.slide_index,
                format_type=request.format_type,
            )

            task = SlideFormatTask(
                task_id=task_id,
                job_id=task_id,
                user_id=user_id,
                slide_index=slide_data.slide_index,
                current_html=slide_data.current_html,
                elements=slide_data.elements or [],
                background=(
                    slide_data.background.dict() if slide_data.background else {}
                ),
                user_instruction=request.user_instruction,
                format_type=request.format_type,
            )

            success = await queue.enqueue_generic_task(task)

            if not success:
                logger.error(f"❌ Failed to enqueue task {task_id}")
                raise HTTPException(
                    status_code=500, detail="Failed to enqueue task to Redis"
                )

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
    - completed: Done (check formatted_html for single, slides_results for batch)
    - failed: Error (check error field)

    **Batch Jobs:**
    - is_batch: true
    - total_slides: Total number of slides
    - completed_slides: Count of completed slides
    - slides_results: Array of {slide_index, formatted_html, suggested_elements, ai_explanation, error}
    """
    try:
        user_id = current_user["uid"]

        # Get job from Redis (Pure Redis pattern)
        queue = await get_slide_format_queue()
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            # Job not in Redis - expired (24h TTL) or invalid job_id
            return SlideFormatJobStatusResponse(
                job_id=job_id,
                status=SlideFormatJobStatus.PENDING,
                created_at=None,
                started_at=None,
                completed_at=None,
                processing_time_seconds=None,
                formatted_html=None,
                suggested_elements=None,
                suggested_background=None,
                ai_explanation=None,
                error=None,
            )

        # Verify ownership
        if job.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have access to this job"
            )

        # Check if batch job
        is_batch = job.get("is_batch", False)

        if is_batch:
            # Batch job - aggregate results from sub-jobs
            total_slides = job.get("total_slides", 0)
            slides_results = job.get("slides_results", [])
            completed_slides = len(
                [r for r in slides_results if r.get("formatted_html")]
            )
            failed_slides = len([r for r in slides_results if r.get("error")])

            # Determine batch status
            if completed_slides + failed_slides == total_slides:
                batch_status = SlideFormatJobStatus.COMPLETED
            elif completed_slides > 0 or failed_slides > 0:
                batch_status = SlideFormatJobStatus.PROCESSING
            else:
                batch_status = SlideFormatJobStatus.PENDING

            return SlideFormatJobStatusResponse(
                job_id=job["job_id"],
                status=batch_status,
                created_at=job.get("created_at"),
                started_at=job.get("started_at"),
                completed_at=job.get("completed_at"),
                processing_time_seconds=job.get("processing_time_seconds"),
                is_batch=True,
                total_slides=total_slides,
                completed_slides=completed_slides,
                failed_slides=failed_slides,
                slides_results=slides_results,
                error=job.get("error"),
            )
        else:
            # Single slide job
            return SlideFormatJobStatusResponse(
                job_id=job["job_id"],
                status=SlideFormatJobStatus(job["status"]),
                created_at=job.get("created_at"),
                started_at=job.get("started_at"),
                completed_at=job.get("completed_at"),
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
