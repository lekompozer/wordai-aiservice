"""API routes for quote settings management"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, List

from src.config.database import get_async_database
from src.middleware.firebase_auth import get_current_user
from src.models.settings_models import (
    UpdateQuoteSettingsRequest,
    QuoteSettingsResponse,
    UserQuoteSettings,
)
from src.models.document_generation_models import DocumentTemplate
from src.services.quote_settings_service import QuoteSettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quote-settings", tags=["Quote Settings"])


@router.get("/")
async def get_quote_settings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """Lấy cài đặt báo giá của user hiện tại và danh sách templates"""
    try:
        settings_service = QuoteSettingsService(db)

        # Lấy hoặc tạo settings mặc định nếu chưa có
        settings = await settings_service.get_or_create_user_settings(
            current_user["uid"]
        )

        # Lấy danh sách templates: System templates + User's own templates
        templates_query = {
            "$or": [
                {
                    "user_id": {"$in": [None, "system"]},
                    "is_public": True,
                },  # System templates
                {"user_id": current_user["uid"]},  # User's own templates
            ],
            "is_active": True,
        }
        templates_cursor = db.document_templates.find(templates_query)
        templates_list = await templates_cursor.to_list(length=None)

        # Convert ObjectId to string và tạo DocumentTemplate objects
        templates = []
        for template in templates_list:
            template["_id"] = str(template["_id"])
            templates.append(DocumentTemplate(**template))

        # Trả về response với cả settings và templates
        return {
            "success": True,
            "message": "Lấy cài đặt và templates thành công",
            "data": settings,
            "templates": templates,
        }

    except Exception as e:
        logger.error(f"Error getting quote settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy cài đặt: {str(e)}",
        )


@router.post("/", response_model=QuoteSettingsResponse)
async def update_quote_settings(
    update_request: UpdateQuoteSettingsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """Cập nhật cài đặt báo giá của user"""
    try:
        settings_service = QuoteSettingsService(db)

        # Cập nhật settings
        updated_settings = await settings_service.update_user_settings(
            current_user["uid"], update_request
        )

        return QuoteSettingsResponse(
            success=True, message="Cập nhật cài đặt thành công", data=updated_settings
        )

    except Exception as e:
        logger.error(f"Error updating quote settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi cập nhật cài đặt: {str(e)}",
        )


@router.put("/", response_model=QuoteSettingsResponse)
async def create_or_update_quote_settings(
    update_request: UpdateQuoteSettingsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """Tạo mới hoặc cập nhật cài đặt báo giá (PUT method)"""
    try:
        settings_service = QuoteSettingsService(db)

        # Cập nhật hoặc tạo mới settings
        updated_settings = await settings_service.update_user_settings(
            current_user["uid"], update_request
        )

        return QuoteSettingsResponse(
            success=True, message="Lưu cài đặt thành công", data=updated_settings
        )

    except Exception as e:
        logger.error(f"Error creating/updating quote settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lưu cài đặt: {str(e)}",
        )


@router.delete("/", response_model=QuoteSettingsResponse)
async def delete_quote_settings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_async_database),
):
    """Xóa cài đặt báo giá của user (reset về mặc định)"""
    try:
        settings_service = QuoteSettingsService(db)

        # Xóa settings hiện tại
        deleted = await settings_service.delete_user_settings(current_user["uid"])

        if deleted:
            # Tạo lại settings mặc định
            default_settings = await settings_service.create_default_settings(
                current_user["uid"]
            )

            return QuoteSettingsResponse(
                success=True,
                message="Đã reset cài đặt về mặc định",
                data=default_settings,
            )
        else:
            return QuoteSettingsResponse(
                success=False, message="Không tìm thấy cài đặt để xóa", data=None
            )

    except Exception as e:
        logger.error(f"Error deleting quote settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xóa cài đặt: {str(e)}",
        )
