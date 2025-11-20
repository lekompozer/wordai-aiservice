"""
Book Cover AI Generation Routes
Uses OpenAI gpt-image-1 to generate book covers
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import logging
import time

# Authentication
from src.middleware.firebase_auth import get_current_user

# Models
from src.models.book_models import (
    GenerateBookCoverRequest,
    GenerateBookCoverResponse,
)

# Services
from src.services.gemini_book_cover_service import GeminiBookCoverService
from src.services.points_service import get_points_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books/ai/cover", tags=["AI Book Cover"])


@router.post(
    "/generate",
    response_model=GenerateBookCoverResponse,
    summary="Generate book cover using Gemini 3 Pro Image",
)
async def generate_book_cover_ai(
    request: GenerateBookCoverRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate book cover image using Gemini 3 Pro Image (gemini-3-pro-image-preview)**

    Generates a professional book cover with title and author name rendered on the cover.
    Uses Google's state-of-the-art image generation model optimized for text rendering.

    **Features:**
    - Uses Gemini 3 Pro Image model (gemini-3-pro-image-preview)
    - Advanced text rendering: Title and author name clearly visible on cover
    - High-resolution output: 1K (896x1200) or 2K (1792x2400)
    - Book cover aspect ratio: 3:4 (portrait orientation)
    - Multiple style options
    - Returns base64 encoded PNG image

    **Authentication:** Required (costs 2 points per generation)

    **Request Body:**
    ```json
    {
        "title": "The Dragon's Quest",
        "author": "John Smith",
        "prompt": "A fantasy scene with a magical castle in the sky surrounded by dragons, mystical atmosphere",
        "style": "fantasy art",
        "resolution": "1K"
    }
    ```

    **Required Fields:**
    - `title`: Book title (will be rendered on cover)
    - `author`: Author name (will be rendered on cover)
    - `prompt`: Design description (visual elements, theme, colors)

    **Optional Fields:**
    - `style`: Art style (fantasy art, minimalist, photorealistic, watercolor, professional)
    - `resolution`: "1K" (896x1200px, default) or "2K" (1792x2400px)

    **Available Styles:**
    - `fantasy art` - Epic fantasy illustrations
    - `minimalist` - Clean, modern design
    - `photorealistic` - Realistic photography style
    - `watercolor` - Soft watercolor paintings
    - `professional` - Corporate/business style

    **Response:**
    - `success`: True if generation succeeded
    - `image_base64`: PNG image in base64 format
    - `prompt_used`: Full prompt sent to Gemini
    - `title`: Book title
    - `author`: Author name
    - `aspect_ratio`: "3:4"
    - `resolution`: "1K" or "2K"
    - `model`: "gemini-3-pro-image-preview"
    - `generation_time_ms`: Time taken in milliseconds

    **Example Usage:**
    1. Generate cover with title/author: `POST /api/v1/books/ai/cover/generate`
    2. Regenerate with different prompt/style if needed
    3. Decode base64 image and display in frontend
    4. Save to book using image upload endpoints

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
        logger.info(f"🎨 User {user_id} generating book cover")
        logger.info(f"   Title: {request.title}")
        logger.info(f"   Author: {request.author}")
        logger.info(f"   Prompt: {request.prompt[:50]}...")

        # ===== STEP 1: Check and deduct points (2 points) =====
        points_service = get_points_service()
        points_cost = 2  # Fixed 2 points for book cover AI generation

        # Check sufficient points
        check_result = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=points_cost,
            service="ai_book_cover_generation",
        )

        if not check_result["has_points"]:
            logger.warning(
                f"💰 Insufficient points for book cover AI - User: {user_id}, Need: {points_cost}, Have: {check_result['points_available']}"
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để tạo bìa sách bằng AI. Cần: {points_cost}, Còn: {check_result['points_available']}",
                    "points_needed": points_cost,
                    "points_available": check_result["points_available"],
                    "service": "ai_book_cover_generation",
                    "action_required": "purchase_points",
                    "purchase_url": "/pricing",
                },
            )

        logger.info(
            f"💰 Points check passed - User: {user_id}, Cost: {points_cost} points"
        )

        # Initialize Gemini service
        gemini_service = GeminiBookCoverService()

        # Generate image
        result = await gemini_service.generate_book_cover(
            title=request.title,
            author=request.author,
            description=request.prompt,
            style=request.style,
            resolution=request.resolution or "1K",
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"✅ Generated book cover for user {user_id} in {generation_time_ms}ms"
        )

        # ===== STEP 2: Deduct points after success =====
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_cost,
                service="ai_book_cover_generation",
                resource_id=f"book_cover_{int(time.time())}",
                description=f"AI book cover: {request.title}",
            )
            logger.info(f"💸 Deducted {points_cost} points for book cover generation")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")
            # Don't fail the request, just log the error

        return GenerateBookCoverResponse(
            success=True,
            image_base64=result["image_base64"],
            prompt_used=result["prompt_used"],
            title=result.get("title"),
            author=result.get("author"),
            style=result.get("style"),
            model=result.get("model"),
            aspect_ratio=result.get("aspect_ratio"),
            resolution=result.get("resolution"),
            timestamp=result.get("timestamp"),
            generation_time_ms=generation_time_ms,
        )

    except ImportError as e:
        logger.error(f"❌ Gemini package not available: {e}")
        return GenerateBookCoverResponse(
            success=False,
            error="Gemini AI service not available. Please install google-genai package.",
        )
    except ValueError as e:
        logger.error(f"❌ Generation error: {e}")
        return GenerateBookCoverResponse(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate book cover: {e}", exc_info=True)
        return GenerateBookCoverResponse(
            success=False,
            error=f"Image generation failed: {str(e)}",
        )


@router.get(
    "/styles",
    summary="Get available book cover styles",
)
async def get_available_styles():
    """
    **Get list of available book cover styles**

    Returns a list of predefined styles that work well for book covers.

    **Authentication:** Not required

    **Response:**
    ```json
    {
        "styles": [
            {
                "name": "fantasy art",
                "description": "Epic fantasy illustrations with magical elements",
                "example": "dragons, castles, magical creatures"
            },
            ...
        ]
    }
    ```
    """
    return {
        "styles": [
            {
                "name": "fantasy art",
                "description": "Epic fantasy illustrations with magical elements",
                "example": "dragons, castles, magical creatures, mystical landscapes",
            },
            {
                "name": "minimalist",
                "description": "Clean, modern design with simple elements",
                "example": "simple shapes, solid colors, typography focus",
            },
            {
                "name": "photorealistic",
                "description": "Realistic photography style",
                "example": "real objects, portraits, natural scenes",
            },
            {
                "name": "watercolor",
                "description": "Soft watercolor paintings",
                "example": "gentle colors, artistic brush strokes, dreamy atmosphere",
            },
            {
                "name": "3D render",
                "description": "Modern 3D graphics and CGI",
                "example": "3D objects, futuristic designs, digital art",
            },
            {
                "name": "vintage",
                "description": "Retro/classic book cover style",
                "example": "old-fashioned typography, aged paper texture, classic designs",
            },
            {
                "name": "abstract",
                "description": "Abstract art and patterns",
                "example": "geometric shapes, color gradients, artistic compositions",
            },
            {
                "name": "comic book",
                "description": "Comic/graphic novel style",
                "example": "bold lines, action scenes, superhero style",
            },
            {
                "name": "professional",
                "description": "Corporate/business style",
                "example": "clean layouts, professional colors, business graphics",
            },
            {
                "name": "horror",
                "description": "Dark, scary, mysterious atmosphere",
                "example": "dark shadows, creepy elements, suspenseful mood",
            },
            {
                "name": "romance",
                "description": "Romantic, emotional, soft colors",
                "example": "couples, flowers, pastel colors, dreamy scenes",
            },
            {
                "name": "sci-fi",
                "description": "Science fiction, futuristic technology",
                "example": "spaceships, aliens, future cities, technology",
            },
        ],
        "total": 12,
    }
