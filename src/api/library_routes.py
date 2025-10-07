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

        deleted_count = await asyncio.to_thread(
            library_manager.empty_library_trash,
            user_id=user_id,
        )

        return {
            "success": True,
            "message": f"Permanently deleted {deleted_count} library files from trash",
            "deleted_count": deleted_count,
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
