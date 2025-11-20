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
from src.services.ai_image_service import AIImageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books/ai/cover", tags=["AI Book Cover"])


@router.post(
    "/generate",
    response_model=GenerateBookCoverResponse,
    summary="Generate book cover using AI (gpt-image-1)",
)
async def generate_book_cover_ai(
    request: GenerateBookCoverRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Generate book cover image using OpenAI gpt-image-1 model**

    Generates a custom book cover based on text description.
    Users can re-generate with different styles.

    **Features:**
    - Uses OpenAI's multimodal gpt-image-1 model
    - Supports custom styles (fantasy art, minimalist, photorealistic, etc.)
    - Returns base64 encoded PNG image
    - Can be regenerated multiple times with different prompts/styles

    **Authentication:** Required

    **Request Body:**
    ```json
    {
        "prompt": "A fantasy book cover with a magical castle in the sky surrounded by dragons",
        "style": "fantasy art"
    }
    ```

    **Available Styles:**
    - `fantasy art` - Epic fantasy illustrations
    - `minimalist` - Clean, modern design
    - `photorealistic` - Realistic photography style
    - `watercolor` - Soft watercolor paintings
    - `3D render` - Modern 3D graphics
    - `vintage` - Retro/classic book cover style
    - `abstract` - Abstract art
    - `comic book` - Comic/graphic novel style
    - `professional` - Corporate/business style

    **Response:**
    - `success`: True if generation succeeded
    - `image_base64`: PNG image in base64 format (can be used directly in <img> tags)
    - `prompt_used`: Full prompt sent to AI (includes style)
    - `timestamp`: Generation time
    - `model`: AI model used (gpt-4.1-mini)
    - `generation_time_ms`: Time taken in milliseconds

    **Example Usage:**
    1. Generate initial cover: `POST /api/v1/books/ai/cover/generate`
    2. If not satisfied, regenerate with different prompt/style
    3. Decode base64 image client-side or save to file
    4. Upload to book using existing image upload endpoints

    **Rate Limits:**
    - Max 10 generations per minute per user
    - Each generation takes ~5-15 seconds

    **Error Responses:**
    - `success: false` with `error` field containing error message
    - Common errors:
      - OpenAI API key not configured
      - Invalid prompt (too short/long)
      - API rate limit exceeded
      - Service temporarily unavailable
    """
    start_time = time.time()

    try:
        user_id = current_user["uid"]
        logger.info(
            f"🎨 User {user_id} generating book cover: {request.prompt[:50]}..."
        )

        # Initialize AI service
        ai_service = AIImageService()

        # Generate image
        result = await ai_service.generate_book_cover(
            prompt=request.prompt,
            style=request.style,
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"✅ Generated book cover for user {user_id} in {generation_time_ms}ms"
        )

        return GenerateBookCoverResponse(
            success=True,
            image_base64=result["image_base64"],
            prompt_used=result["prompt_used"],
            style=result.get("style"),
            model=result.get("model"),
            timestamp=result.get("timestamp"),
            generation_time_ms=generation_time_ms,
        )

    except ImportError as e:
        logger.error(f"❌ OpenAI not available: {e}")
        return GenerateBookCoverResponse(
            success=False,
            error="AI image generation service not available. Please install OpenAI package.",
        )
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
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
