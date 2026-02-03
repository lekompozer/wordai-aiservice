"""
Font Management API Routes

Endpoints for custom font upload and management
"""

import logging
from typing import List
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status,
)

from src.middleware.firebase_auth import get_current_user
from src.services.font_upload_service import FontUploadService
from src.models.font_models import (
    FontFamily,
    FontResponse,
    FontListResponse,
    FontDeleteResponse,
    FontFaceResponse,
)

# System default fonts (Google Fonts + Apple San Francisco Pro)
SYSTEM_DEFAULT_FONTS = [
    # Sans-serif fonts
    {
        "font_name": "San Francisco Pro",
        "font_family": "sans-serif",
        "description": "Apple's system font - clean and modern",
        "google_fonts_family": None,  # Not on Google Fonts (system font)
        "is_system": True,
        "css_family": "-apple-system, BlinkMacSystemFont, 'San Francisco', 'SF Pro Display', 'SF Pro Text'",
    },
    {
        "font_name": "Inter",
        "font_family": "sans-serif",
        "description": "Modern and highly legible sans-serif",
        "google_fonts_family": "Inter",
        "is_system": False,
    },
    {
        "font_name": "Roboto",
        "font_family": "sans-serif",
        "description": "Google's signature sans-serif font",
        "google_fonts_family": "Roboto",
        "is_system": False,
    },
    {
        "font_name": "Open Sans",
        "font_family": "sans-serif",
        "description": "Clean and friendly sans-serif",
        "google_fonts_family": "Open+Sans",
        "is_system": False,
    },
    {
        "font_name": "Lato",
        "font_family": "sans-serif",
        "description": "Warm and stable sans-serif",
        "google_fonts_family": "Lato",
        "is_system": False,
    },
    # Serif fonts
    {
        "font_name": "Merriweather",
        "font_family": "serif",
        "description": "Classic serif designed for screens",
        "google_fonts_family": "Merriweather",
        "is_system": False,
    },
    {
        "font_name": "Lora",
        "font_family": "serif",
        "description": "Elegant and readable serif",
        "google_fonts_family": "Lora",
        "is_system": False,
    },
    {
        "font_name": "Playfair Display",
        "font_family": "serif",
        "description": "High-contrast serif for titles",
        "google_fonts_family": "Playfair+Display",
        "is_system": False,
    },
    # Monospace fonts
    {
        "font_name": "Roboto Mono",
        "font_family": "monospace",
        "description": "Google's monospace font",
        "google_fonts_family": "Roboto+Mono",
        "is_system": False,
    },
    {
        "font_name": "Source Code Pro",
        "font_family": "monospace",
        "description": "Adobe's coding font",
        "google_fonts_family": "Source+Code+Pro",
        "is_system": False,
    },
    # Vietnamese fonts
    {
        "font_name": "Noto Sans",
        "font_family": "sans-serif",
        "description": "Google's font with excellent Vietnamese support",
        "google_fonts_family": "Noto+Sans",
        "is_system": False,
    },
    {
        "font_name": "Noto Serif",
        "font_family": "serif",
        "description": "Serif variant with Vietnamese support",
        "google_fonts_family": "Noto+Serif",
        "is_system": False,
    },
]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fonts", tags=["fonts"])


def get_font_service() -> FontUploadService:
    """Get font upload service instance"""
    return FontUploadService()


@router.post(
    "/upload",
    response_model=FontResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload custom font",
    description="Upload a custom font file (TTF/WOFF/WOFF2) for use in documents",
)
async def upload_font(
    file: UploadFile = File(
        ...,
        description="Font file (TTF/OTF/WOFF/WOFF2, max 5MB)",
    ),
    font_name: str = Form(
        ...,
        description="Display name for the font",
        min_length=1,
        max_length=100,
    ),
    font_family: FontFamily = Form(
        ...,
        description="Font family category (serif/sans-serif/monospace/display/handwriting)",
    ),
    description: str = Form(
        None,
        description="Optional description of the font",
        max_length=500,
    ),
    current_user: dict = Depends(get_current_user),
    font_service: FontUploadService = Depends(get_font_service),
):
    """
    Upload a custom font for use in documents.

    **Requirements:**
    - File format: TTF, OTF, WOFF, or WOFF2
    - Maximum file size: 5MB
    - Font name must be unique for the user

    **Returns:**
    - Font metadata including public URL for @font-face usage
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        font_response = await font_service.upload_font(
            user_id=user_id,
            file=file,
            font_name=font_name,
            font_family=font_family,
            description=description,
        )

        return font_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading font: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload font: {str(e)}",
        )


@router.get(
    "",
    response_model=FontListResponse,
    summary="List user fonts",
    description="Get list of all custom fonts uploaded by the current user",
)
async def list_fonts(
    current_user: dict = Depends(get_current_user),
    font_service: FontUploadService = Depends(get_font_service),
):
    """
    List all custom fonts uploaded by the current user.

    **Returns:**
    - List of font metadata sorted by creation date (newest first)
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        fonts = await font_service.list_user_fonts(user_id)

        return FontListResponse(fonts=fonts, total=len(fonts))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing fonts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list fonts: {str(e)}",
        )


@router.get(
    "/system-defaults",
    summary="Get system default fonts",
    description="Get list of built-in system fonts (Google Fonts + Apple San Francisco Pro)",
)
async def get_system_default_fonts():
    """
    Get list of system default fonts available without upload.

    **Returns:**
    - List of default fonts including:
      - San Francisco Pro (Apple system font)
      - Google Fonts (Inter, Roboto, etc.)
      - Vietnamese-optimized fonts (Noto Sans/Serif)

    **Usage:**
    - Use `google_fonts_family` to construct Google Fonts CDN URL
    - Use `css_family` for direct CSS font-family value
    - System fonts (is_system=true) work on Apple devices without loading
    """
    return {
        "fonts": SYSTEM_DEFAULT_FONTS,
        "total": len(SYSTEM_DEFAULT_FONTS),
        "google_fonts_base_url": "https://fonts.googleapis.com/css2?family=",
    }


@router.delete(
    "/{font_id}",
    response_model=FontDeleteResponse,
    summary="Delete custom font",
    description="Delete a custom font by ID",
)
async def delete_font(
    font_id: str,
    current_user: dict = Depends(get_current_user),
    font_service: FontUploadService = Depends(get_font_service),
):
    """
    Delete a custom font by ID.

    **Requirements:**
    - User must own the font

    **Returns:**
    - Success message with deleted font ID
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        success = await font_service.delete_font(user_id, font_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete font",
            )

        return FontDeleteResponse(
            success=True,
            message="Font deleted successfully",
            font_id=font_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting font: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete font: {str(e)}",
        )


@router.get(
    "/css",
    response_model=FontFaceResponse,
    summary="Get CSS @font-face rules",
    description="Get CSS @font-face rules for all user fonts",
)
async def get_font_face_css(
    current_user: dict = Depends(get_current_user),
    font_service: FontUploadService = Depends(get_font_service),
):
    """
    Get CSS @font-face rules for all custom fonts.

    **Usage:**
    Inject the returned CSS rules into your document's <style> tag
    to make custom fonts available for use.

    **Returns:**
    - Array of @font-face CSS rules
    - Combined CSS string ready for injection
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        font_face_rules = await font_service.get_font_face_rules(user_id)

        # Combine all rules into single CSS string
        combined_css = "\n\n".join([rule.css_rule for rule in font_face_rules])

        return FontFaceResponse(
            font_face_rules=font_face_rules,
            combined_css=combined_css,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating font-face CSS: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate font-face CSS: {str(e)}",
        )
