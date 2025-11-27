"""
Online Test Cover AI Generation Routes
Uses Gemini 3 Pro Image to generate test covers with 16:9 aspect ratio
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import logging
import time
import base64

# Authentication
from src.middleware.firebase_auth import get_current_user

# Database
from src.database.db_manager import DBManager

# Models
from src.models.book_models import (
    GenerateTestCoverRequest,
    GenerateTestCoverResponse,
)

# Services
from src.services.gemini_test_cover_service import (
    GeminiTestCoverService,
    get_gemini_test_cover_service,
)
from src.services.points_service import get_points_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tests/ai/cover", tags=["AI Test Cover"])

# Initialize DB
db_manager = DBManager()
db = db_manager.db


@router.post(
    "/generate",
    response_model=GenerateTestCoverResponse,
    summary="Generate online test cover using Gemini 3 Pro Image",
)
async def generate_test_cover_ai(
    request: GenerateTestCoverRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate online test cover image using Gemini 3 Pro Image (gemini-3-pro-image-preview)**

    Generates a professional test cover with title rendered on the cover.
    Uses Google's state-of-the-art image generation model optimized for text rendering.

    **Features:**
    - Uses Gemini 3 Pro Image model (gemini-3-pro-image-preview)
    - Advanced text rendering: Title clearly visible on cover
    - Wide format output: 16:9 aspect ratio (landscape orientation)
    - Perfect for online tests and exams
    - Multiple style options
    - Returns base64 encoded PNG image
    - Automatically saved to user's library

    **Authentication:** Required (costs 2 points per generation)

    **Request Body:**
    ```json
    {
        "title": "IELTS Practice Test 2024",
        "description": "Modern educational design with books and pencils, clean minimalist style",
        "style": "modern"
    }
    ```

    **Required Fields:**
    - `title`: Test title (will be rendered on cover)
    - `description`: Design description (visual elements, theme, colors)

    **Optional Fields:**
    - `style`: Art style (modern, minimalist, professional, educational, academic)

    **Available Styles:**
    - `modern` - Contemporary, clean design
    - `minimalist` - Simple, focused design
    - `professional` - Corporate/business style
    - `educational` - Academic, learning-focused
    - `academic` - Scholarly, traditional style

    **Response:**
    - `success`: True if generation succeeded
    - `image_base64`: PNG image in base64 format
    - `prompt_used`: Full prompt sent to Gemini
    - `title`: Test title
    - `aspect_ratio`: "16:9"
    - `model`: "gemini-3-pro-image-preview"
    - `generation_time_ms`: Time taken in milliseconds
    - `file_id`: Library file ID
    - `file_url`: Direct download URL
    - `r2_key`: R2 storage key

    **Example Usage:**
    1. Generate cover with title: `POST /api/v1/tests/ai/cover/generate`
    2. Regenerate with different description/style if needed
    3. Decode base64 image and display in frontend
    4. Use file_url to access from library

    **Rate Limits:**
    - Costs 2 points per generation
    - Each generation takes ~5-15 seconds

    **Error Responses:**
    - `402`: Insufficient points
    - `500`: Generation failed (with error details)
    """
    start_time = time.time()

    try:
        user_id = current_user["uid"]
        logger.info(f"🎨 User {user_id} generating test cover")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Description: {request.description[:50]}...")

        # ===== STEP 1: Check and deduct points (2 points) =====
        points_service = get_points_service()
        points_cost = 2  # Fixed 2 points for test cover AI generation

        # Check sufficient points
        check_result = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=points_cost,
            service="ai_test_cover_generation",
        )

        if not check_result["has_points"]:
            logger.warning(
                f"💰 Insufficient points for test cover AI - User: {user_id}, Need: {points_cost}, Have: {check_result['points_available']}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để tạo ảnh bìa đề thi bằng AI. Cần: {points_cost}, Còn: {check_result['points_available']}",
                    "points_needed": points_cost,
                    "points_available": check_result["points_available"],
                    "service": "ai_test_cover_generation",
                    "action_required": "purchase_points",
                    "purchase_url": "/pricing",
                },
            )

        logger.info(
            f"💰 Points check passed - User: {user_id}, Cost: {points_cost} points"
        )

        # Initialize Gemini service (use singleton)
        gemini_service = get_gemini_test_cover_service()

        # Generate image
        result = await gemini_service.generate_test_cover(
            title=request.title,
            description=request.description,
            style=request.style,
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"✅ Generated test cover for user {user_id} in {generation_time_ms}ms"
        )

        # ===== STEP 2: Upload to R2 and save to library =====
        try:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(result["image_base64"])
            file_size = len(image_bytes)

            # Generate filename
            safe_title = "".join(
                c for c in request.title if c.isalnum() or c in (" ", "-", "_")
            )[:30]
            filename = f"test_cover_{safe_title}_{int(time.time())}.png"

            # Upload to R2
            upload_result = await gemini_service.upload_to_r2(
                image_bytes=image_bytes,
                user_id=user_id,
                filename=filename,
            )

            logger.info(f"☁️  Uploaded test cover to R2: {upload_result['file_url']}")

            # Save to library
            library_doc = await gemini_service.save_to_library(
                user_id=user_id,
                filename=filename,
                file_size=file_size,
                r2_key=upload_result["r2_key"],
                file_url=upload_result["file_url"],
                title=request.title,
                description=request.description,
                style=request.style,
                prompt_used=result["prompt_used"],
                db=db,
            )

            logger.info(f"📚 Saved test cover to library: {library_doc['file_id']}")

        except Exception as storage_error:
            logger.error(f"❌ Failed to save to R2/library: {storage_error}")
            # Continue with response even if storage fails
            library_doc = {}
            upload_result = {}

        # ===== STEP 3: Deduct points after success =====
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_cost,
                service="ai_test_cover_generation",
                resource_id=f"test_cover_{int(time.time())}",
                description=f"AI test cover: {request.title}",
            )
            logger.info(f"💸 Deducted {points_cost} points for test cover generation")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")
            # Don't fail the request, just log the error

        return GenerateTestCoverResponse(
            success=True,
            image_base64=result["image_base64"],
            prompt_used=result["prompt_used"],
            title=result.get("title"),
            style=result.get("style"),
            model=result.get("model"),
            aspect_ratio=result.get("aspect_ratio"),
            timestamp=result.get("timestamp"),
            generation_time_ms=generation_time_ms,
            file_id=library_doc.get("file_id") if library_doc else None,
            file_url=upload_result.get("file_url") if upload_result else None,
            r2_key=upload_result.get("r2_key") if upload_result else None,
        )

    except ImportError as e:
        logger.error(f"❌ Missing dependencies: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "DEPENDENCY_ERROR",
                "message": "Gemini AI service not available. Please contact administrator.",
                "technical_details": str(e),
            },
        )

    except ValueError as e:
        logger.error(f"❌ Generation error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GENERATION_FAILED",
                "message": "Không thể tạo ảnh bìa đề thi. Vui lòng thử lại.",
                "technical_details": str(e),
            },
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions (like insufficient points)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Lỗi hệ thống. Vui lòng thử lại sau.",
                "technical_details": str(e),
            },
        )
