"""
Document Settings API Routes
Handles document preferences and settings for users
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

from src.config.firebase_config import firebase_config
from src.middleware.auth import verify_firebase_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/document-settings", tags=["Document Settings"])


class DocumentSettings(BaseModel):
    """Document settings model"""

    user_id: str
    language: str = "vi"
    font_family: str = "Times New Roman"
    font_size: int = 12
    line_spacing: float = 1.5
    margin_top: float = 2.5
    margin_bottom: float = 2.5
    margin_left: float = 3.0
    margin_right: float = 3.0
    header_enabled: bool = True
    footer_enabled: bool = True
    page_numbers: bool = True
    watermark: Optional[str] = None


class DocumentSettingsResponse(BaseModel):
    """Document settings response model"""

    success: bool
    settings: Optional[DocumentSettings] = None
    message: str


class DocumentSettingsRequest(BaseModel):
    """Document settings update request"""

    language: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    line_spacing: Optional[float] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    header_enabled: Optional[bool] = None
    footer_enabled: Optional[bool] = None
    page_numbers: Optional[bool] = None
    watermark: Optional[str] = None


@router.get("/", response_model=DocumentSettingsResponse)
async def get_document_settings(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get document settings for the authenticated user
    """
    try:
        user_id = user_data.get("uid")

        # Default settings for now - in a real app, you'd fetch from database
        default_settings = DocumentSettings(
            user_id=user_id,
            language="vi",
            font_family="Times New Roman",
            font_size=12,
            line_spacing=1.5,
            margin_top=2.5,
            margin_bottom=2.5,
            margin_left=3.0,
            margin_right=3.0,
            header_enabled=True,
            footer_enabled=True,
            page_numbers=True,
            watermark=None,
        )

        logger.info(
            f"✅ Retrieved document settings for user: {user_data.get('email', user_id)}"
        )

        return DocumentSettingsResponse(
            success=True,
            settings=default_settings,
            message="Document settings retrieved successfully",
        )

    except Exception as e:
        logger.error(f"❌ Failed to get document settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document settings",
        )


@router.put("/", response_model=DocumentSettingsResponse)
async def update_document_settings(
    settings_request: DocumentSettingsRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update document settings for the authenticated user
    """
    try:
        user_id = user_data.get("uid")

        # In a real app, you'd update the database here
        # For now, just return success with the updated settings

        updated_settings = DocumentSettings(
            user_id=user_id,
            language=settings_request.language or "vi",
            font_family=settings_request.font_family or "Times New Roman",
            font_size=settings_request.font_size or 12,
            line_spacing=settings_request.line_spacing or 1.5,
            margin_top=settings_request.margin_top or 2.5,
            margin_bottom=settings_request.margin_bottom or 2.5,
            margin_left=settings_request.margin_left or 3.0,
            margin_right=settings_request.margin_right or 3.0,
            header_enabled=(
                settings_request.header_enabled
                if settings_request.header_enabled is not None
                else True
            ),
            footer_enabled=(
                settings_request.footer_enabled
                if settings_request.footer_enabled is not None
                else True
            ),
            page_numbers=(
                settings_request.page_numbers
                if settings_request.page_numbers is not None
                else True
            ),
            watermark=settings_request.watermark,
        )

        logger.info(
            f"✅ Updated document settings for user: {user_data.get('email', user_id)}"
        )

        return DocumentSettingsResponse(
            success=True,
            settings=updated_settings,
            message="Document settings updated successfully",
        )

    except Exception as e:
        logger.error(f"❌ Failed to update document settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document settings",
        )
