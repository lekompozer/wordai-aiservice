"""
Media Upload Service

Service for generating pre-signed URLs for direct R2 image uploads
"""

import os
import uuid
import logging
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException
import boto3
from botocore.exceptions import ClientError
from pymongo.database import Database

from src.database.db_manager import DBManager
from src.models.media_models import (
    ResourceType,
    PresignedUploadRequest,
    PresignedUploadResponse,
    MediaMetadata,
)

logger = logging.getLogger(__name__)


class MediaUploadService:
    """Service for generating pre-signed upload URLs"""

    # Pre-signed URL expiration time (15 minutes)
    PRESIGNED_URL_EXPIRATION = 15 * 60  # seconds

    # Maximum file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def __init__(self):
        """Initialize media upload service"""
        # Initialize database
        db_manager = DBManager()
        self.db: Database = db_manager.db
        self.documents_collection = self.db["documents"]
        self.chapters_collection = self.db["online_book_chapters"]
        self.media_collection = self.db["media_uploads"]

        # R2 Storage configuration
        self.r2_account_id = os.getenv("R2_ACCOUNT_ID")
        self.r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
        self.r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.r2_bucket_name = os.getenv("R2_BUCKET_NAME", "wordai")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

        # Initialize R2 client
        self.r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{self.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            region_name="auto",
        )

        # Create indexes
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes"""
        try:
            self.media_collection.create_index(
                [("resource_type", 1), ("resource_id", 1), ("is_deleted", 1)]
            )
            self.media_collection.create_index([("user_id", 1), ("created_at", -1)])
            self.media_collection.create_index("media_id", unique=True)
            logger.info("Media collection indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating media indexes: {e}")

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for R2 storage

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators and dangerous characters
        safe_filename = "".join(
            c if c.isalnum() or c in (".", "-", "_") else "_" for c in filename
        )

        # Ensure filename is not empty
        if not safe_filename or safe_filename.startswith("."):
            safe_filename = (
                f"file_{uuid.uuid4().hex[:8]}.{safe_filename.split('.')[-1]}"
            )

        return safe_filename

    def _generate_r2_key(
        self, resource_type: ResourceType, resource_id: str, filename: str
    ) -> str:
        """
        Generate R2 storage key

        Format: {resource_type}s/{resource_id}/images/{timestamp}-{uuid}-{filename}

        Args:
            resource_type: Type of resource
            resource_id: Resource ID
            filename: Original filename

        Returns:
            R2 storage key
        """
        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)

        # Generate unique filename with timestamp and UUID
        timestamp = int(time.time())
        unique_id = uuid.uuid4().hex[:8]
        unique_filename = f"{timestamp}-{unique_id}-{safe_filename}"

        # Generate key
        if resource_type == ResourceType.DOCUMENT:
            r2_key = f"documents/{resource_id}/images/{unique_filename}"
        elif resource_type == ResourceType.CHAPTER:
            r2_key = f"chapters/{resource_id}/images/{unique_filename}"
        else:
            raise ValueError(f"Invalid resource_type: {resource_type}")

        return r2_key

    def _verify_resource_ownership(
        self, user_id: str, resource_type: ResourceType, resource_id: str
    ) -> bool:
        """
        Verify that user owns the resource

        Args:
            user_id: User's Firebase UID
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            True if user owns resource

        Raises:
            HTTPException: If resource not found or user doesn't have permission
        """
        if resource_type == ResourceType.DOCUMENT:
            collection = self.documents_collection
            query = {"document_id": resource_id, "user_id": user_id}
        elif resource_type == ResourceType.CHAPTER:
            collection = self.chapters_collection
            # For chapters, check if user owns the book
            chapter = collection.find_one({"chapter_id": resource_id})
            if not chapter:
                raise HTTPException(status_code=404, detail="Chapter not found")

            book_id = chapter.get("book_id")
            if not book_id:
                raise HTTPException(
                    status_code=500, detail="Chapter has no associated book"
                )

            # Check book ownership
            book = self.db["online_books"].find_one({"book_id": book_id})
            if not book:
                raise HTTPException(status_code=404, detail="Book not found")

            if book.get("user_id") != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to upload images to this chapter",
                )

            return True
        else:
            raise ValueError(f"Invalid resource_type: {resource_type}")

        resource = collection.find_one(query)
        if not resource:
            resource_name = (
                "Document" if resource_type == ResourceType.DOCUMENT else "Chapter"
            )
            raise HTTPException(
                status_code=404,
                detail=f"{resource_name} not found or you don't have permission",
            )

        return True

    async def generate_presigned_upload_url(
        self, user_id: str, request: PresignedUploadRequest
    ) -> PresignedUploadResponse:
        """
        Generate pre-signed URL for direct R2 upload

        Args:
            user_id: User's Firebase UID
            request: Upload request with resource info

        Returns:
            PresignedUploadResponse with upload URL and CDN URL

        Raises:
            HTTPException: If validation fails or permission denied
        """
        # Verify resource ownership
        self._verify_resource_ownership(
            user_id, request.resource_type, request.resource_id
        )

        # Generate R2 key
        r2_key = self._generate_r2_key(
            request.resource_type, request.resource_id, request.filename
        )

        # Generate CDN URL
        cdn_url = f"{self.r2_public_url}/{r2_key}"

        # Generate pre-signed URL
        try:
            upload_url = self.r2_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.r2_bucket_name,
                    "Key": r2_key,
                    "ContentType": request.content_type,
                },
                ExpiresIn=self.PRESIGNED_URL_EXPIRATION,
            )

            # Generate upload ID for tracking
            upload_id = str(uuid.uuid4())

            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(
                seconds=self.PRESIGNED_URL_EXPIRATION
            )

            # Store metadata in database (for tracking)
            media_metadata = MediaMetadata(
                media_id=upload_id,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                user_id=user_id,
                cdn_url=cdn_url,
                r2_key=r2_key,
                filename=request.filename,
                content_type=request.content_type,
                file_size=request.file_size,
                created_at=datetime.utcnow(),
                is_deleted=False,
            )

            self.media_collection.insert_one(media_metadata.dict())

            logger.info(
                f"Generated pre-signed URL for {request.resource_type} {request.resource_id}: {r2_key}"
            )

            return PresignedUploadResponse(
                upload_url=upload_url,
                cdn_url=cdn_url,
                upload_id=upload_id,
                expires_at=expires_at,
            )

        except ClientError as e:
            logger.error(f"Failed to generate pre-signed URL: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to generate upload URL: {str(e)}"
            )

    async def list_resource_media(
        self, user_id: str, resource_type: ResourceType, resource_id: str
    ) -> list:
        """
        List all media for a resource

        Args:
            user_id: User's Firebase UID
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            List of media metadata
        """
        # Verify ownership
        self._verify_resource_ownership(user_id, resource_type, resource_id)

        # Query media
        media = list(
            self.media_collection.find(
                {
                    "resource_type": resource_type.value,
                    "resource_id": resource_id,
                    "is_deleted": False,
                }
            ).sort("created_at", -1)
        )

        return media

    async def delete_media(self, user_id: str, media_id: str) -> bool:
        """
        Delete media by ID

        Args:
            user_id: User's Firebase UID
            media_id: Media ID to delete

        Returns:
            True if deleted successfully

        Raises:
            HTTPException: If media not found or permission denied
        """
        # Find media
        media = self.media_collection.find_one({"media_id": media_id})

        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        # Verify ownership
        if media.get("user_id") != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have permission to delete this media"
            )

        # Delete from R2 (optional - keep for now)
        try:
            self.r2_client.delete_object(
                Bucket=self.r2_bucket_name, Key=media["r2_key"]
            )
            logger.info(f"Deleted media from R2: {media['r2_key']}")
        except ClientError as e:
            logger.warning(f"Failed to delete from R2: {e}")

        # Soft delete in database
        self.media_collection.update_one(
            {"media_id": media_id},
            {"$set": {"is_deleted": True, "updated_at": datetime.utcnow()}},
        )

        logger.info(f"Media deleted: {media_id} for user {user_id}")
        return True
