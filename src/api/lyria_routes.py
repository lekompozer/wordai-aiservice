"""
Lyria Music Generation API Routes
AI Tools - Music generation from text prompts
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.models.lyria_models import (
    LyriaMusicRequest,
    LyriaMusicTask,
    LyriaMusicResponse,
)
from src.services.points_service import get_points_service
from src.services.rate_limit import check_ai_rate_limit
from src.queue.queue_dependencies import get_lyria_music_queue
from src.queue.queue_manager import get_job_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lyria", tags=["Lyria Music Generation"])

# Cost configuration
POINTS_COST_MUSIC = 3  # 3 points per 30s music generation


@router.post(
    "/generate",
    response_model=LyriaMusicResponse,
    summary="Generate Music from Text Prompt",
    description="""
    **Generate instrumental music using Lyria AI**

    Uses Google Vertex AI Lyria-002 model to create ~30 second instrumental music
    from text description.

    **Cost:** 3 points per generation

    **Features:**
    - Text-to-music generation (English prompts recommended)
    - Instrumental music output (no vocals)
    - ~30 seconds duration
    - Automatic save to library_audio
    - Background queue processing
    - Real-time job status polling

    **Example Prompts:**
    - "An energetic electronic dance track with a fast tempo"
    - "A calm acoustic folk song with gentle guitar melody"
    - "Upbeat jazz piano with smooth saxophone"
    - "Epic orchestral soundtrack with dramatic strings"

    **Flow:**
    1. Deduct 3 points (refunded on failure)
    2. Enqueue generation job
    3. Return job_id for polling
    4. Poll GET /lyria/status/{job_id}
    5. Download from library_audio when completed

    **Rate Limit:** 10 requests per minute per user
    """,
)
async def generate_music(
    request: LyriaMusicRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate music from text prompt (async queue)"""
    try:
        user_id = current_user["uid"]
        user_email = current_user.get("email", "unknown")

        logger.info("=" * 80)
        logger.info("🎵 LYRIA MUSIC GENERATION REQUEST")
        logger.info(f"📍 Endpoint: POST /api/v1/lyria/generate")
        logger.info(f"👤 User: {user_email} ({user_id})")
        logger.info(f"🎼 Prompt: {request.prompt[:100]}...")
        if request.negative_prompt:
            logger.info(f"🚫 Negative: {request.negative_prompt}")
        if request.seed is not None:
            logger.info(f"🎲 Seed: {request.seed}")
        logger.info("=" * 80)

        # ✅ SECURITY: Rate limiting
        try:
            await check_ai_rate_limit(
                user_id=user_id,
                action="lyria_music_generation",
                max_requests=10,
                window_seconds=60,
            )
        except Exception as rate_error:
            logger.warning(f"⚠️ Rate limit exceeded: {user_id}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please wait 1 minute.",
                    "retry_after": 60,
                },
            )

        # Get points service
        points_service = get_points_service()

        # Check points BEFORE generation
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=POINTS_COST_MUSIC,
            service="lyria_music_generation",
        )

        if not check["has_points"]:
            logger.warning(
                f"❌ Insufficient points: {check['points_available']} < {POINTS_COST_MUSIC}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ điểm. Cần: {POINTS_COST_MUSIC}, Còn: {check['points_available']}",
                    "points_needed": POINTS_COST_MUSIC,
                    "points_available": check["points_available"],
                },
            )

        # Deduct points BEFORE enqueuing (refund on failure)
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_MUSIC,
            service="lyria_music",
            resource_id="",  # Will be updated with job_id
            description=f"Music generation: {request.prompt[:50]}...",
        )

        logger.info(f"✅ Deducted {POINTS_COST_MUSIC} points from user {user_id}")

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Create task for queue
        task = LyriaMusicTask(
            task_id=job_id,
            job_id=job_id,
            user_id=user_id,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            seed=request.seed,
        )

        # Get queue and enqueue
        queue = await get_lyria_music_queue()
        await queue.enqueue_generic_task(task)

        logger.info(f"✅ Music generation job {job_id} enqueued")
        logger.info(f"   Prompt: {request.prompt[:50]}...")
        logger.info(f"   Status: pending → Poll /lyria/status/{job_id}")

        return LyriaMusicResponse(
            job_id=job_id,
            status="pending",
            audio_url=None,
            library_audio_id=None,
            duration_seconds=30,  # Lyria generates ~30s
            error=None,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create music generation job: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to create music generation job: {str(e)}")


@router.get(
    "/status/{job_id}",
    response_model=LyriaMusicResponse,
    summary="Get Music Generation Job Status",
    description="""
    Poll music generation job status.

    **Status Flow:**
    - pending → processing → completed (success)
    - pending → processing → failed (error)

    **When Completed:**
    - audio_url: R2 public URL for playback
    - library_audio_id: Library audio ID
    - duration_seconds: Music duration (~30s)

    **Polling Recommendation:**
    - Poll every 3-5 seconds during processing
    - Stop polling when status is 'completed' or 'failed'
    - Expected time: 30-60 seconds

    **On Failure:**
    - Points are automatically refunded
    - error: Error message describing failure
    """,
)
async def get_music_generation_status(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get music generation job status"""
    try:
        queue = await get_lyria_music_queue()
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            raise HTTPException(404, f"Job {job_id} not found")

        # Check authorization (job must belong to current user)
        if job.get("user_id") != current_user["uid"]:
            raise HTTPException(403, "Not authorized to view this job")

        return LyriaMusicResponse(
            job_id=job_id,
            status=job.get("status", "pending"),
            audio_url=job.get("audio_url"),
            library_audio_id=job.get("library_audio_id"),
            duration_seconds=job.get("duration_seconds", 30),
            error=job.get("error"),
            created_at=job.get("created_at"),
            updated_at=job.get("updated_at"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get job status: {str(e)}")
