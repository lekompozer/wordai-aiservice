"""
Secret Images API Routes
Dedicated endpoints for E2EE secret images in library with folder support
"""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, File, Form, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.middleware.auth import verify_firebase_token
from src.services.library_manager import LibraryManager
from config.config import get_r2_client, get_mongodb, R2_BUCKET_NAME

logger = logging.getLogger("chatbot")  # Use 'chatbot' logger to match app.py

router = APIRouter(prefix="/api/library/secret-images", tags=["Secret Images"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class SecretFolderResponse(BaseModel):
    """Secret image folder metadata"""

    folder_id: str
    folder_name: str
    parent_folder_id: Optional[str] = None
    owner_id: str
    is_secret: bool = True  # Always true for secret folders

    # Encryption metadata for folder (optional, for future use)
    encrypted_folder_key: Optional[str] = None

    # Stats
    image_count: int = 0
    total_size: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False


class SecretImageResponse(BaseModel):
    """Secret image complete metadata with encryption info"""

    # Basic info
    image_id: str  # Same as library_id
    library_id: str  # For backward compatibility
    owner_id: str
    filename: str
    description: str = ""
    file_size: int
    tags: List[str] = []

    # Folder organization
    folder_id: Optional[str] = None
    folder_name: Optional[str] = None

    # Encryption metadata (REQUIRED for secret images)
    is_encrypted: bool = True
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

    # R2 storage paths
    r2_image_path: str
    r2_thumbnail_path: str

    # Presigned URLs (generated on-demand)
    image_download_url: str
    thumbnail_download_url: str

    # Sharing
    shared_with: List[str] = []

    # Timestamps
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    is_deleted: bool = False


class SecretImageListResponse(BaseModel):
    """List response with folders and images"""

    folders: List[SecretFolderResponse]
    images: List[SecretImageResponse]
    pagination: Dict[str, Any]


class CreateSecretFolderRequest(BaseModel):
    """Request to create a new secret folder"""

    folder_name: str = Field(..., min_length=1, max_length=255)
    parent_folder_id: Optional[str] = None
    encrypted_folder_key: Optional[str] = None  # For future folder encryption


class UpdateSecretImageRequest(BaseModel):
    """Update secret image metadata"""

    filename: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_library_manager() -> LibraryManager:
    """Get LibraryManager instance"""
    db = get_mongodb()
    s3_client = get_r2_client()
    return LibraryManager(db=db, s3_client=s3_client)


def generate_presigned_urls_for_secret_image(
    image_doc: Dict[str, Any], s3_client, expires_in: int = 3600
) -> Dict[str, Any]:
    """
    Generate presigned URLs for encrypted image and thumbnail

    Args:
        image_doc: MongoDB document with r2_image_path and r2_thumbnail_path
        s3_client: boto3 S3 client
        expires_in: URL expiration time in seconds

    Returns:
        Updated image_doc with download URLs
    """
    try:
        # Generate URL for full encrypted image
        if image_doc.get("r2_image_path"):
            image_doc["image_download_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": image_doc["r2_image_path"]},
                ExpiresIn=expires_in,
            )

        # Generate URL for encrypted thumbnail
        if image_doc.get("r2_thumbnail_path"):
            image_doc["thumbnail_download_url"] = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": R2_BUCKET_NAME,
                    "Key": image_doc["r2_thumbnail_path"],
                },
                ExpiresIn=expires_in,
            )

        return image_doc

    except Exception as e:
        logger.error(f"❌ Error generating presigned URLs: {e}")
        # Return doc without URLs rather than failing
        image_doc["image_download_url"] = None
        image_doc["thumbnail_download_url"] = None
        return image_doc


# ============================================================================
# FOLDER MANAGEMENT
# ============================================================================


