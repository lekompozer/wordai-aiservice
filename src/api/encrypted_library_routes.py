"""
Encrypted Library Images API Routes
E2EE (End-to-End Encrypted) images with Zero-Knowledge architecture
"""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.middleware.auth import verify_firebase_token
from src.services.encrypted_library_manager import EncryptedLibraryManager
from config.config import get_r2_client, get_mongodb, R2_BUCKET_NAME

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/library/encrypted-images", tags=["Encrypted Library Images"]
)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class EncryptedImageResponse(BaseModel):
    """Encrypted image metadata response"""

    image_id: str
    owner_id: str
    filename: str
    description: str = ""
    file_size: int
    tags: List[str] = []
    folder_id: Optional[str] = None

    # Encryption metadata
    is_encrypted: bool
    encrypted_file_keys: Dict[str, str]  # {user_id: encrypted_file_key}
    encryption_iv_original: str
    encryption_iv_thumbnail: str
    encryption_iv_exif: Optional[str] = None
    encrypted_exif: Optional[str] = None

    # Image dimensions
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None

    # R2 paths
    r2_image_path: str
    r2_thumbnail_path: str

    # Presigned download URLs (generated on-demand, not stored)
    image_download_url: Optional[str] = None
    thumbnail_download_url: Optional[str] = None

    # Sharing
    shared_with: List[str] = []

    # Timestamps
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    is_deleted: bool


class ShareImageRequest(BaseModel):
    """Request to share an encrypted image"""

    recipient_user_id: str
    encrypted_file_key_for_recipient: (
        str  # File key encrypted with recipient's public key
    )


class UpdateImageMetadataRequest(BaseModel):
    """Request to update image metadata"""

    filename: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_encrypted_library_manager() -> EncryptedLibraryManager:
    """Get EncryptedLibraryManager instance"""
    db = get_mongodb()
    s3_client = get_r2_client()
    return EncryptedLibraryManager(db=db, s3_client=s3_client)


# ============================================================================
# PHASE 1: UPLOAD & LIST OPERATIONS
# ============================================================================
# NOTE: Indexes are now auto-created on app startup (see src/app.py)
# No need for manual initialization endpoint


