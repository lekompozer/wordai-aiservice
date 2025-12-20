"""
Book Background API Routes
Endpoints for managing book and chapter backgrounds
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Dict, Any, Optional
import logging
import time
import os
from datetime import datetime

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.services.book_background_service import get_book_background_service
from src.services.book_manager import UserBookManager
from src.services.points_service import get_points_service
from src.storage.r2_client import create_r2_client
from src.models.book_background_models import (
    GenerateBackgroundRequest,
    GenerateBackgroundResponse,
    UpdateBookBackgroundRequest,
    UpdateChapterBackgroundRequest,
    BackgroundResponse,
)

logger = logging.getLogger(__name__)

# R2 public URL from environment (same as other services)
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

router = APIRouter(prefix="/api/v1/books", tags=["Book Backgrounds"])

# Separate router for upload endpoint with proper prefix
upload_router = APIRouter(
    prefix="/api/book-backgrounds", tags=["Book Background Upload"]
)

# Separate router for slide backgrounds
slide_router = APIRouter(prefix="/api/slide-backgrounds", tags=["Slide Backgrounds"])

# Initialize services
db_manager = DBManager()
db = db_manager.db
book_manager = UserBookManager(db)

# Constants
POINTS_COST_BACKGROUND = 2  # Same as book cover generation


# ==================== BOOK BACKGROUND ENDPOINTS ====================


@router.post(
    "/{book_id}/background/generate",
    response_model=GenerateBackgroundResponse,
    summary="Generate AI background for book",
)
async def generate_book_background(
    book_id: str,
    request: GenerateBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Generate AI background for book using Gemini 3 Pro Image

    **Authentication:** Required (Owner only)

    **Cost:** 2 points per generation

    **Request Body:**
    - prompt: Detailed background description (10-500 chars)
    - aspect_ratio: Default "3:4" for A4 portrait
    - style: Optional style modifier (minimalist, modern, abstract, etc.)

    **Returns:**
    - success: Generation status
    - image_url: R2 public URL
    - r2_key: Storage key
    - file_id: Library file ID
    - prompt_used: Full prompt sent to AI
    - generation_time_ms: Generation time
    - points_deducted: Points cost
    - ai_metadata: Generation metadata

    **Errors:**
    - 402: Insufficient points
    - 403: Not book owner
    - 404: Book not found
    - 500: Generation failed
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Book not found"
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can generate background",
            )

        # Check points availability first (but DON'T deduct yet)
        points_service = get_points_service()
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=POINTS_COST_BACKGROUND,
            service="ai_background_generation",
        )

        if not check["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để tạo background. Cần: {POINTS_COST_BACKGROUND}, Còn: {check['points_available']}",
                    "points_needed": POINTS_COST_BACKGROUND,
                    "points_available": check["points_available"],
                },
            )

        logger.info(f"🎨 User {user_id} generating AI background for book {book_id}")

        # Generate background (may fail with 503 or other errors)
        bg_service = get_book_background_service(db)
        result = await bg_service.generate_ai_background(user_id, request)

        # Only deduct points AFTER successful generation
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_BACKGROUND,
            service="ai_background_generation",
            resource_id=f"bg_{book_id}",
            description=f"AI background: {request.prompt[:50]}",
        )

        logger.info(f"✅ Generated AI background for book {book_id}")

        return GenerateBackgroundResponse(
            success=True,
            image_url=result["image_url"],
            r2_key=result["r2_key"],
            file_id=result["file_id"],
            prompt_used=result["prompt_used"],
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_COST_BACKGROUND,
            ai_metadata=result["ai_metadata"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Background generation failed: {str(e)}",
        )


@router.put(
    "/{book_id}/background",
    response_model=BackgroundResponse,
    summary="Update book background",
)
async def update_book_background(
    book_id: str,
    request: UpdateBookBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update book background configuration

    **Authentication:** Required (Owner only)

    **Request Body:**
    - background_config: Full background configuration object

    **Returns:**
    - success: Update status
    - background_config: Updated configuration
    - message: Success message

    **Errors:**
    - 403: Not book owner
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"📝 User {user_id} updating background for book {book_id} (type: {request.background_config.type})"
        )

        bg_service = get_book_background_service(db)
        result = bg_service.update_book_background(
            book_id, user_id, request.background_config
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or not authorized",
            )

        return BackgroundResponse(
            success=True,
            background_config=request.background_config,
            message="Book background updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update book background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update background: {str(e)}",
        )


@router.get(
    "/{book_id}/background",
    summary="Get book background",
)
async def get_book_background(
    book_id: str,
    current_user: Optional[Dict[str, Any]] = None,
):
    """
    Get book background configuration

    **Authentication:** Optional (public for published books)

    **Returns:**
    - book_id: Book ID
    - background_config: Background configuration or null

    **Errors:**
    - 404: Book not found
    """
    try:
        # Verify book exists
        book = book_manager.get_book(book_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Book not found"
            )

        bg_service = get_book_background_service(db)
        config = bg_service.get_book_background(book_id)

        return {"book_id": book_id, "background_config": config}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get book background: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get background",
        )


@router.delete(
    "/{book_id}/background",
    summary="Delete book background",
)
async def delete_book_background(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Reset book background to default (remove background_config)

    **Authentication:** Required (Owner only)

    **Returns:**
    - success: Deletion status
    - message: Success message

    **Errors:**
    - 403: Not book owner
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(f"🗑️  User {user_id} deleting background for book {book_id}")

        bg_service = get_book_background_service(db)
        success = bg_service.delete_book_background(book_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or not authorized",
            )

        return {"success": True, "message": "Book background reset to default"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete book background: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete background",
        )


# ==================== CHAPTER BACKGROUND ENDPOINTS ====================


@router.put(
    "/{book_id}/chapters/{chapter_id}/background",
    summary="Update chapter background",
)
async def update_chapter_background(
    book_id: str,
    chapter_id: str,
    request: UpdateChapterBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update chapter background configuration

    **Authentication:** Required (Owner only)

    **Request Body:**
    - use_book_background: true (inherit) or false (custom)
    - background_config: Required if use_book_background=false

    **Returns:**
    - success: Update status
    - chapter_id: Chapter ID
    - use_book_background: Inheritance flag
    - background_config: Configuration
    - message: Success message

    **Errors:**
    - 400: Invalid request (missing config when use_book_background=false)
    - 403: Not book owner
    - 404: Chapter or book not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"📝 User {user_id} updating background for chapter {chapter_id} (use_book: {request.use_book_background})"
        )

        bg_service = get_book_background_service(db)
        result = bg_service.update_chapter_background(
            book_id,
            chapter_id,
            user_id,
            request.use_book_background,
            request.background_config,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter or book not found, or not authorized",
            )

        return {
            "success": True,
            "chapter_id": chapter_id,
            "use_book_background": request.use_book_background,
            "background_config": request.background_config,
            "message": "Chapter background updated successfully",
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to update chapter background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chapter background: {str(e)}",
        )


@router.get(
    "/{book_id}/chapters/{chapter_id}/background",
    summary="Get chapter background",
)
async def get_chapter_background(
    book_id: str,
    chapter_id: str,
    current_user: Optional[Dict[str, Any]] = None,
):
    """
    Get chapter background (with fallback to book background)

    **Authentication:** Optional (public for published books)

    **Returns:**
    - chapter_id: Chapter ID
    - use_book_background: Inheritance flag
    - background_config: Configuration (from chapter or inherited from book)
    - inherited_from_book: True if using book background

    **Errors:**
    - 404: Chapter not found
    """
    try:
        bg_service = get_book_background_service(db)
        result = bg_service.get_chapter_background(book_id, chapter_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter background: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chapter background",
        )


@router.delete(
    "/{book_id}/chapters/{chapter_id}/background",
    summary="Reset chapter background",
)
async def delete_chapter_background(
    book_id: str,
    chapter_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Reset chapter background to use book background

    **Authentication:** Required (Owner only)

    **Returns:**
    - success: Deletion status
    - message: Success message

    **Errors:**
    - 403: Not book owner
    - 404: Chapter or book not found
    """
    try:
        user_id = current_user["uid"]

        logger.info(
            f"🗑️  User {user_id} resetting background for chapter {chapter_id} to use book"
        )

        bg_service = get_book_background_service(db)
        success = bg_service.delete_chapter_background(book_id, chapter_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter or book not found, or not authorized",
            )

        return {
            "success": True,
            "message": "Chapter background reset to use book background",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete chapter background: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chapter background",
        )


