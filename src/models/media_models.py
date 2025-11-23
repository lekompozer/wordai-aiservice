"""
Media Upload Models

Models for pre-signed URL image/video uploads to R2 storage
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class ResourceType(str, Enum):
    """Resource types that can have media uploads"""

    DOCUMENT = "document"
    CHAPTER = "chapter"


class PresignedUploadRequest(BaseModel):
    """Request model for pre-signed upload URL"""

    resource_type: ResourceType = Field(
        ..., description="Type of resource (document or chapter)"
    )
    resource_id: str = Field(..., description="UUID of the document or chapter")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type (must be image/*)")
    file_size: int = Field(..., description="File size in bytes", gt=0)

    @validator("content_type")
    def validate_content_type(cls, v):
        """Validate that content type is an image"""
        if not v.startswith("image/"):
            raise ValueError("content_type must be an image MIME type (image/*)")

        # Allowed image types
        allowed_types = {
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/svg+xml",
        }

        if v not in allowed_types:
            raise ValueError(
                f"Unsupported image type. Allowed: {', '.join(allowed_types)}"
            )

        return v

    @validator("file_size")
    def validate_file_size(cls, v):
        """Validate file size (max 10MB)"""
        max_size = 10 * 1024 * 1024  # 10MB
        if v > max_size:
            raise ValueError(
                f"File size {v / 1024 / 1024:.2f}MB exceeds maximum of 10MB"
            )
        return v

    @validator("filename")
    def validate_filename(cls, v):
        """Validate filename"""
        if not v or len(v.strip()) == 0:
            raise ValueError("filename cannot be empty")

        if len(v) > 255:
            raise ValueError("filename too long (max 255 characters)")

        return v


class PresignedUploadResponse(BaseModel):
    """Response model for pre-signed upload URL"""

    upload_url: str = Field(..., description="Pre-signed URL for PUT request")
    cdn_url: str = Field(..., description="Public CDN URL after upload")
    upload_id: str = Field(..., description="Tracking ID for this upload")
    expires_at: datetime = Field(..., description="Pre-signed URL expiration time")


class MediaMetadata(BaseModel):
    """Media metadata stored in database (optional tracking)"""

    media_id: str = Field(..., description="Unique media ID (UUID)")
    resource_type: ResourceType = Field(..., description="Resource type")
    resource_id: str = Field(..., description="Resource ID")
    user_id: str = Field(..., description="Uploader's Firebase UID")
    cdn_url: str = Field(..., description="Public CDN URL")
    r2_key: str = Field(..., description="R2 storage key")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Upload timestamp"
    )
    is_deleted: bool = Field(False, description="Soft delete flag")
