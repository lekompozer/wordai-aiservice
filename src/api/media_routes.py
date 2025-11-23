"""
Media Upload API Routes

Endpoints for pre-signed URL generation for direct R2 uploads
"""

import logging
from typing import List
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from src.middleware.firebase_auth import get_current_user
from src.services.media_upload_service import MediaUploadService
from src.models.media_models import (
    ResourceType,
    PresignedUploadRequest,
    PresignedUploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/media", tags=["media"])


def get_media_service() -> MediaUploadService:
    """Get media upload service instance"""
    return MediaUploadService()


@router.post(
    "/presign-upload",
    response_model=PresignedUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate pre-signed upload URL",
    description="Generate a pre-signed URL for direct R2 image upload to documents or chapters",
)
async def presign_upload(
    request: PresignedUploadRequest,
    current_user: dict = Depends(get_current_user),
    media_service: MediaUploadService = Depends(get_media_service),
):
    """
    Generate a pre-signed URL for direct image upload to R2 storage.

    **Flow:**
    1. Client requests pre-signed URL with file metadata
    2. Backend verifies user owns the resource (document/chapter)
    3. Backend generates pre-signed URL and CDN URL
    4. Client uploads directly to R2 using pre-signed URL (PUT request)
    5. Client uses CDN URL in Tiptap editor

    **Requirements:**
    - User must own the document or chapter
    - File must be an image (JPEG, PNG, GIF, WebP, SVG)
    - Maximum file size: 10MB
    - Pre-signed URL valid for 15 minutes

    **Returns:**
    - Pre-signed URL for PUT request
    - Public CDN URL for embedding in editor
    - Upload ID for tracking
    - Expiration timestamp
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        response = await media_service.generate_presigned_upload_url(user_id, request)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating pre-signed URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}",
        )


@router.get(
    "/{resource_type}/{resource_id}",
    summary="List resource media",
    description="List all media uploads for a specific document or chapter",
)
async def list_media(
    resource_type: ResourceType,
    resource_id: str,
    current_user: dict = Depends(get_current_user),
    media_service: MediaUploadService = Depends(get_media_service),
):
    """
    List all media uploads for a resource.

    **Returns:**
    - Array of media metadata (CDN URLs, file info, timestamps)
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        media_list = await media_service.list_resource_media(
            user_id, resource_type, resource_id
        )

        return {"media": media_list, "total": len(media_list)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing media: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list media: {str(e)}",
        )


@router.delete(
    "/{media_id}",
    summary="Delete media",
    description="Delete a media upload by ID",
)
async def delete_media(
    media_id: str,
    current_user: dict = Depends(get_current_user),
    media_service: MediaUploadService = Depends(get_media_service),
):
    """
    Delete a media upload by ID.

    **Requirements:**
    - User must own the media

    **Returns:**
    - Success message
    """
    try:
        user_id = current_user.get("uid")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required",
            )

        success = await media_service.delete_media(user_id, media_id)

        return {
            "success": success,
            "message": "Media deleted successfully",
            "media_id": media_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting media: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete media: {str(e)}",
        )