# ==================== BACKGROUND IMAGE UPLOAD ====================


@upload_router.post("/upload-background")
async def upload_background_image(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Upload custom background image to R2 storage

    Returns R2 URL that can be used with custom_image background type

    **File Requirements:**
    - Format: JPG, PNG, WebP
    - Max size: 10MB
    - Recommended: High resolution for A4 pages (1754x2480px for 3:4)
    """
    try:
        user_id = current_user.get("uid")

        # Validate file type
        allowed_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {file.content_type}. Allowed: JPG, PNG, WebP",
            )

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large: {file_size / (1024*1024):.2f}MB. Max: 10MB",
            )

        logger.info(
            f"📤 Uploading background image for user {user_id}: {file.filename} ({file_size / 1024:.2f}KB)"
        )

        # Generate R2 key
        timestamp = int(time.time())
        file_ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        r2_key = f"backgrounds/{user_id}/bg_{timestamp}.{file_ext}"

        # Upload to R2
        r2_client = create_r2_client()
        await r2_client.upload_file_from_bytes(
            file_bytes=file_content,
            remote_path=r2_key,
            content_type=file.content_type,
        )

        # Generate public URL (using R2_PUBLIC_URL env variable)
        image_url = f"{R2_PUBLIC_URL}/{r2_key}"

        # Save to library_files collection
        library_file = {
            "user_id": user_id,
            "file_url": image_url,
            "r2_key": r2_key,
            "file_type": "background",
            "file_name": file.filename,
            "content_type": file.content_type,
            "file_size": file_size,
            "created_at": datetime.utcnow(),
            "metadata": {
                "upload_type": "custom_background",
                "original_filename": file.filename,
            },
        }

        result = db.library_files.insert_one(library_file)
        file_id = str(result.inserted_id)

        logger.info(f"✅ Background uploaded: {image_url} (Library ID: {file_id})")

        return {
            "success": True,
            "image_url": image_url,
            "r2_key": r2_key,
            "file_id": file_id,
            "file_size": file_size,
            "content_type": file.content_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to upload background: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload background image",
        )


# ==================== SLIDE BACKGROUND GENERATION ENDPOINT ====================


@slide_router.post(
    "/generate",
    response_model=GenerateBackgroundResponse,
    summary="Generate AI background for presentation slides",
)
async def generate_slide_background(
    request: GenerateBackgroundRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Generate AI background specifically optimized for presentation slides

    **Authentication:** Required

    **Cost:** 2 points per generation

    **Request Body:**
    - prompt: Detailed background description (10-500 chars)
    - aspect_ratio: Default "16:9" for slides (can use "3:4" for portrait)
    - style: Presentation style (business, startup, corporate, education, academic, creative, minimalist, modern)
    - generation_type: Must be "slide_background"

    **Optimized Styles:**
    - **business**: Professional corporate presentations with clean design
    - **startup**: Dynamic pitch decks with bold colors and modern shapes
    - **corporate**: Formal presentations with trustworthy aesthetics
    - **education**: Learning-focused designs with clear layouts
    - **academic**: Scholarly presentations for research/conferences
    - **creative**: Artistic and expressive designs
    - **minimalist**: Clean, simple with lots of white space
    - **modern**: Contemporary sleek designs

    **Returns:**
    - success: Generation status
    - image_url: R2 public URL
    - r2_key: Storage key
    - file_id: Library file ID
    - prompt_used: Full optimized prompt sent to AI
    - generation_time_ms: Generation time
    - points_deducted: Points cost (2)
    - ai_metadata: Generation metadata

    **Errors:**
    - 402: Insufficient points
    - 404: Resource not found
    - 500: Generation failed

    **Example:**
    ```json
    {
      "prompt": "Modern tech startup background with gradient blue tones",
      "aspect_ratio": "16:9",
      "style": "startup",
      "generation_type": "slide_background"
    }
    ```
    """
    try:
        user_id = current_user["uid"]

        # Override generation_type to ensure it's slide_background
        request.generation_type = "slide_background"

        # Default to 16:9 for slides if not specified
        if not request.aspect_ratio or request.aspect_ratio == "3:4":
            request.aspect_ratio = "16:9"

        # Check points availability first (but DON'T deduct yet)
        points_service = get_points_service()
        check = await points_service.check_sufficient_points(
            user_id=user_id,
            points_needed=POINTS_COST_BACKGROUND,
            service="slide_background_generation",
        )

        if not check["has_points"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "INSUFFICIENT_POINTS",
                    "message": f"Không đủ điểm để tạo slide background. Cần: {POINTS_COST_BACKGROUND}, Còn: {check['points_available']}",
                    "points_needed": POINTS_COST_BACKGROUND,
                    "points_available": check["points_available"],
                },
            )

        logger.info(f"🎨 User {user_id} generating slide background")
        logger.info(f"   Style: {request.style or 'default'}")
        logger.info(f"   Aspect Ratio: {request.aspect_ratio}")

        # Generate background (may fail with 503 or other errors)
        bg_service = get_book_background_service(db)
        result = await bg_service.generate_ai_background(user_id, request)

        # Only deduct points AFTER successful generation
        await points_service.deduct_points(
            user_id=user_id,
            amount=POINTS_COST_BACKGROUND,
            service="slide_background_generation",
            resource_id=f"slide_bg_{result['file_id']}",
            description=f"Slide background: {request.prompt[:50]}",
        )

        logger.info(
            f"✅ Generated slide background (style: {request.style or 'default'})"
        )

        return GenerateBackgroundResponse(
            success=True,
            image_url=result["image_url"],
            r2_key=result["r2_key"],
            file_id=result["file_id"],
            prompt_used=result["prompt_used"],
            generation_time_ms=result["generation_time_ms"],
            points_deducted=POINTS_COST_BACKGROUND,
            ai_metadata=result["ai_metadata"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate slide background: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Slide background generation failed: {str(e)}",
        )