@router.post("/upload", response_model=EncryptedImageResponse)
async def upload_encrypted_image(
    # Encrypted files
    encryptedImage: UploadFile = File(
        ..., description="Encrypted original image binary"
    ),
    encryptedThumbnail: UploadFile = File(
        ..., description="Encrypted thumbnail binary"
    ),
    # Encryption metadata
    encryptedFileKey: str = Form(
        ..., description="RSA-OAEP encrypted AES file key (base64)"
    ),
    ivOriginal: str = Form(..., description="IV for original image (base64, 12 bytes)"),
    ivThumbnail: str = Form(..., description="IV for thumbnail (base64, 12 bytes)"),
    # Optional EXIF encryption
    encryptedExif: Optional[str] = Form(
        None, description="Encrypted EXIF JSON (base64)"
    ),
    ivExif: Optional[str] = Form(None, description="IV for EXIF (base64, 12 bytes)"),
    # Image metadata
    filename: str = Form(..., description="Original filename"),
    imageWidth: Optional[int] = Form(None, description="Original image width"),
    imageHeight: Optional[int] = Form(None, description="Original image height"),
    thumbnailWidth: Optional[int] = Form(None, description="Thumbnail width"),
    thumbnailHeight: Optional[int] = Form(None, description="Thumbnail height"),
    # Organization
    description: str = Form("", description="Optional description"),
    tags: str = Form("", description="Comma-separated tags"),
    folderId: Optional[str] = Form(None, description="Optional folder ID"),
    # Auth
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Upload encrypted image with thumbnail

    Client-side encryption flow:
    1. Generate random AES-256 file key
    2. Encrypt original image with file key (AES-256-GCM)
    3. Encrypt thumbnail with same file key
    4. Encrypt EXIF data (optional)
    5. Encrypt file key with user's RSA public key (RSA-OAEP)
    6. Upload all encrypted blobs + metadata

    Server never sees plaintext!
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()
        s3_client = get_r2_client()

        # Read encrypted files
        encrypted_image_content = await encryptedImage.read()
        encrypted_thumbnail_content = await encryptedThumbnail.read()

        file_size = len(encrypted_image_content)

        # === CHECK STORAGE LIMIT ===
        from src.services.subscription_service import get_subscription_service

        subscription_service = get_subscription_service()
        file_size_mb = file_size / (1024 * 1024)

        if not await subscription_service.check_storage_limit(owner_id, file_size_mb):
            subscription = await subscription_service.get_or_create_subscription(
                owner_id
            )
            remaining_mb = subscription.storage_limit_mb - subscription.storage_used_mb
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "storage_limit_exceeded",
                    "message": f"Không đủ dung lượng lưu trữ. File cần: {file_size_mb:.2f}MB, Còn lại: {remaining_mb:.2f}MB",
                    "storage_used_mb": round(subscription.storage_used_mb, 2),
                    "storage_limit_mb": subscription.storage_limit_mb,
                    "file_size_mb": round(file_size_mb, 2),
                    "remaining_mb": round(remaining_mb, 2),
                    "upgrade_url": "/pricing",
                    "current_plan": subscription.plan,
                },
            )

        logger.info(
            f"✅ Encrypted library storage check passed: {file_size_mb:.2f}MB for user {owner_id}"
        )

        # Validate file size (max 50MB for encrypted images)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {max_size / (1024 * 1024)}MB",
            )

        # Generate R2 keys with .enc extension
        import uuid

        unique_id = uuid.uuid4().hex[:12]
        file_extension = filename.split(".")[-1] if "." in filename else "jpg"

        r2_image_path = f"encrypted-library/{owner_id}/{unique_id}.{file_extension}.enc"
        r2_thumbnail_path = (
            f"encrypted-library/{owner_id}/{unique_id}_thumb.{file_extension}.enc"
        )

        # Upload encrypted files to R2
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_image_path,
            Body=encrypted_image_content,
            ContentType="application/octet-stream",  # Binary encrypted data
        )

        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_thumbnail_path,
            Body=encrypted_thumbnail_content,
            ContentType="application/octet-stream",
        )

        logger.info(f"🔐 Uploaded encrypted image to R2: {r2_image_path}")

        # Parse tags
        tags_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        )

        # Save metadata to MongoDB
        image_doc = await asyncio.to_thread(
            manager.upload_encrypted_image,
            owner_id=owner_id,
            filename=filename,
            file_size=file_size,
            r2_image_path=r2_image_path,
            r2_thumbnail_path=r2_thumbnail_path,
            encrypted_file_key=encryptedFileKey,
            encryption_iv_original=ivOriginal,
            encryption_iv_thumbnail=ivThumbnail,
            image_width=imageWidth,
            image_height=imageHeight,
            thumbnail_width=thumbnailWidth,
            thumbnail_height=thumbnailHeight,
            encrypted_exif=encryptedExif,
            encryption_iv_exif=ivExif,
            folder_id=folderId,
            tags=tags_list,
            description=description,
        )

        logger.info(f"🔐 Encrypted image saved: {image_doc['image_id']}")

        # Generate presigned URLs for immediate use (optional for upload response)
        image_doc["image_download_url"] = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": r2_image_path},
            ExpiresIn=3600,
        )
        image_doc["thumbnail_download_url"] = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": r2_thumbnail_path},
            ExpiresIn=3600,
        )

        return EncryptedImageResponse(**image_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading encrypted image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_encrypted_images_with_folders(
    folderId: Optional[str] = Query(None, description="Filter by folder ID"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    search: Optional[str] = Query(None, description="Search by filename"),
    includeShared: bool = Query(False, description="Include images shared with you"),
    includeDeleted: bool = Query(False, description="Include soft-deleted images"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List encrypted images AND folders for current user

    Returns:
    - folders: List of folders (filtered by folderId if provided)
    - images: List of images with thumbnail URLs
    - pagination: Total count and pagination info

    Returns metadata only (no full image data)
    Client downloads thumbnails and decrypts on-demand
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        # Get folder manager
        from src.services.encrypted_folder_manager import EncryptedFolderManager

        folder_manager = EncryptedFolderManager(db=get_mongodb())

        # Parse tags
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Get folders (if no specific folder filter, get root level folders)
        folders = await asyncio.to_thread(
            folder_manager.list_folders,
            owner_id=owner_id,
            parent_folder_id=folderId,
            include_deleted=includeDeleted,
        )

        # Get images
        images = await asyncio.to_thread(
            manager.list_encrypted_images,
            owner_id=owner_id,
            folder_id=folderId,
            tags=tags_list,
            search_filename=search,
            include_shared=includeShared,
            include_deleted=includeDeleted,
            limit=limit,
            offset=offset,
        )

        # Get total count for pagination
        total_count = await asyncio.to_thread(
            manager.count_encrypted_images,
            owner_id=owner_id,
            folder_id=folderId,
            tags=tags_list,
            search_filename=search,
            include_shared=includeShared,
            include_deleted=includeDeleted,
        )

        # Generate presigned URLs for both thumbnail AND full image
        s3_client = get_r2_client()
        for img in images:
            # Thumbnail URL
            img["thumbnail_download_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": img["r2_thumbnail_path"]},
                ExpiresIn=3600,
            )
            # Full image URL (include in list for better performance)
            img["image_download_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": img["r2_image_path"]},
                ExpiresIn=3600,
            )

        logger.info(
            f"📚 Listed {len(folders)} folders and {len(images)} images for {owner_id}"
        )

        return {
            "folders": folders,
            "images": [EncryptedImageResponse(**img) for img in images],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            },
        }

    except Exception as e:
        logger.error(f"❌ Error listing encrypted images with folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}", response_model=EncryptedImageResponse)
async def get_encrypted_image(
    image_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get single encrypted image metadata by ID

    Access control:
    - Owner can always access
    - Users in shared_with can access
    - Others get 403 Forbidden
    """
    try:
        user_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        # Get image with access check
        image = await asyncio.to_thread(
            manager.get_encrypted_image,
            image_id=image_id,
            user_id=user_id,
            include_deleted=False,
        )

        if not image:
            raise HTTPException(
                status_code=404, detail="Image not found or you don't have access"
            )

        # Generate presigned URLs
        s3_client = get_r2_client()
        image["image_download_url"] = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": image["r2_image_path"]},
            ExpiresIn=3600,
        )
        image["thumbnail_download_url"] = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": image["r2_thumbnail_path"]},
            ExpiresIn=3600,
        )

        logger.info(f"🔍 User {user_id} accessed encrypted image {image_id}")

        return EncryptedImageResponse(**image)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting encrypted image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PHASE 3: SHARING OPERATIONS
# ============================================================================


@router.post("/{image_id}/share")
async def share_encrypted_image(
    image_id: str,
    share_request: ShareImageRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Share encrypted image with another user

    Client-side flow:
    1. Owner decrypts file key using their private key
    2. Owner fetches recipient's public key from server
    3. Owner encrypts file key with recipient's public key (RSA-OAEP)
    4. Owner sends encrypted file key to this endpoint

    Server stores the recipient-specific encrypted file key
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        # Add share access
        success = await asyncio.to_thread(
            manager.add_share_access,
            image_id=image_id,
            owner_id=owner_id,
            recipient_id=share_request.recipient_user_id,
            encrypted_file_key_for_recipient=share_request.encrypted_file_key_for_recipient,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Image not found or you are not the owner"
            )

        logger.info(
            f"🤝 Image {image_id} shared by {owner_id} with {share_request.recipient_user_id}"
        )

        return {
            "success": True,
            "message": f"Image shared with {share_request.recipient_user_id}",
            "image_id": image_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error sharing image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{image_id}/share/{recipient_id}")
async def revoke_share_access(
    image_id: str,
    recipient_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Revoke share access for a specific user

    Only owner can revoke access
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        # Revoke access
        success = await asyncio.to_thread(
            manager.revoke_share_access,
            image_id=image_id,
            owner_id=owner_id,
            recipient_id=recipient_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Image not found or you are not the owner"
            )

        logger.info(
            f"🚫 Image {image_id} access revoked for {recipient_id} by {owner_id}"
        )

        return {
            "success": True,
            "message": f"Access revoked for {recipient_id}",
            "image_id": image_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error revoking access for image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PHASE 4: DELETE OPERATIONS
# ============================================================================


@router.delete("/{image_id}")
async def soft_delete_encrypted_image(
    image_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Soft delete encrypted image (move to trash)

    Only owner can delete
    R2 files are NOT deleted yet (can be restored)
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        success = await asyncio.to_thread(
            manager.soft_delete_image,
            image_id=image_id,
            owner_id=owner_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Image not found or you are not the owner"
            )

        logger.info(f"🗑️ Image {image_id} soft deleted by {owner_id}")

        return {
            "success": True,
            "message": "Image moved to trash",
            "image_id": image_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{image_id}/restore")
async def restore_encrypted_image(
    image_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Restore soft-deleted encrypted image from trash

    Only owner can restore
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        success = await asyncio.to_thread(
            manager.restore_image,
            image_id=image_id,
            owner_id=owner_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Image not found or you are not the owner"
            )

        logger.info(f"♻️ Image {image_id} restored by {owner_id}")

        return {
            "success": True,
            "message": "Image restored from trash",
            "image_id": image_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring image {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# METADATA UPDATE OPERATIONS
# ============================================================================


@router.put("/{image_id}/metadata", response_model=EncryptedImageResponse)
async def update_image_metadata(
    image_id: str,
    request: UpdateImageMetadataRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update encrypted image metadata

    Only owner can update metadata

    - **filename**: New filename (optional)
    - **description**: New description (optional)
    - **tags**: New tags array (optional, replaces existing tags)
    - **folder_id**: Move to different folder (optional, null = move to root)
    """
    try:
        owner_id = user_data.get("uid")
        manager = get_encrypted_library_manager()

        # Build updates dict (only include non-None values)
        updates = {}
        if request.filename is not None:
            updates["filename"] = request.filename
        if request.description is not None:
            updates["description"] = request.description
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.folder_id is not None:
            updates["folder_id"] = request.folder_id

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Update metadata
        updated_image = await asyncio.to_thread(
            manager.update_image_metadata,
            image_id=image_id,
            owner_id=owner_id,
            updates=updates,
        )

        if not updated_image:
            raise HTTPException(
                status_code=404, detail="Image not found or you are not the owner"
            )

        logger.info(f"✅ Image metadata updated: {image_id} by {owner_id}")

        return EncryptedImageResponse(**updated_image)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating image metadata {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
