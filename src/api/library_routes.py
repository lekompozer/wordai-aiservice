"""
Library Files API Routes
Type 3: Library Files (Templates, Guides, References, Resources)
"""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.middleware.auth import verify_firebase_token
from src.services.library_manager import LibraryManager
from src.services.subscription_service import get_subscription_service
from src.models.subscription import SubscriptionUsageUpdate
from config.config import get_r2_client, get_mongodb, R2_BUCKET_NAME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["Library Files"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class LibraryFileResponse(BaseModel):
    """Library file response model"""

    library_id: str
    user_id: str
    filename: str
    file_type: str
    file_size: int
    category: str
    description: str = ""
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    file_url: str
    is_deleted: bool = False
    uploaded_at: datetime
    updated_at: datetime


class LibraryStatsResponse(BaseModel):
    """Library statistics response"""

    total_files: int
    total_bytes: int
    by_category: Dict[str, Dict[str, int]]


class UpdateLibraryMetadataRequest(BaseModel):
    """Update library metadata request"""

    filename: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = Field(
        None, pattern="^(templates|guides|references|resources)$"
    )
    tags: Optional[List[str]] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_library_manager() -> LibraryManager:
    """Get LibraryManager instance"""
    db = get_mongodb()
    s3_client = get_r2_client()
    return LibraryManager(db=db, s3_client=s3_client)


def extract_file_metadata(file: UploadFile, file_type: str) -> Dict[str, Any]:
    """
    Extract metadata from uploaded file

    Args:
        file: Uploaded file
        file_type: MIME type

    Returns:
        Metadata dictionary
    """
    metadata = {}

    # For images: would extract dimensions
    if file_type.startswith("image/"):
        # TODO: Extract image dimensions using Pillow
        metadata["type"] = "image"

    # For videos: would extract duration, resolution
    elif file_type.startswith("video/"):
        # TODO: Extract video metadata using ffmpeg-python
        metadata["type"] = "video"

    # For documents
    elif file_type in ["application/pdf", "application/msword"]:
        metadata["type"] = "document"

    return metadata


# ============================================================================
# INITIALIZATION ENDPOINT
# ============================================================================


@router.post("/initialize")
async def initialize_library_indexes(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Initialize library_files collection indexes
    Run this once during setup
    """
    try:
        library_manager = get_library_manager()

        success = await asyncio.to_thread(library_manager.create_indexes)

        if success:
            return {
                "success": True,
                "message": "Library indexes created successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create indexes")

    except Exception as e:
        logger.error(f"❌ Error initializing library indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# UPLOAD & CRUD OPERATIONS
# ============================================================================


@router.post("/upload", response_model=LibraryFileResponse)
async def upload_library_file(
    file: UploadFile = File(...),
    description: str = Form(""),
    tags: str = Form(""),  # Comma-separated tags
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Upload file to library with auto-categorization

    Category is automatically detected from file type:
    - documents: PDF, Word, Excel, PPT, Text files
    - images: JPG, PNG, GIF, SVG, WebP
    - videos: MP4, AVI, MOV, WebM
    - audio: MP3, WAV, OGG, M4A
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()
        s3_client = get_r2_client()

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # === CHECK STORAGE LIMIT ===
        from src.services.subscription_service import get_subscription_service

        subscription_service = get_subscription_service()
        file_size_mb = file_size / (1024 * 1024)

        if not await subscription_service.check_storage_limit(user_id, file_size_mb):
            subscription = await subscription_service.get_or_create_subscription(
                user_id
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
            f"✅ Library storage check passed: {file_size_mb:.2f}MB for user {user_id}"
        )

        # Validate file size (max 100MB for library files)
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {max_size / (1024 * 1024)}MB",
            )

        # Generate R2 key (category will be auto-detected in service)
        import uuid

        file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
        r2_key = f"library/{user_id}/{uuid.uuid4().hex}.{file_extension}"

        # Upload to R2
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key,
            Body=file_content,
            ContentType=file.content_type or "application/octet-stream",
        )

        # Generate signed URL (private)
        file_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": r2_key},
            ExpiresIn=3600,  # 1 hour
        )

        # Extract metadata
        metadata = extract_file_metadata(file, file.content_type or "")

        # Parse tags
        tags_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        )

        # Save to MongoDB (category auto-detected in service)
        library_doc = await asyncio.to_thread(
            library_manager.upload_library_file,
            user_id=user_id,
            filename=file.filename,
            file_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            r2_key=r2_key,
            file_url=file_url,
            description=description,
            tags=tags_list,
            metadata=metadata,
        )

        logger.info(
            f"📚 Library file uploaded: {library_doc['library_id']} (category: {library_doc['category']})"
        )

        # === UPDATE USAGE COUNTERS ===
        try:
            await subscription_service.update_usage(
                user_id=user_id,
                update=SubscriptionUsageUpdate(storage_mb=file_size_mb, upload_files=1),
            )
            logger.info(
                f"📊 Updated storage (+{file_size_mb:.2f}MB) and file counter (+1)"
            )
        except Exception as usage_error:
            logger.error(f"❌ Error updating usage counters: {usage_error}")
            # Don't fail the request if counter update fails

        return LibraryFileResponse(**library_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading library file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files", response_model=List[LibraryFileResponse])
async def list_library_files(
    category: Optional[str] = Query(None, pattern="^(documents|images|videos|audio)$"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List library files with optional filters

    Categories (auto-detected from file type):
    - documents: PDF, Word, Excel, PPT, Text files
    - images: JPG, PNG, GIF, SVG, WebP
    - videos: MP4, AVI, MOV, WebM
    - audio: MP3, WAV, OGG, M4A

    Query Parameters:
    - category: Filter by category (documents, images, videos, audio)
    - tags: Comma-separated tags to filter by (e.g., "insurance,contract")
    - limit: Max results (default: 50, max: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        # Parse tags
        tags_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else None
        )

        files = await asyncio.to_thread(
            library_manager.list_library_files,
            user_id=user_id,
            category=category,
            tags=tags_list,
            limit=limit,
            offset=offset,
        )

        # Generate fresh signed URLs
        s3_client = get_r2_client()
        for file_doc in files:
            file_doc["file_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": file_doc["r2_key"]},
                ExpiresIn=3600,
            )

        return [LibraryFileResponse(**doc) for doc in files]

    except Exception as e:
        logger.error(f"❌ Error listing library files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{library_id}", response_model=LibraryFileResponse)
async def get_library_file(
    library_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Get single library file by ID"""
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        file_doc = await asyncio.to_thread(
            library_manager.get_library_file,
            library_id=library_id,
            user_id=user_id,
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="Library file not found")

        # Generate fresh signed URL
        s3_client = get_r2_client()
        file_doc["file_url"] = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": file_doc["r2_key"]},
            ExpiresIn=3600,
        )

        return LibraryFileResponse(**file_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting library file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/{library_id}")
async def update_library_metadata(
    library_id: str,
    request: UpdateLibraryMetadataRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Update library file metadata (filename, description, category, tags)"""
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        success = await asyncio.to_thread(
            library_manager.update_library_metadata,
            library_id=library_id,
            user_id=user_id,
            filename=request.filename,
            description=request.description,
            category=request.category,
            tags=request.tags,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Library file not found")

        return {
            "success": True,
            "message": f"Library file {library_id} updated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating library file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TRASH MANAGEMENT
# ============================================================================


@router.delete("/files/{library_id}/trash")
async def move_library_file_to_trash(
    library_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Move library file to trash (soft delete)"""
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        success = await asyncio.to_thread(
            library_manager.soft_delete_library_file,
            library_id=library_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Library file not found")

        return {
            "success": True,
            "message": f"Library file {library_id} moved to trash",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error moving library file to trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/trash/list", response_model=List[LibraryFileResponse])
async def list_library_trash(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """List deleted library files (trash)"""
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        files = await asyncio.to_thread(
            library_manager.list_deleted_library_files,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

        # Generate fresh signed URLs
        s3_client = get_r2_client()
        for file_doc in files:
            file_doc["file_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": file_doc["r2_key"]},
                ExpiresIn=3600,
            )

        return [LibraryFileResponse(**doc) for doc in files]

    except Exception as e:
        logger.error(f"❌ Error listing library trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{library_id}/restore")
async def restore_library_file_from_trash(
    library_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Restore library file from trash"""
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        success = await asyncio.to_thread(
            library_manager.restore_library_file,
            library_id=library_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Library file not found in trash"
            )

        return {
            "success": True,
            "message": f"Library file {library_id} restored from trash",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring library file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{library_id}/permanent")
async def permanent_delete_library_file(
    library_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Permanently delete library file from R2 and MongoDB
    ⚠️ WARNING: This action cannot be undone!
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        success = await asyncio.to_thread(
            library_manager.delete_library_file_permanent,
            library_id=library_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Library file not found")

        return {
            "success": True,
            "message": f"Library file {library_id} permanently deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error permanently deleting library file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/trash/empty")
async def empty_library_trash(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Permanently delete ALL library files in trash
    ⚠️ WARNING: This action cannot be undone!
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        # Get deleted files to calculate storage
        deleted_files = await asyncio.to_thread(
            library_manager.list_deleted_library_files, user_id=user_id, limit=10000
        )

        # Calculate total storage to free
        total_bytes_freed = sum(
            file_doc.get("file_size", 0) for file_doc in deleted_files
        )
        total_mb_freed = total_bytes_freed / (1024 * 1024)

        # Delete files
        deleted_count = await asyncio.to_thread(
            library_manager.empty_library_trash,
            user_id=user_id,
        )

        # === DECREASE STORAGE USED ===
        if deleted_count > 0 and total_mb_freed > 0:
            try:
                subscription_service = get_subscription_service()
                await subscription_service.update_usage(
                    user_id=user_id,
                    update=SubscriptionUsageUpdate(storage_mb=-total_mb_freed),
                )
                logger.info(
                    f"📊 Decreased storage by {total_mb_freed:.2f}MB ({deleted_count} library files)"
                )
            except Exception as usage_error:
                logger.error(f"❌ Error updating storage counter: {usage_error}")

        return {
            "success": True,
            "message": f"Permanently deleted {deleted_count} library files from trash",
            "deleted_count": deleted_count,
            "storage_freed_mb": round(total_mb_freed, 2),
        }

    except Exception as e:
        logger.error(f"❌ Error emptying library trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SEARCH & CATEGORIES
# ============================================================================


@router.get("/search", response_model=List[LibraryFileResponse])
async def search_library_files(
    q: str = Query(..., min_length=1, description="Search query"),
    category: Optional[str] = Query(None, pattern="^(documents|images|videos|audio)$"),
    limit: int = Query(50, ge=1, le=100),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Full-text search in library files

    Searches in: filename, description
    Categories are auto-detected from file types (optional filter)
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        files = await asyncio.to_thread(
            library_manager.search_library,
            user_id=user_id,
            query=q,
            category=category,
            limit=limit,
        )

        # Generate fresh signed URLs
        s3_client = get_r2_client()
        for file_doc in files:
            file_doc["file_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": file_doc["r2_key"]},
                ExpiresIn=3600,
            )

        return [LibraryFileResponse(**doc) for doc in files]

    except Exception as e:
        logger.error(f"❌ Error searching library: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_library_categories(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get list of available categories

    Categories are auto-detected from file types during upload
    Returns list of category objects with name and description
    """
    return {
        "categories": [
            {
                "value": "documents",
                "label": "Documents",
                "description": "PDF, Word, Excel, PowerPoint, text files",
            },
            {
                "value": "images",
                "label": "Images",
                "description": "JPG, PNG, GIF, SVG, WebP images",
            },
            {
                "value": "videos",
                "label": "Videos",
                "description": "MP4, AVI, MOV, WebM video files",
            },
            {
                "value": "audio",
                "label": "Audio",
                "description": "MP3, WAV, OGG, M4A audio files",
            },
        ]
    }


# ============================================================================
# STATISTICS
# ============================================================================


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_library_stats(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Get library statistics (total files, size by category)"""
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        stats = await asyncio.to_thread(
            library_manager.get_library_stats,
            user_id=user_id,
        )

        return LibraryStatsResponse(**stats)

    except Exception as e:
        logger.error(f"❌ Error getting library stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DOWNLOAD
# ============================================================================


@router.get("/files/{library_id}/download")
async def generate_library_download_url(
    library_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Generate signed download URL for library file
    URL expires in 1 hour
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()

        # Get file info
        file_doc = await asyncio.to_thread(
            library_manager.get_library_file,
            library_id=library_id,
            user_id=user_id,
        )

        if not file_doc:
            raise HTTPException(status_code=404, detail="Library file not found")

        # Generate signed URL
        s3_client = get_r2_client()
        download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": R2_BUCKET_NAME,
                "Key": file_doc["r2_key"],
                "ResponseContentDisposition": f'attachment; filename="{file_doc["filename"]}"',
            },
            ExpiresIn=3600,  # 1 hour
        )

        return {
            "download_url": download_url,
            "filename": file_doc["filename"],
            "file_size": file_doc["file_size"],
            "expires_in": 3600,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating download URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PHASE 2: CONVERT REGULAR IMAGE TO SECRET
# ============================================================================


@router.post("/files/{library_id}/convert-to-secret")
async def convert_regular_image_to_secret(
    library_id: str,
    # Encrypted files (same as upload endpoint in encrypted_library_routes.py)
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
    imageWidth: Optional[int] = Form(None, description="Original image width"),
    imageHeight: Optional[int] = Form(None, description="Original image height"),
    thumbnailWidth: Optional[int] = Form(None, description="Thumbnail width"),
    thumbnailHeight: Optional[int] = Form(None, description="Thumbnail height"),
    # Auth
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Convert an existing regular (unencrypted) library image to E2EE secret image

    Flow:
    1. Client downloads the regular image from library
    2. Client encrypts it using E2EE flow (AES-256-GCM + RSA-OAEP)
    3. Client calls this endpoint with encrypted blobs
    4. Server OVERWRITES the regular file on R2 with encrypted version
    5. Server updates MongoDB document with encryption metadata

    This ensures no unencrypted copy remains on the server!
    """
    try:
        user_id = user_data.get("uid")
        library_manager = get_library_manager()
        s3_client = get_r2_client()

        # 1. Verify user owns this file
        existing_file = await asyncio.to_thread(
            library_manager.get_library_file,
            library_id=library_id,
            user_id=user_id,
        )

        if not existing_file:
            raise HTTPException(
                status_code=404,
                detail="Library file not found or you don't have permission",
            )

        # 2. Check if already encrypted
        if existing_file.get("is_encrypted", False):
            raise HTTPException(
                status_code=400, detail="This image is already encrypted"
            )

        # 3. Verify it's an image
        if existing_file["category"] != "images":
            raise HTTPException(
                status_code=400,
                detail="Only images can be converted to secret. This file is a "
                + existing_file["category"],
            )

        # 4. Read encrypted files
        encrypted_image_content = await encryptedImage.read()
        encrypted_thumbnail_content = await encryptedThumbnail.read()

        file_size = len(encrypted_image_content)

        # 5. Generate NEW R2 keys with .enc extension
        import uuid

        unique_id = uuid.uuid4().hex[:12]
        file_extension = (
            existing_file["filename"].split(".")[-1]
            if "." in existing_file["filename"]
            else "jpg"
        )

        # Use encrypted-library prefix to separate from regular files
        r2_image_path = f"encrypted-library/{user_id}/{unique_id}.{file_extension}.enc"
        r2_thumbnail_path = (
            f"encrypted-library/{user_id}/{unique_id}_thumb.{file_extension}.enc"
        )

        # 6. Upload encrypted files to R2 (NEW paths)
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

        logger.info(f"🔐 Uploaded encrypted version to R2: {r2_image_path}")

        # 7. DELETE old unencrypted file from R2
        try:
            s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=existing_file["r2_key"])
            logger.info(f"🗑️ Deleted old unencrypted file: {existing_file['r2_key']}")
        except Exception as e:
            logger.warning(
                f"⚠️ Could not delete old file {existing_file['r2_key']}: {e}"
            )

        # 8. Update MongoDB document with encryption metadata
        from datetime import datetime, timezone

        update_data = {
            "is_encrypted": True,
            "encrypted_file_keys": {user_id: encryptedFileKey},
            "encryption_iv_original": ivOriginal,
            "encryption_iv_thumbnail": ivThumbnail,
            "encryption_iv_exif": ivExif if encryptedExif else None,
            "encrypted_exif": encryptedExif,
            "image_width": imageWidth,
            "image_height": imageHeight,
            "thumbnail_width": thumbnailWidth,
            "thumbnail_height": thumbnailHeight,
            "r2_image_path": r2_image_path,
            "r2_thumbnail_path": r2_thumbnail_path,
            "r2_key": r2_image_path,  # Update primary key
            "file_size": file_size,
            "updated_at": datetime.now(timezone.utc),
            "shared_with": [],  # Initialize empty sharing list
        }

        # Update the document
        db = get_mongodb()
        result = db["library_files"].update_one(
            {"library_id": library_id, "user_id": user_id}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="Failed to update document with encryption metadata",
            )

        logger.info(f"✅ Converted library image {library_id} to encrypted")

        # Generate presigned URLs for immediate access
        image_download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": r2_image_path},
            ExpiresIn=3600,
        )
        thumbnail_download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": r2_thumbnail_path},
            ExpiresIn=3600,
        )

        return {
            "success": True,
            "message": "Image successfully converted to secret",
            "library_id": library_id,
            "image_id": library_id,  # Can use same ID
            "r2_image_path": r2_image_path,
            "r2_thumbnail_path": r2_thumbnail_path,
            "is_encrypted": True,
            "image_download_url": image_download_url,
            "thumbnail_download_url": thumbnail_download_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error converting image to secret: {e}")
        raise HTTPException(status_code=500, detail=str(e))