@router.post("/folders", response_model=SecretFolderResponse)
async def create_secret_folder(
    request: CreateSecretFolderRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Create a new folder for secret images

    Folders are stored in library_folders collection with is_secret=true
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()

        from datetime import datetime, timezone
        import uuid

        now = datetime.now(timezone.utc)
        folder_id = f"secret_folder_{uuid.uuid4().hex[:12]}"

        folder_doc = {
            "folder_id": folder_id,
            "folder_name": request.folder_name,
            "parent_folder_id": request.parent_folder_id,
            "owner_id": user_id,
            "is_secret": True,  # Mark as secret folder
            "encrypted_folder_key": request.encrypted_folder_key,
            "image_count": 0,
            "total_size": 0,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        }

        db["library_folders"].insert_one(folder_doc)

        logger.info(f"🔐 Created secret folder: {folder_id} for user {user_id}")

        return SecretFolderResponse(**folder_doc)

    except Exception as e:
        logger.error(f"❌ Error creating secret folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# REMOVED: Separate list folders endpoint - Use main list endpoint instead
# The main GET /api/library/secret-images endpoint returns BOTH folders and images
# This provides better UX with single API call for folder navigation

# @router.get("/folders", response_model=List[SecretFolderResponse])
# async def list_secret_folders(...)
#     """List all secret folders - DEPRECATED: Use main list endpoint"""


@router.delete("/folders/{folder_id}")
async def delete_secret_folder(
    folder_id: str,
    permanently: bool = Query(False, description="Permanently delete (vs soft delete)"),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Delete a secret folder (soft delete by default)

    Note: Images in folder are NOT automatically deleted
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()

        # Verify ownership
        folder = db["library_folders"].find_one(
            {
                "folder_id": folder_id,
                "owner_id": user_id,
                "is_secret": True,
            }
        )

        if not folder:
            raise HTTPException(status_code=404, detail="Secret folder not found")

        if permanently:
            # Hard delete
            result = db["library_folders"].delete_one(
                {
                    "folder_id": folder_id,
                    "owner_id": user_id,
                }
            )

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Folder not found")

            logger.info(f"🗑️ Permanently deleted secret folder: {folder_id}")

            return {
                "success": True,
                "message": f"Folder {folder_id} permanently deleted",
                "permanently": True,
            }
        else:
            # Soft delete
            from datetime import datetime, timezone

            result = db["library_folders"].update_one(
                {"folder_id": folder_id, "owner_id": user_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Folder not found")

            logger.info(f"🗑️ Soft deleted secret folder: {folder_id}")

            return {
                "success": True,
                "message": f"Folder {folder_id} moved to trash",
                "permanently": False,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting secret folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SECRET IMAGE OPERATIONS
# ============================================================================


@router.get("", response_model=SecretImageListResponse)
async def list_secret_images(
    folder_id: Optional[str] = Query(None, description="Filter by folder"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    search: Optional[str] = Query(None, description="Search by filename"),
    include_shared: bool = Query(False, description="Include images shared with you"),
    include_deleted: bool = Query(False, description="Include soft-deleted images"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List secret images with folder structure

    Returns:
    - folders: List of secret folders (filtered by folder_id if provided)
    - images: List of secret images with presigned URLs
    - pagination: Total count and pagination info

    Only returns ENCRYPTED images (is_encrypted: true)
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()
        s3_client = get_r2_client()

        # Build query for images
        query = {
            "user_id": user_id,
            "is_encrypted": True,  # Only secret images
            "category": "images",
        }

        if folder_id is not None:
            query["folder_id"] = folder_id

        if not include_deleted:
            query["is_deleted"] = False

        # Search by filename
        if search:
            query["filename"] = {"$regex": search, "$options": "i"}

        # Filter by tags
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            query["tags"] = {"$in": tags_list}

        # Include shared images
        if include_shared:
            query = {
                "$or": [
                    query,
                    {
                        "is_encrypted": True,
                        "shared_with": user_id,
                        "is_deleted": False,
                    },
                ]
            }

        # Get total count
        total_count = db["library_files"].count_documents(query)

        # Get images with pagination
        images = list(
            db["library_files"]
            .find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )

        # Generate presigned URLs for each image
        for img in images:
            # Set image_id (same as library_id for compatibility)
            img["image_id"] = img.get("library_id", img.get("_id"))

            # Map user_id to owner_id (backward compatibility)
            if "owner_id" not in img and "user_id" in img:
                img["owner_id"] = img["user_id"]

            # Map uploaded_at to created_at (backward compatibility)
            if "created_at" not in img and "uploaded_at" in img:
                img["created_at"] = img["uploaded_at"]

            # Get folder name if folder_id exists (BEFORE generating URLs)
            if img.get("folder_id"):
                folder = db["library_folders"].find_one({"folder_id": img["folder_id"]})
                img["folder_name"] = folder.get("folder_name") if folder else None
                # DEBUG: Log folder lookup
                logger.info(
                    f"🔍 [IMAGE_FOLDER_DEBUG] image_id={img.get('library_id')}, folder_id={img.get('folder_id')}, folder_name={img.get('folder_name')}, folder_found={folder is not None}"
                )
            else:
                img["folder_name"] = None

            # Generate presigned URLs (AFTER setting folder_name)
            img = generate_presigned_urls_for_secret_image(img, s3_client)

        # Get folders (if not filtering by specific folder, get root folders)
        folders_query = {
            "owner_id": user_id,
            "is_secret": True,
        }

        if folder_id is not None:
            # Get subfolders of this folder
            folders_query["parent_folder_id"] = folder_id
        else:
            # Get root level folders
            folders_query["parent_folder_id"] = None

        if not include_deleted:
            folders_query["is_deleted"] = False

        folders = list(db["library_folders"].find(folders_query).sort("created_at", -1))

        # Calculate stats for folders
        for folder in folders:
            # DEBUG: Log folder data
            logger.info(
                f"🔍 [FOLDER_DEBUG] folder_id={folder.get('folder_id')}, folder_name={folder.get('folder_name')}, owner_id={folder.get('owner_id')}"
            )

            folder["image_count"] = db["library_files"].count_documents(
                {
                    "user_id": user_id,
                    "is_encrypted": True,
                    "folder_id": folder["folder_id"],
                    "is_deleted": False,
                }
            )

            # Calculate total size
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "is_encrypted": True,
                        "folder_id": folder["folder_id"],
                        "is_deleted": False,
                    }
                },
                {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}},
            ]

            result = list(db["library_files"].aggregate(pipeline))
            folder["total_size"] = result[0]["total_size"] if result else 0

        logger.info(
            f"🔐 Listed {len(folders)} folders and {len(images)} secret images for {user_id}"
        )

        return SecretImageListResponse(
            folders=[SecretFolderResponse(**f) for f in folders],
            images=[SecretImageResponse(**img) for img in images],
            pagination={
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count,
            },
        )

    except Exception as e:
        logger.error(f"❌ Error listing secret images: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}", response_model=SecretImageResponse)
async def get_secret_image(
    image_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get single secret image by ID with full encryption metadata

    Returns:
    - Complete encryption metadata (keys, IVs, etc.)
    - Presigned URLs for encrypted image and thumbnail
    - Image dimensions and file info

    Use this when user clicks on an image to view/edit
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()
        s3_client = get_r2_client()

        # Query by image_id or library_id
        image = db["library_files"].find_one(
            {
                "$or": [
                    {"library_id": image_id},
                    {"_id": image_id},
                ],
                "is_encrypted": True,
            }
        )

        if not image:
            raise HTTPException(status_code=404, detail="Secret image not found")

        # Verify access (owner or shared with)
        if image["user_id"] != user_id and user_id not in image.get("shared_with", []):
            raise HTTPException(
                status_code=403, detail="You don't have permission to access this image"
            )

        # Set image_id
        image["image_id"] = image.get("library_id", image.get("_id"))

        # Map user_id to owner_id (backward compatibility)
        if "owner_id" not in image and "user_id" in image:
            image["owner_id"] = image["user_id"]

        # Map uploaded_at to created_at (backward compatibility)
        if "created_at" not in image and "uploaded_at" in image:
            image["created_at"] = image["uploaded_at"]

        # Generate presigned URLs
        image = generate_presigned_urls_for_secret_image(image, s3_client)

        # Get folder name if exists
        if image.get("folder_id"):
            folder = db["library_folders"].find_one({"folder_id": image["folder_id"]})
            image["folder_name"] = folder.get("folder_name") if folder else None

        logger.info(f"🔐 Retrieved secret image {image_id} for user {user_id}")

        return SecretImageResponse(**image)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting secret image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{image_id}")
async def update_secret_image(
    image_id: str,
    request: UpdateSecretImageRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update secret image metadata (filename, description, tags, folder)

    Encryption metadata CANNOT be changed after creation
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()

        # Verify ownership
        image = db["library_files"].find_one(
            {
                "$or": [
                    {"library_id": image_id},
                    {"_id": image_id},
                ],
                "user_id": user_id,
                "is_encrypted": True,
            }
        )

        if not image:
            raise HTTPException(
                status_code=404,
                detail="Secret image not found or you don't have permission",
            )

        # Build update document
        update_doc = {"updated_at": datetime.now()}

        if request.filename is not None:
            update_doc["filename"] = request.filename

        if request.description is not None:
            update_doc["description"] = request.description

        if request.tags is not None:
            update_doc["tags"] = request.tags

        if request.folder_id is not None:
            # Verify folder exists and belongs to user
            folder = db["library_folders"].find_one(
                {
                    "folder_id": request.folder_id,
                    "owner_id": user_id,
                    "is_secret": True,
                }
            )

            if not folder:
                raise HTTPException(status_code=404, detail="Folder not found")

            update_doc["folder_id"] = request.folder_id

        # Update document
        result = db["library_files"].update_one(
            {"library_id": image_id, "user_id": user_id}, {"$set": update_doc}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Image not found")

        logger.info(f"✅ Updated secret image {image_id}")

        return {
            "success": True,
            "message": f"Secret image {image_id} updated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating secret image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{image_id}")
async def delete_secret_image(
    image_id: str,
    permanently: bool = Query(False, description="Permanently delete from R2 storage"),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Delete a secret image

    Options:
    - Soft delete (default): Mark as deleted in MongoDB, keep R2 files
    - Hard delete (permanently=true): Delete from both MongoDB AND R2 storage

    Hard delete removes:
    - Encrypted image file from R2
    - Encrypted thumbnail from R2
    - MongoDB document
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()
        s3_client = get_r2_client()

        # Verify ownership
        image = db["library_files"].find_one(
            {
                "$or": [
                    {"library_id": image_id},
                    {"_id": image_id},
                ],
                "user_id": user_id,
                "is_encrypted": True,
            }
        )

        if not image:
            raise HTTPException(
                status_code=404,
                detail="Secret image not found or you don't have permission",
            )

        if permanently:
            # HARD DELETE: Remove from R2 and MongoDB

            # Delete encrypted files from R2
            try:
                if image.get("r2_image_path"):
                    s3_client.delete_object(
                        Bucket=R2_BUCKET_NAME, Key=image["r2_image_path"]
                    )
                    logger.info(f"🗑️ Deleted R2 image: {image['r2_image_path']}")

                if image.get("r2_thumbnail_path"):
                    s3_client.delete_object(
                        Bucket=R2_BUCKET_NAME, Key=image["r2_thumbnail_path"]
                    )
                    logger.info(f"🗑️ Deleted R2 thumbnail: {image['r2_thumbnail_path']}")

            except Exception as e:
                logger.warning(f"⚠️ Error deleting R2 files: {e}")
                # Continue with MongoDB deletion even if R2 fails

            # Delete from MongoDB
            result = db["library_files"].delete_one(
                {
                    "library_id": image_id,
                    "user_id": user_id,
                }
            )

            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Image not found")

            logger.info(f"🗑️ Permanently deleted secret image: {image_id}")

            return {
                "success": True,
                "message": f"Secret image {image_id} permanently deleted",
                "permanently": True,
                "r2_deleted": True,
            }

        else:
            # SOFT DELETE: Mark as deleted in MongoDB
            from datetime import datetime, timezone

            result = db["library_files"].update_one(
                {"library_id": image_id, "user_id": user_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.now(timezone.utc),
                    }
                },
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=404, detail="Image not found")

            logger.info(f"🗑️ Soft deleted secret image: {image_id}")

            return {
                "success": True,
                "message": f"Secret image {image_id} moved to trash",
                "permanently": False,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting secret image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{image_id}/download")
async def download_secret_image(
    image_id: str,
    thumbnail: bool = Query(
        False, description="Download thumbnail instead of full image"
    ),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get direct download URL for secret image

    Returns a redirect to R2 presigned URL for encrypted file

    Args:
        image_id: Secret image ID
        thumbnail: If true, download thumbnail; otherwise full image

    Returns:
        Redirect to presigned R2 URL (expires in 1 hour)
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()
        s3_client = get_r2_client()

        # Get image
        image = db["library_files"].find_one(
            {
                "$or": [
                    {"library_id": image_id},
                    {"_id": image_id},
                ],
                "is_encrypted": True,
            }
        )

        if not image:
            raise HTTPException(status_code=404, detail="Secret image not found")

        # Verify access
        if image["user_id"] != user_id and user_id not in image.get("shared_with", []):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to download this image",
            )

        # Generate presigned URL
        if thumbnail:
            r2_key = image.get("r2_thumbnail_path")
            if not r2_key:
                raise HTTPException(status_code=404, detail="Thumbnail not found")
        else:
            r2_key = image.get("r2_image_path")
            if not r2_key:
                raise HTTPException(status_code=404, detail="Image not found")

        download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": r2_key},
            ExpiresIn=3600,  # 1 hour
        )

        logger.info(
            f"⬇️ Generated download URL for secret image {image_id} "
            f"({'thumbnail' if thumbnail else 'full'}) for user {user_id}"
        )

        # Return redirect to R2 URL
        return RedirectResponse(url=download_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating download URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TRASH MANAGEMENT
# ============================================================================


@router.get("/trash/list", response_model=List[SecretImageResponse])
async def list_secret_images_trash(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List deleted secret images (trash)

    Shows images that were soft-deleted
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()
        s3_client = get_r2_client()

        # Get deleted secret images
        images = list(
            db["library_files"]
            .find(
                {
                    "user_id": user_id,
                    "is_encrypted": True,
                    "is_deleted": True,
                }
            )
            .sort("deleted_at", -1)
            .skip(offset)
            .limit(limit)
        )

        # Generate presigned URLs
        for img in images:
            img["image_id"] = img.get("library_id", img.get("_id"))

            # Map user_id to owner_id (backward compatibility)
            if "owner_id" not in img and "user_id" in img:
                img["owner_id"] = img["user_id"]

            # Map uploaded_at to created_at (backward compatibility)
            if "created_at" not in img and "uploaded_at" in img:
                img["created_at"] = img["uploaded_at"]

            img = generate_presigned_urls_for_secret_image(img, s3_client)

            if img.get("folder_id"):
                folder = db["library_folders"].find_one({"folder_id": img["folder_id"]})
                img["folder_name"] = folder.get("folder_name") if folder else None

        logger.info(f"🗑️ Listed {len(images)} deleted secret images for {user_id}")

        return [SecretImageResponse(**img) for img in images]

    except Exception as e:
        logger.error(f"❌ Error listing secret images trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{image_id}/restore")
async def restore_secret_image(
    image_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Restore a secret image from trash (undo soft delete)
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()

        # Update document
        result = db["library_files"].update_one(
            {
                "library_id": image_id,
                "user_id": user_id,
                "is_encrypted": True,
                "is_deleted": True,
            },
            {
                "$set": {
                    "is_deleted": False,
                    "deleted_at": None,
                    "updated_at": datetime.now(),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=404, detail="Secret image not found in trash"
            )

        logger.info(f"♻️ Restored secret image {image_id} from trash")

        return {
            "success": True,
            "message": f"Secret image {image_id} restored successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring secret image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STATISTICS
# ============================================================================


@router.get("/stats/summary")
async def get_secret_images_stats(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get statistics for secret images

    Returns:
    - Total secret images count
    - Total storage used (bytes)
    - Count by folder
    - Count deleted (trash)
    """
    try:
        user_id = user_data.get("uid")
        db = get_mongodb()

        # Total active secret images
        total_images = db["library_files"].count_documents(
            {
                "user_id": user_id,
                "is_encrypted": True,
                "is_deleted": False,
            }
        )

        # Total storage used
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "is_encrypted": True,
                    "is_deleted": False,
                }
            },
            {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}},
        ]

        result = list(db["library_files"].aggregate(pipeline))
        total_bytes = result[0]["total_size"] if result else 0

        # Count by folder
        folder_pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "is_encrypted": True,
                    "is_deleted": False,
                }
            },
            {
                "$group": {
                    "_id": "$folder_id",
                    "count": {"$sum": 1},
                    "size": {"$sum": "$file_size"},
                }
            },
        ]

        folder_stats = list(db["library_files"].aggregate(folder_pipeline))

        # Get folder names
        by_folder = {}
        for stat in folder_stats:
            folder_id = stat["_id"] if stat["_id"] else "root"
            folder_name = "Root"

            if stat["_id"]:
                folder = db["library_folders"].find_one({"folder_id": stat["_id"]})
                folder_name = folder.get("folder_name") if folder else folder_id

            by_folder[folder_name] = {
                "folder_id": stat["_id"],
                "count": stat["count"],
                "size": stat["size"],
            }

        # Count deleted
        deleted_count = db["library_files"].count_documents(
            {
                "user_id": user_id,
                "is_encrypted": True,
                "is_deleted": True,
            }
        )

        logger.info(f"📊 Generated stats for secret images (user: {user_id})")

        return {
            "total_images": total_images,
            "total_bytes": total_bytes,
            "by_folder": by_folder,
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"❌ Error getting secret images stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DIRECT UPLOAD SECRET IMAGE
# ============================================================================


@router.post("/upload")
async def upload_secret_image(
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
    imageWidth: int = Form(..., description="Original image width"),
    imageHeight: int = Form(..., description="Original image height"),
    thumbnailWidth: int = Form(..., description="Thumbnail width"),
    thumbnailHeight: int = Form(..., description="Thumbnail height"),
    # Optional metadata
    description: Optional[str] = Form("", description="Image description"),
    tags: Optional[str] = Form("", description="Comma-separated tags"),
    folderId: Optional[str] = Form(None, description="Secret folder ID"),
    # Auth
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Upload encrypted image directly to secret images collection

    This is a direct upload endpoint - no need to upload regular image first.
    Client encrypts the image locally and uploads encrypted binary directly.

    Flow:
    1. Client encrypts image with AES-256-GCM (generates random AES key)
    2. Client encrypts AES key with user's RSA public key
    3. Client uploads encrypted binary + encrypted key to this endpoint
    4. Server stores encrypted data on R2 and metadata in MongoDB
    5. Server NEVER sees unencrypted image (Zero-Knowledge E2EE)
    """
    try:
        user_id = user_data.get("uid")
        s3_client = get_r2_client()
        db = get_mongodb()

        # Read encrypted files
        encrypted_image_content = await encryptedImage.read()
        encrypted_thumbnail_content = await encryptedThumbnail.read()

        file_size = len(encrypted_image_content)

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
            f"✅ Secret image storage check passed: {file_size_mb:.2f}MB for user {user_id}"
        )

        # Validate folder if provided
        folder_name = None
        if folderId:
            folder = db["library_folders"].find_one(
                {
                    "folder_id": folderId,
                    "owner_id": user_id,
                    "is_secret": True,
                    "is_deleted": False,
                }
            )
            if not folder:
                raise HTTPException(
                    status_code=404,
                    detail=f"Secret folder {folderId} not found or not accessible",
                )
            folder_name = folder.get("folder_name")
            logger.info(f"✅ Validated folder {folderId}: {folder_name}")

        # Generate R2 keys with .enc extension
        import uuid

        unique_id = uuid.uuid4().hex[:12]
        file_extension = filename.split(".")[-1] if "." in filename else "jpg"

        r2_image_path = f"encrypted-library/{user_id}/{unique_id}.{file_extension}.enc"
        r2_thumbnail_path = (
            f"encrypted-library/{user_id}/{unique_id}_thumb.{file_extension}.enc"
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

        # Create MongoDB document
        from datetime import datetime, timezone

        library_id = f"lib_{unique_id}"
        now = datetime.now(timezone.utc)

        image_doc = {
            "library_id": library_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": "image/jpeg",  # Encrypted, actual type doesn't matter
            "file_size": file_size,
            "category": "images",
            "description": description,
            "tags": tags_list,
            "folder_id": folderId if folderId else None,
            # Encryption metadata
            "is_encrypted": True,
            "encrypted_file_keys": {user_id: encryptedFileKey},
            "encryption_iv_original": ivOriginal,
            "encryption_iv_thumbnail": ivThumbnail,
            "encryption_iv_exif": ivExif if encryptedExif else None,
            "encrypted_exif": encryptedExif,
            # Image dimensions
            "image_width": imageWidth,
            "image_height": imageHeight,
            "thumbnail_width": thumbnailWidth,
            "thumbnail_height": thumbnailHeight,
            # R2 storage
            "r2_image_path": r2_image_path,
            "r2_thumbnail_path": r2_thumbnail_path,
            "r2_key": r2_image_path,
            # Sharing
            "shared_with": [],
            # Timestamps
            "uploaded_at": now,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
            "is_deleted": False,
        }

        db["library_files"].insert_one(image_doc)

        logger.info(
            f"✅ Created secret image {library_id} for user {user_id}"
            + (f" in folder {folderId}" if folderId else "")
        )

        # === UPDATE USAGE COUNTERS ===
        try:
            from src.models.subscription import SubscriptionUsageUpdate

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

        # Generate presigned URLs
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
            "message": "Secret image uploaded successfully",
            "library_id": library_id,
            "image_id": library_id,
            "filename": filename,
            "folder_id": folderId,
            "folder_name": folder_name,
            "is_encrypted": True,
            "r2_image_path": r2_image_path,
            "r2_thumbnail_path": r2_thumbnail_path,
            "image_download_url": image_download_url,
            "thumbnail_download_url": thumbnail_download_url,
            "image_width": imageWidth,
            "image_height": imageHeight,
            "thumbnail_width": thumbnailWidth,
            "thumbnail_height": thumbnailHeight,
            "file_size": file_size,
            "created_at": now.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading secret image: {e}")
        raise HTTPException(status_code=500, detail=str(e))
