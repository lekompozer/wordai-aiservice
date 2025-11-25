"""
Book Background API Routes
Endpoints for managing book and chapter backgrounds
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
import logging

from src.middleware.firebase_auth import get_current_user
from src.database.db_manager import DBManager
from src.services.book_background_service import get_book_background_service
from src.services.book_manager import UserBookManager
from src.services.points_service import get_points_service
from src.models.book_background_models import (
    GenerateBackgroundRequest,
    GenerateBackgroundResponse,
    UpdateBookBackgroundRequest,
    UpdateChapterBackgroundRequest,
    BackgroundResponse,
    ThemesResponse,
    ThemeItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books", tags=["Book Backgrounds"])

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

        # Check and deduct points
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

        # Generate background
        bg_service = get_book_background_service(db)
        result = await bg_service.generate_ai_background(user_id, request)

        # Deduct points
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


# ==================== PRESET THEMES ENDPOINT ====================


@router.get(
    "/backgrounds/themes",
    response_model=ThemesResponse,
    tags=["Background Themes"],
    summary="Get available background themes",
)
async def get_background_themes():
    """
    Get list of available preset background themes

    **Authentication:** Not required

    **Returns:**
    - themes: Array of theme objects with id, name, preview_colors, type, direction

    **Available Themes:**
    - ocean: Ocean Blue gradient
    - forest: Forest Green gradient
    - sunset: Warm Sunset gradient
    - minimal: Minimal White solid
    - dark: Dark Mode solid
    - light: Light Gray solid
    - tech: Tech Purple gradient
    - vintage: Vintage Sepia gradient
    """
    themes = [
        ThemeItem(
            id="ocean",
            name="Ocean Blue",
            preview_colors=["#0077be", "#1e90ff", "#87ceeb"],
            type="gradient",
            direction="to-br",
        ),
        ThemeItem(
            id="forest",
            name="Forest Green",
            preview_colors=["#228b22", "#32cd32", "#90ee90"],
            type="gradient",
            direction="to-br",
        ),
        ThemeItem(
            id="sunset",
            name="Warm Sunset",
            preview_colors=["#ff6b6b", "#ee5a6f", "#c44569"],
            type="gradient",
            direction="to-br",
        ),
        ThemeItem(
            id="minimal",
            name="Minimal White",
            preview_colors=["#ffffff"],
            type="solid",
            direction=None,
        ),
        ThemeItem(
            id="dark",
            name="Dark Mode",
            preview_colors=["#1f2937"],
            type="solid",
            direction=None,
        ),
        ThemeItem(
            id="light",
            name="Light Gray",
            preview_colors=["#f9fafb"],
            type="solid",
            direction=None,
        ),
        ThemeItem(
            id="tech",
            name="Tech Purple",
            preview_colors=["#667eea", "#764ba2"],
            type="gradient",
            direction="to-br",
        ),
        ThemeItem(
            id="vintage",
            name="Vintage Sepia",
            preview_colors=["#f4e7d7", "#d4a574", "#8b6f47"],
            type="gradient",
            direction="to-br",
        ),
    ]

    return ThemesResponse(themes=themes)
