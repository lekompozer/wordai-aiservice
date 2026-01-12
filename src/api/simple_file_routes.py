"""
Simple File Upload & Folder Management API
Upload files (PDF, Word, TXT) to R2 và CRUD folders
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
import uuid
import boto3
from datetime import datetime, timedelta
import mimetypes
from pathlib import Path
import logging
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

from src.middleware.auth import verify_firebase_token
from src.services.user_manager import get_user_manager
from src.services.subscription_service import get_subscription_service
from src.services.points_service import get_points_service
from src.models.subscription import SubscriptionUsageUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simple-files", tags=["Simple File Management"])

# R2 Configuration - NEW (wordai.pro domain)
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "wordai")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")

# Log R2 configuration for debugging
logger.info(f"🔧 R2 Configuration loaded:")
logger.info(f"   Bucket: {R2_BUCKET_NAME}")
logger.info(f"   Endpoint: {R2_ENDPOINT_URL}")
logger.info(f"   Public URL: {R2_PUBLIC_URL}")
logger.info(f"   Access Key ID: {'✅ Set' if R2_ACCESS_KEY_ID else '❌ Missing'}")
logger.info(f"   Secret Key: {'✅ Set' if R2_SECRET_ACCESS_KEY else '❌ Missing'}")

# Initialize R2 client
try:
    if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL]):
        raise ValueError("Missing R2 credentials or endpoint")

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        endpoint_url=R2_ENDPOINT_URL,
        region_name="auto",
    )

    logger.info("✅ R2 client initialized successfully")

except Exception as e:
    logger.error(f"❌ Failed to initialize R2 client: {e}")
    s3_client = None


# Pydantic Models
class FolderCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class FolderResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    parent_id: Optional[str]
    user_id: str
    created_at: datetime
    updated_at: datetime
    file_count: int


class FileResponse(BaseModel):
    """File metadata for list endpoints (no signed URLs)"""

    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    folder_id: Optional[str]
    user_id: str
    r2_key: str  # R2 storage key (internal use only)
    created_at: datetime
    updated_at: datetime


class FileDownloadResponse(BaseModel):
    """File metadata with download URL for single file requests"""

    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    folder_id: Optional[str]
    user_id: str
    r2_key: str
    download_url: str  # ✅ Signed URL (only for single file requests)
    created_at: datetime
    updated_at: datetime


class FileUpdate(BaseModel):
    """Model for updating file metadata"""

    filename: Optional[str] = None  # New filename (without path)
    folder_id: Optional[str] = (
        None  # Move to different folder (use "root" or "default" for root folder)
    )


class FolderWithFiles(BaseModel):
    """Folder with its files"""

    folder: FolderResponse
    files: List[FileResponse]


class FileSystemStructure(BaseModel):
    """Complete file system structure with folders and files"""

    root_files: List[FileResponse]  # Files in root (no folder)
    folders: List[FolderWithFiles]  # Folders with their files
    total_files: int
    total_folders: int


# Allowed file types
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/rtf",
}

# File size limit: 100MB (matches Nginx client_max_body_size)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes


def get_file_extension_and_type(filename: str, content_type: str):
    """Get file extension and validate type"""
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type not allowed. File: {filename}, Type: {content_type}",
        )

    return ext, content_type


async def upload_to_r2(file_content: bytes, key: str, content_type: str) -> str:
    """Upload file to R2 private storage and return private URL"""
    try:
        logger.info(f"   [R2] Starting upload...")
        logger.info(f"   [R2] Key: {key}")
        logger.info(f"   [R2] Content-Type: {content_type}")
        logger.info(f"   [R2] Size: {len(file_content)} bytes")

        if s3_client is None:
            logger.error("   [R2] ❌ S3 client is None - R2 not configured!")
            raise HTTPException(
                status_code=500, detail="R2 storage not configured properly"
            )

        logger.info(f"   [R2] Bucket: {R2_BUCKET_NAME}")
        logger.info(f"   [R2] Endpoint: {R2_ENDPOINT_URL}")

        # Upload without ACL (private by default)
        logger.info("   [R2] Calling s3_client.put_object()...")
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=file_content,
            ContentType=content_type,
            # Remove ACL="public-read" to make it private
        )
        logger.info("   [R2] ✅ put_object() completed successfully!")

        # Return private R2 URL (not publicly accessible)
        private_url = f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}/{key}"
        logger.info(f"   [R2] Generated private URL: {private_url}")
        logger.info(f"   [R2] ✅ Upload completed successfully!")
        return private_url

    except Exception as e:
        logger.error(f"   [R2] ❌ Upload failed!")
        logger.error(f"   [R2] Error Type: {type(e).__name__}")
        logger.error(f"   [R2] Error Message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def generate_signed_url(key: str, expiration: int = 3600) -> str:
    """Generate signed URL for private R2 file access"""
    try:
        logger.info(f"   [SignedURL] Generating signed URL...")
        logger.info(f"   [SignedURL] Key: {key}")
        logger.info(
            f"   [SignedURL] Expiration: {expiration}s ({expiration / 3600:.1f} hours)"
        )

        if s3_client is None:
            logger.error("   [SignedURL] ❌ S3 client is None!")
            raise HTTPException(status_code=500, detail="R2 client not available")

        # Generate presigned URL for GET request
        logger.info("   [SignedURL] Calling generate_presigned_url()...")
        signed_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expiration,  # URL expires in 1 hour by default
        )

        logger.info(f"   [SignedURL] ✅ Generated successfully!")
        logger.info(f"   [SignedURL] URL length: {len(signed_url)} chars")

        return signed_url

    except Exception as e:
        logger.error(f"   [SignedURL] ❌ Failed to generate signed URL!")
        logger.error(f"   [SignedURL] Error Type: {type(e).__name__}")
        logger.error(f"   [SignedURL] Error Message: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate access URL: {str(e)}"
        )


# ===== FOLDER CRUD ENDPOINTS =====


@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    folder: FolderCreate, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Create new folder in MongoDB"""
    try:
        user_id = user_data.get("uid")
        folder_id = f"folder_{uuid.uuid4().hex[:12]}"
        user_manager = get_user_manager()

        # Create folder in MongoDB (upload_files collection)
        success = await asyncio.to_thread(
            user_manager.create_folder,
            folder_id=folder_id,
            user_id=user_id,
            name=folder.name,
            description=folder.description,
            parent_id=folder.parent_id,
        )

        if not success:
            raise HTTPException(
                status_code=400, detail="Failed to create folder (may already exist)"
            )

        # Retrieve the created folder to return
        folder_doc = await asyncio.to_thread(
            user_manager.get_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not folder_doc:
            raise HTTPException(status_code=500, detail="Folder created but not found")

        logger.info(
            f"✅ Created folder {folder.name} for user {user_data.get('email')}"
        )

        # Build response
        folder_data = {
            "id": folder_doc.get("folder_id"),
            "name": folder_doc.get("name"),
            "description": folder_doc.get("description"),
            "parent_id": folder_doc.get("parent_id"),
            "user_id": folder_doc.get("user_id"),
            "created_at": folder_doc.get("created_at"),
            "updated_at": folder_doc.get("updated_at"),
            "file_count": folder_doc.get("file_count", 0),
        }

        return FolderResponse(**folder_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to create folder")


@router.get("/folders", response_model=List[FolderResponse])
async def list_folders(
    parent_id: Optional[str] = Query(
        None, description="Parent folder ID, null for root folders"
    ),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """List folders for user from MongoDB"""
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        # Query folders from MongoDB (upload_files folders collection)
        folders_docs = await asyncio.to_thread(
            user_manager.list_folders,
            user_id=user_id,
            parent_id=parent_id,
        )

        # Build response list
        folders = []
        for doc in folders_docs:
            folder_data = {
                "id": doc.get("folder_id"),
                "name": doc.get("name"),
                "description": doc.get("description"),
                "parent_id": doc.get("parent_id"),
                "user_id": doc.get("user_id"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "file_count": doc.get("file_count", 0),
            }
            folders.append(FolderResponse(**folder_data))

        logger.info(
            f"✅ Found {len(folders)} folders for user {user_id} (parent: {parent_id or 'root'})"
        )
        return folders

    except Exception as e:
        logger.error(f"❌ Failed to list folders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list folders")


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Get folder details from MongoDB"""
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        # Get folder from MongoDB
        folder_doc = await asyncio.to_thread(
            user_manager.get_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Build response
        folder_data = {
            "id": folder_doc.get("folder_id"),
            "name": folder_doc.get("name"),
            "description": folder_doc.get("description"),
            "parent_id": folder_doc.get("parent_id"),
            "user_id": folder_doc.get("user_id"),
            "created_at": folder_doc.get("created_at"),
            "updated_at": folder_doc.get("updated_at"),
            "file_count": folder_doc.get("file_count", 0),
        }

        return FolderResponse(**folder_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get folder: {e}")
        raise HTTPException(status_code=404, detail="Folder not found")


@router.put("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Update folder in MongoDB"""
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        # Update folder in MongoDB
        success = await asyncio.to_thread(
            user_manager.update_folder,
            folder_id=folder_id,
            user_id=user_id,
            name=folder_update.name,
            description=folder_update.description,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Get updated folder
        folder_doc = await asyncio.to_thread(
            user_manager.get_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not folder_doc:
            raise HTTPException(status_code=500, detail="Folder updated but not found")

        logger.info(f"✅ Updated folder {folder_id} for user {user_data.get('email')}")

        # Build response
        folder_data = {
            "id": folder_doc.get("folder_id"),
            "name": folder_doc.get("name"),
            "description": folder_doc.get("description"),
            "parent_id": folder_doc.get("parent_id"),
            "user_id": folder_doc.get("user_id"),
            "created_at": folder_doc.get("created_at"),
            "updated_at": folder_doc.get("updated_at"),
            "file_count": folder_doc.get("file_count", 0),
        }

        return FolderResponse(**folder_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to update folder")


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Delete folder from MongoDB (only if empty)"""
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        # Delete folder from MongoDB
        success = await asyncio.to_thread(
            user_manager.delete_folder,
            folder_id=folder_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete folder: folder not found or contains files/subfolders",
            )

        logger.info(f"✅ Deleted folder {folder_id} for user {user_data.get('email')}")

        return {"success": True, "message": "Folder deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete folder")


# ===== FILE UPLOAD ENDPOINTS =====


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Query(None, description="Folder ID to upload file to"),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Upload file (PDF, Word, TXT) to R2 storage"""
    try:
        user_id = user_data.get("uid")
        user_email = user_data.get("email", "unknown")

        # 🔍 DEBUG: Log incoming request
        logger.info("=" * 80)
        logger.info("📤 FILE UPLOAD REQUEST RECEIVED")
        logger.info(f"   User: {user_email} (UID: {user_id})")
        logger.info(f"   Filename: {file.filename}")
        logger.info(f"   Content-Type: {file.content_type}")
        logger.info(f"   Folder ID (raw): {repr(folder_id)}")

        # Handle "default" folder_id from frontend → convert to root
        if folder_id and folder_id.lower() in ["default", "root", ""]:
            logger.info(
                f"   ⚠️  Converting folder_id '{folder_id}' → None (root folder)"
            )
            folder_id = None

        logger.info(f"   Folder ID (processed): {repr(folder_id)}")

        # Validate file type
        logger.info("   🔍 Validating file type...")
        ext, content_type = get_file_extension_and_type(
            file.filename, file.content_type
        )
        logger.info(f"   ✅ File type validated: {ext} ({content_type})")

        # Read file content
        logger.info("   📥 Reading file content...")
        file_content = await file.read()
        file_size = len(file_content)
        logger.info(
            f"   ✅ File read successfully: {file_size} bytes ({file_size / 1024:.2f} KB)"
        )

        # Validate file size (100MB limit)
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            limit_mb = MAX_FILE_SIZE / (1024 * 1024)
            logger.error(f"   ❌ File too large: {size_mb:.2f}MB (limit: {limit_mb}MB)")
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {size_mb:.2f}MB. Maximum allowed: {limit_mb}MB",
            )

        if file_size == 0:
            logger.error("   ❌ File is empty (0 bytes)")
            raise HTTPException(status_code=400, detail="File is empty")

        logger.info(f"   ✅ File size validated: {file_size / (1024 * 1024):.2f}MB")

        # === CHECK STORAGE & FILE COUNT LIMITS (NO POINTS DEDUCTION) ===
        subscription_service = get_subscription_service()

        # Check storage limit
        file_size_mb = file_size / (1024 * 1024)
        if not await subscription_service.check_storage_limit(user_id, file_size_mb):
            subscription = await subscription_service.get_or_create_subscription(
                user_id
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "storage_limit_exceeded",
                    "message": f"Không đủ dung lượng. Cần: {file_size_mb:.2f}MB, Còn: {subscription.storage_limit_mb - subscription.storage_used_mb:.2f}MB",
                    "storage_used_mb": subscription.storage_used_mb,
                    "storage_limit_mb": subscription.storage_limit_mb,
                    "file_size_mb": file_size_mb,
                    "upgrade_url": "/pricing",
                },
            )

        # Check file count limit
        if not await subscription_service.check_upload_files_limit(user_id):
            subscription = await subscription_service.get_or_create_subscription(
                user_id
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "file_limit_exceeded",
                    "message": f"Bạn đã đạt giới hạn {subscription.upload_files_limit} files. Nâng cấp để upload thêm!",
                    "current_count": subscription.upload_files_count,
                    "limit": subscription.upload_files_limit,
                    "upgrade_url": "/pricing",
                },
            )

        logger.info(f"✅ Storage & file count limits passed for user {user_id}")

        # Generate unique filename
        file_id = f"file_{uuid.uuid4().hex[:12]}"
        # Get file extension from original filename
        file_ext = Path(file.filename).suffix.lower() or ".pdf"
        safe_filename = f"{file_id}{file_ext}"
        logger.info(f"   📝 Generated file ID: {file_id}")
        logger.info(f"   📝 Safe filename: {safe_filename}")

        # R2 key structure: uploads/{user_id}/{file_id}.ext (STANDARD for user_files)
        r2_key = f"uploads/{user_id}/{safe_filename}"
        if folder_id:
            logger.info(f"   📂 Folder ID: {folder_id} (stored in MongoDB only)")
        else:
            logger.info(f"   📂 Using root folder (no folder_id specified)")

        logger.info(f"   🔑 R2 Key: {r2_key}")

        logger.info(f"   🔑 R2 Key: {r2_key}")

        # Upload to R2 private storage
        logger.info("   ☁️  Uploading to R2...")
        private_url = await upload_to_r2(file_content, r2_key, content_type)
        logger.info(f"   ✅ R2 upload successful!")
        logger.info(f"   🔗 Private URL: {private_url}")

        # Generate signed URL for download (expires in 1 hour)
        logger.info("   🔐 Generating signed URL...")
        download_url = generate_signed_url(r2_key, expiration=3600)
        logger.info(f"   ✅ Signed URL generated (expires in 1 hour)")

        # Save file metadata to MongoDB
        logger.info("   💾 Saving file metadata to MongoDB...")
        user_manager = get_user_manager()

        saved = await asyncio.to_thread(
            user_manager.save_file_metadata,
            file_id=file_id,
            user_id=user_id,
            filename=safe_filename,
            original_name=file.filename,
            file_type=ext,
            file_size=file_size,
            folder_id=folder_id,
            r2_key=r2_key,
            private_url=private_url,
        )

        if not saved:
            logger.warning("   ⚠️ Failed to save file metadata to MongoDB")
        else:
            logger.info("   ✅ File metadata saved to MongoDB")

        # Create file record for response
        now = datetime.utcnow()
        file_data = {
            "id": file_id,
            "filename": safe_filename,
            "original_name": file.filename,
            "file_type": ext,
            "file_size": file_size,
            "folder_id": folder_id,
            "user_id": user_id,
            "r2_key": r2_key,  # Store the key instead of URL
            "private_url": private_url,  # Private URL (not accessible)
            "download_url": download_url,  # Signed URL for temporary access
            "created_at": now,
            "updated_at": now,
        }

        logger.info("✅ FILE UPLOAD COMPLETED SUCCESSFULLY!")
        logger.info(f"   📄 File ID: {file_id}")
        logger.info(f"   📁 Original Name: {file.filename}")
        logger.info(f"   📊 Size: {file_size} bytes ({file_size / 1024:.2f} KB)")
        logger.info(f"   🔗 Download URL: {download_url[:100]}...")

        # === UPDATE USAGE COUNTERS (NO POINTS DEDUCTION) ===
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

        logger.info("=" * 80)

        return FileResponse(**file_data)

    except HTTPException as http_exc:
        logger.error("=" * 80)
        logger.error("❌ FILE UPLOAD FAILED - HTTP Exception")
        logger.error(f"   Status Code: {http_exc.status_code}")
        logger.error(f"   Detail: {http_exc.detail}")
        logger.error(f"   User: {user_data.get('email', 'unknown')}")
        logger.error(f"   File: {file.filename if file else 'unknown'}")
        logger.error("=" * 80)
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ FILE UPLOAD FAILED - Unexpected Error")
        logger.error(f"   Error Type: {type(e).__name__}")
        logger.error(f"   Error Message: {str(e)}")
        logger.error(f"   User: {user_data.get('email', 'unknown')}")
        logger.error(f"   File: {file.filename if file else 'unknown'}")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files", response_model=List[FileResponse])
async def list_files(
    folder_id: Optional[str] = Query(None, description="Folder ID to list files from"),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """List files for user from MongoDB (excludes deleted files)"""
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(
            f"🔍 Listing files for user {user_id}, folder: {folder_id or 'root'}"
        )

        # Get files from MongoDB (excludes deleted files)
        files_docs = await asyncio.to_thread(
            user_manager.list_user_files,
            user_id=user_id,
            folder_id=folder_id,
            limit=100,
        )

        files = []
        for doc in files_docs:
            file_data = {
                "id": doc.get("file_id"),
                "filename": doc.get("filename"),
                "original_name": doc.get("original_name"),
                "file_type": doc.get("file_type"),
                "file_size": doc.get("file_size"),
                "folder_id": doc.get("folder_id"),
                "user_id": doc.get("user_id"),
                "r2_key": doc.get("r2_key"),
                "created_at": doc.get("uploaded_at"),
                "updated_at": doc.get("updated_at"),
            }
            files.append(FileResponse(**file_data))

        logger.info(f"✅ Found {len(files)} files in folder {folder_id or 'root'}")
        return files

    except Exception as e:
        logger.error(f"❌ Failed to list files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


@router.get("/files/all", response_model=FileSystemStructure)
async def list_all_files(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get complete file system structure with folders and files
    Returns organized structure: root files + folders with their files
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(f"🔍 Getting file system structure for user {user_id}")

        # 1. Get all root folders (parent_id = None)
        folders_docs = await asyncio.to_thread(
            user_manager.list_folders,
            user_id=user_id,
            parent_id=None,  # Root folders only
        )

        # 2. Get root files (folder_id = None)
        root_files_docs = await asyncio.to_thread(
            user_manager.list_user_files,
            user_id=user_id,
            folder_id=None,  # Root files only
            limit=1000,
        )

        # Build root files list
        root_files = []
        for doc in root_files_docs:
            file_data = {
                "id": doc.get("file_id"),
                "filename": doc.get("filename"),
                "original_name": doc.get("original_name"),
                "file_type": doc.get("file_type"),
                "file_size": doc.get("file_size"),
                "folder_id": doc.get("folder_id"),
                "user_id": doc.get("user_id"),
                "r2_key": doc.get("r2_key"),
                "created_at": doc.get("uploaded_at"),
                "updated_at": doc.get("updated_at"),
            }
            root_files.append(FileResponse(**file_data))

        # 3. For each folder, get its files
        folders_with_files = []
        total_files = len(root_files)

        for folder_doc in folders_docs:
            folder_id = folder_doc.get("folder_id")

            # Get files in this folder
            folder_files_docs = await asyncio.to_thread(
                user_manager.list_user_files,
                user_id=user_id,
                folder_id=folder_id,
                limit=1000,
            )

            folder_files = []
            for doc in folder_files_docs:
                file_data = {
                    "id": doc.get("file_id"),
                    "filename": doc.get("filename"),
                    "original_name": doc.get("original_name"),
                    "file_type": doc.get("file_type"),
                    "file_size": doc.get("file_size"),
                    "folder_id": doc.get("folder_id"),
                    "user_id": doc.get("user_id"),
                    "r2_key": doc.get("r2_key"),
                    "created_at": doc.get("uploaded_at"),
                    "updated_at": doc.get("updated_at"),
                }
                folder_files.append(FileResponse(**file_data))

            total_files += len(folder_files)

            # Build folder response
            folder_response = FolderResponse(
                id=folder_doc.get("folder_id"),
                name=folder_doc.get("name"),
                description=folder_doc.get("description"),
                parent_id=folder_doc.get("parent_id"),
                user_id=folder_doc.get("user_id"),
                created_at=folder_doc.get("created_at"),
                updated_at=folder_doc.get("updated_at"),
                file_count=len(folder_files),
            )

            folders_with_files.append(
                FolderWithFiles(folder=folder_response, files=folder_files)
            )

        # Build final response
        result = FileSystemStructure(
            root_files=root_files,
            folders=folders_with_files,
            total_files=total_files,
            total_folders=len(folders_docs),
        )

        logger.info(
            f"✅ File system structure: {len(folders_docs)} folders, {total_files} total files"
        )
        return result

    except Exception as e:
        logger.error(f"❌ Failed to get file system structure: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file system")


@router.get("/files/{file_id}", response_model=FileDownloadResponse)
async def get_file(
    file_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Get file details with download URL (on-demand signed URL generation)"""
    try:
        user_id = user_data.get("uid")

        if s3_client is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable")

        # 🔍 FIRST: Try to find in MongoDB user_files collection (new uploads + split files)
        user_manager = get_user_manager()
        file_doc = await asyncio.to_thread(
            user_manager.get_file_by_id, file_id, user_id
        )

        if file_doc and not file_doc.get("is_deleted", False):
            # ✅ Found in MongoDB - generate signed URL
            r2_key = file_doc.get("r2_key")
            download_url = generate_signed_url(r2_key, expiration=3600)

            file_data = {
                "id": file_doc.get("file_id"),
                "filename": file_doc.get("filename"),
                "original_name": file_doc.get("original_name"),
                "file_type": file_doc.get("file_type"),
                "file_size": file_doc.get("file_size"),
                "folder_id": file_doc.get("folder_id"),
                "user_id": file_doc.get("user_id"),
                "r2_key": r2_key,
                "download_url": download_url,
                "created_at": file_doc.get("uploaded_at"),
                "updated_at": file_doc.get("updated_at"),
            }

            logger.info(f"✅ Found file in MongoDB: {file_id}")
            return FileDownloadResponse(**file_data)

        # 🔍 FALLBACK: Search in R2 for files not in MongoDB
        prefix = f"uploads/{user_id}/"
        logger.info(f"🔍 Searching for file {file_id} in R2 with prefix: {prefix}")

        try:
            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix=prefix, MaxKeys=1000
            )

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Pattern: uploads/{user_id}/{file_id}.ext or {file_id}_part{N}.ext
                    if f"/{file_id}" in key or f"/{file_id}_" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 3:  # uploads/{user_id}/{filename}
                            filename = key_parts[2]  # file_xxx.pdf
                            # Extract file_id from filename (before .ext or _part)
                            found_file_id = filename.split(".")[0].split("_part")[0]

                            # Check exact match OR prefix match (multipart)
                            if found_file_id == file_id or filename.startswith(
                                f"{file_id}_"
                            ):
                                # filename is already just the base name (e.g., file_xxx.pdf)
                                original_name = filename

                                file_ext = Path(filename).suffix.lower()

                                # ✅ Generate signed URL for single file download (on-demand)
                                download_url = generate_signed_url(key, expiration=3600)

                                file_data = {
                                    "id": file_id,
                                    "filename": filename,
                                    "original_name": original_name,
                                    "file_type": file_ext,
                                    "file_size": obj["Size"],
                                    "folder_id": None,  # uploads/ pattern has no folder in path
                                    "user_id": user_id,
                                    "r2_key": key,
                                    "download_url": download_url,
                                    "created_at": obj["LastModified"],
                                    "updated_at": obj["LastModified"],
                                }

                                logger.info(f"✅ Found file {file_id}: {filename}")

                                # 🔍 Check if this file has been converted to document
                                try:
                                    from src.api.document_editor_routes import (
                                        get_document_manager,
                                    )

                                    doc_manager = get_document_manager()
                                    existing_doc = await asyncio.to_thread(
                                        doc_manager.get_document_by_file_id,
                                        file_id,
                                        user_id,
                                    )
                                    if existing_doc:
                                        logger.warning(
                                            f"🔍 FILE DEBUG: file_id={file_id} → "
                                            f"DOCUMENT EXISTS: {existing_doc['document_id']}"
                                        )
                                        logger.warning(
                                            f"🔍 FRONTEND: If user clicks Edit, call GET /api/documents/file/{file_id}"
                                        )
                                        logger.warning(
                                            f"🔍 FRONTEND: Response will have document_id={existing_doc['document_id']}"
                                        )
                                        logger.warning(
                                            f"🔍 FRONTEND: Must save to PUT /api/documents/{existing_doc['document_id']}/"
                                        )
                                    else:
                                        logger.warning(
                                            f"📝 FILE DEBUG: file_id={file_id} → NO DOCUMENT YET"
                                        )
                                        logger.warning(
                                            f"📝 FRONTEND: First time Edit will create new document"
                                        )
                                except Exception as doc_check_error:
                                    logger.error(
                                        f"❌ ERROR checking document for file {file_id}: {doc_check_error}"
                                    )
                                    import traceback

                                    logger.error(traceback.format_exc())

                                return FileDownloadResponse(**file_data)

            # File not found
            logger.warning(f"❌ File {file_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="File not found")

        except HTTPException:
            raise
        except Exception as s3_error:
            logger.error(f"❌ R2 search error: {s3_error}")
            raise HTTPException(status_code=500, detail="Failed to search file")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get file: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file")


@router.put("/files/{file_id}", response_model=FileDownloadResponse)
async def update_file(
    file_id: str,
    file_update: FileUpdate,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update file metadata (filename and/or folder_id)
    - Can rename file
    - Can move file to different folder
    - File content in R2 will be moved/renamed accordingly
    - Returns updated file with fresh download URL
    """
    try:
        user_id = user_data.get("uid")
        user_email = user_data.get("email", "unknown")

        logger.info("=" * 80)
        logger.info(f"📝 FILE UPDATE REQUEST for file_id: {file_id}")
        logger.info(f"   User: {user_email} (UID: {user_id})")
        logger.info(f"   New filename: {file_update.filename}")
        logger.info(f"   New folder_id: {file_update.folder_id}")

        if s3_client is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable")

        # Step 1: Try to get file from MongoDB first (has r2_key)
        user_manager = get_user_manager()
        file_doc = await asyncio.to_thread(
            user_manager.get_file_by_id, file_id, user_id
        )

        old_key = None
        old_metadata = None

        if file_doc and file_doc.get("r2_key"):
            # ✅ Found in MongoDB with r2_key
            old_key = file_doc.get("r2_key")
            logger.info(f"   ✅ Found file in MongoDB: {old_key}")

            # Get file info from R2
            try:
                obj_info = s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=old_key)
                old_metadata = {
                    "size": obj_info["ContentLength"],
                    "last_modified": obj_info["LastModified"],
                    "old_filename": old_key.split("/")[-1],
                }
                logger.info(f"   📦 File size: {old_metadata['size']} bytes")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not get R2 file info: {e}")
                # Use MongoDB data
                old_metadata = {
                    "size": file_doc.get("file_size", 0),
                    "last_modified": file_doc.get("last_modified"),
                    "old_filename": file_doc.get("filename"),
                }
        else:
            # Fallback: Search in R2 (for files not in MongoDB)
            logger.info(f"   🔍 File not in MongoDB, searching R2...")
            prefix = f"uploads/{user_id}/"
            logger.info(f"   🔍 Searching with prefix: {prefix}")

            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix=prefix, MaxKeys=1000
            )

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]
                    # Pattern: uploads/{user_id}/{file_id}.ext
                    if f"/{file_id}" in key or f"/{file_id}_" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 3:  # uploads/{user_id}/{filename}
                            old_filename = key_parts[2]
                            # Extract file_id from filename (before .ext)
                            found_file_id = old_filename.rsplit(".", 1)[0]
                            # Check exact match OR prefix match
                            if found_file_id == file_id or old_filename.startswith(
                                f"{file_id}_"
                            ):
                                old_key = key
                                old_metadata = {
                                    "size": obj["Size"],
                                    "last_modified": obj["LastModified"],
                                    "old_filename": old_filename,
                                }
                                logger.info(
                                    f"   🎯 Matched file_id: {found_file_id} (searching for: {file_id})"
                                )
                                break

        if not old_key:
            logger.warning(f"❌ File {file_id} not found for update")
            if file_doc:
                logger.warning(f"   MongoDB file: {file_doc.get('filename')}")
                logger.warning(f"   MongoDB r2_key: {file_doc.get('r2_key')}")
            else:
                prefix = f"uploads/{user_id}/"
                logger.warning(f"   Searched prefix: {prefix}")
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"   ✅ Found file: {old_key}")
        logger.info(f"   📦 Current size: {old_metadata['size']} bytes")

        # Step 2: Get new filename (if renaming)
        if file_update.filename:
            # User wants to rename
            # Keep extension from original file
            old_ext = Path(old_metadata["old_filename"]).suffix
            new_filename = f"{file_id}{old_ext}"  # file_xxx.pdf
            logger.info(f"   ✏️  Renaming to: {new_filename}")
        else:
            # Keep old filename
            new_filename = old_metadata["old_filename"]
            logger.info(f"   ✏️  Keeping filename: {new_filename}")

        # Step 3: Check folder_id (for MongoDB only, R2 path doesn't change)
        new_folder_id = file_update.folder_id
        if new_folder_id and new_folder_id.lower() in ["default", "root", ""]:
            logger.info(f"   ⚠️  Converting folder_id '{new_folder_id}' → None (root)")
            new_folder_id = None

        # Step 4: Build new R2 key (ALWAYS uploads/ pattern)
        new_key = f"uploads/{user_id}/{new_filename}"

        logger.info(f"   🔑 Old key: {old_key}")
        logger.info(f"   🔑 New key: {new_key}")

        # Step 5: Copy file to new location if key changed (only for renames)
        if old_key != new_key:
            logger.info("   📦 Copying file to new location...")

            # Copy object to new location
            s3_client.copy_object(
                Bucket=R2_BUCKET_NAME,
                CopySource={"Bucket": R2_BUCKET_NAME, "Key": old_key},
                Key=new_key,
            )
            logger.info("   ✅ File copied successfully")

            # Delete old file
            logger.info("   🗑️  Deleting old file...")
            s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=old_key)
            logger.info("   ✅ Old file deleted")
        else:
            logger.info("   ℹ️  No changes to filename, skipping copy")

        # Step 6: UPDATE MONGODB
        logger.info("   💾 Updating file metadata in MongoDB...")
        user_manager = get_user_manager()

        update_data = {
            "filename": new_filename,
            "r2_key": new_key,
            "last_modified": datetime.utcnow(),
        }

        # Add folder_id if provided
        if file_update.folder_id is not None:
            update_data["folder_id"] = new_folder_id

        # Add original_name if user renamed the file
        if file_update.filename:
            update_data["original_name"] = file_update.filename

        db_updated = await asyncio.to_thread(
            user_manager.update_file_metadata,
            file_id=file_id,
            user_id=user_id,
            update_data=update_data,
        )

        if db_updated:
            logger.info("   ✅ MongoDB updated successfully!")
            logger.info(f"      - filename: {new_filename}")
            logger.info(f"      - r2_key: {new_key}")
            if new_folder_id:
                logger.info(f"      - folder_id: {new_folder_id}")
        else:
            logger.warning("   ⚠️  MongoDB update failed or no changes detected")

        # Step 7: Generate new signed URL
        logger.info("   🔐 Generating signed URL for updated file...")
        download_url = generate_signed_url(new_key, expiration=3600)

        file_ext = Path(new_filename).suffix.lower()

        # Step 8: Build response
        now = datetime.utcnow()
        file_data = {
            "id": file_id,
            "filename": new_filename,
            "original_name": file_update.filename or new_filename,
            "file_type": file_ext,
            "file_size": old_metadata["size"],
            "folder_id": new_folder_id,
            "user_id": user_id,
            "r2_key": new_key,
            "download_url": download_url,
            "created_at": old_metadata["last_modified"],
            "updated_at": now,
        }

        logger.info("✅ FILE UPDATE COMPLETED!")
        logger.info(f"   📄 File ID: {file_id}")
        logger.info(f"   📁 New filename: {original_name}")
        logger.info(f"   📂 New folder: {new_folder_id or 'root'}")
        logger.info("=" * 80)

        return FileDownloadResponse(**file_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ FILE UPDATE FAILED for {file_id}")
        logger.error(f"   Error Type: {type(e).__name__}")
        logger.error(f"   Error Message: {str(e)}")
        logger.error(f"   User: {user_data.get('email', 'unknown')}")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Generates a short-lived signed URL and redirects the client to download the file.
    """
    try:
        user_id = user_data.get("uid")

        if s3_client is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable")

        # Search for the file's key
        prefix = f"files/{user_id}/"
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix)

        file_key = None
        for page in pages:
            if "Contents" not in page:
                continue
            for obj in page["Contents"]:
                key = obj["Key"]
                # Support multipart files: file_xxx_part1_xxx
                if f"/{file_id}/" in key or f"/{file_id}_" in key:
                    key_parts = key.split("/")
                    if len(key_parts) >= 4:
                        found_file_id = key_parts[3]
                        # Check exact or prefix match
                        if found_file_id == file_id or found_file_id.startswith(
                            f"{file_id}_"
                        ):
                            file_key = key
                            logger.info(
                                f"   🎯 Matched file_id: {found_file_id} (searching for: {file_id})"
                            )
                            break
            if file_key:
                break

        if not file_key:
            logger.warning(f"Download request for non-existent file_id: {file_id}")
            raise HTTPException(status_code=404, detail="File not found")

        # Generate a short-lived signed URL (e.g., 5 minutes)
        download_url = generate_signed_url(file_key, expiration=300)

        logger.info(f"Redirecting user {user_data.get('email')} to download {file_id}")
        return RedirectResponse(url=download_url, status_code=307)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate download redirect for {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not process file download")


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Delete file from R2 storage"""
    try:
        user_id = user_data.get("uid")
        user_email = user_data.get("email", "unknown")

        if s3_client is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable")

        # Search for file to get its key
        prefix = f"uploads/{user_id}/"
        logger.info(f"🔍 Searching for file {file_id} to delete")

        try:
            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix=prefix, MaxKeys=1000
            )

            file_key = None
            filename = None

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Pattern: uploads/{user_id}/{file_id}.ext or {file_id}_part{N}.ext
                    if f"/{file_id}" in key or f"/{file_id}_" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 3:  # uploads/{user_id}/{filename}
                            filename = key_parts[2]
                            # Extract file_id from filename
                            found_file_id = filename.split(".")[0].split("_part")[0]
                            # Check exact match OR prefix match (multipart)
                            if found_file_id == file_id or filename.startswith(
                                f"{file_id}_"
                            ):
                                file_key = key
                                logger.info(
                                    f"   🎯 Matched file_id: {found_file_id} (searching for: {file_id})"
                                )
                                break

            if not file_key:
                logger.warning(f"❌ File {file_id} not found for deletion")
                raise HTTPException(status_code=404, detail="File not found")

            # Note: We do NOT delete related documents because:
            # - User may have created documents from this file
            # - Those documents belong to the user, not the file
            # - Cache will auto-invalidate since file won't exist

            # Delete the file from R2
            s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=file_key)

            # Also mark as deleted in MongoDB (soft delete)
            user_manager = get_user_manager()
            await asyncio.to_thread(
                user_manager.update_file_metadata,
                file_id=file_id,
                user_id=user_id,
                update_data={"is_deleted": True, "last_modified": datetime.utcnow()},
            )

            logger.info(
                f"✅ Deleted file {filename} (ID: {file_id}) for user {user_email}"
            )
            logger.info(f"   R2 Key: {file_key}")

            return {
                "success": True,
                "message": "File deleted successfully",
                "file_id": file_id,
                "filename": filename,
            }

        except HTTPException:
            raise
        except Exception as s3_error:
            logger.error(f"❌ R2 delete error: {s3_error}")
            raise HTTPException(
                status_code=500, detail="Failed to delete file from storage"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")


@router.post("/files/{file_id}/generate-download-url")
async def generate_file_download_url(
    file_id: str,
    expiration: int = Query(
        3600, description="URL expiration in seconds (default 1 hour)", ge=300, le=86400
    ),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Generate new signed URL for file download"""
    try:
        user_id = user_data.get("uid")

        if s3_client is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable")

        # Find the file first
        prefix = f"files/{user_id}/"

        try:
            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix=prefix, MaxKeys=1000
            )

            file_key = None

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Check if this key contains our file_id (support multipart)
                    if f"/{file_id}/" in key or f"/{file_id}_" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 4:
                            found_file_id = key_parts[3]
                            # Check exact match OR prefix match (multipart)
                            if found_file_id == file_id or found_file_id.startswith(
                                f"{file_id}_"
                            ):
                                file_key = key
                                logger.info(
                                    f"   🎯 Matched file_id: {found_file_id} (searching for: {file_id})"
                                )
                                break

            if not file_key:
                logger.warning(f"❌ File {file_id} not found for signed URL generation")
                raise HTTPException(status_code=404, detail="File not found")

            # Generate new signed URL
            signed_url = generate_signed_url(file_key, expiration=expiration)

            logger.info(
                f"✅ Generated signed URL for file {file_id} (expires in {expiration}s)"
            )

            return {
                "success": True,
                "file_id": file_id,
                "download_url": signed_url,
                "expires_in": expiration,
                "expires_at": (
                    datetime.utcnow() + timedelta(seconds=expiration)
                ).isoformat(),
            }

        except HTTPException:
            raise
        except Exception as s3_error:
            logger.error(f"❌ Failed to generate signed URL: {s3_error}")
            raise HTTPException(
                status_code=500, detail="Failed to generate download URL"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL")


# ===== UTILITY ENDPOINTS =====


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Simple File Management API",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# FILE TRASH MANAGEMENT
# ============================================================================


@router.delete("/files/{file_id}/trash")
async def move_file_to_trash(
    file_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Move file to trash (soft delete)
    File is not physically deleted from R2, just marked as deleted in MongoDB
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(f"🗑️ Moving file {file_id} to trash for user {user_id}")

        success = await asyncio.to_thread(
            user_manager.soft_delete_file,
            file_id=file_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(status_code=404, detail="File not found")

        return {
            "success": True,
            "message": f"File {file_id} moved to trash",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error moving file to trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/trash/list", response_model=List[FileResponse])
async def list_trash_files(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List files in trash (soft-deleted files)
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(f"🗑️ Listing trash files for user {user_id}")

        files_docs = await asyncio.to_thread(
            user_manager.list_deleted_files,
            user_id=user_id,
            limit=1000,
        )

        files = []
        for doc in files_docs:
            file_data = {
                "id": doc.get("file_id"),
                "filename": doc.get("filename"),
                "original_name": doc.get("original_name"),
                "file_type": doc.get("file_type"),
                "file_size": doc.get("file_size"),
                "folder_id": doc.get("folder_id"),
                "user_id": doc.get("user_id"),
                "r2_key": doc.get("r2_key"),
                "created_at": doc.get("uploaded_at"),
                "updated_at": doc.get("deleted_at"),  # Show when deleted
            }
            files.append(FileResponse(**file_data))

        logger.info(f"✅ Found {len(files)} files in trash")
        return files

    except Exception as e:
        logger.error(f"❌ Error listing trash files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list trash")


@router.post("/files/{file_id}/restore")
async def restore_file_from_trash(
    file_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Restore file from trash
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(f"♻️ Restoring file {file_id} from trash for user {user_id}")

        success = await asyncio.to_thread(
            user_manager.restore_file,
            file_id=file_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(status_code=404, detail="File not found in trash")

        return {
            "success": True,
            "message": f"File {file_id} restored from trash",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_id}/permanent")
async def permanent_delete_file(
    file_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Permanently delete file from R2 and MongoDB
    ⚠️ WARNING: This action cannot be undone!

    Use this to delete a specific file from trash permanently.
    The file will be removed from both R2 storage and MongoDB.
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(f"💀 Permanently deleting file {file_id} for user {user_id}")

        success = await asyncio.to_thread(
            user_manager.permanent_delete_file,
            file_id=file_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="File not found or already deleted"
            )

        return {
            "success": True,
            "message": f"File {file_id} permanently deleted",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error permanently deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/trash/empty")
async def empty_files_trash(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Permanently delete ALL files in trash
    ⚠️ WARNING: This action cannot be undone!

    This will:
    1. Find all files with is_deleted=true for current user
    2. Calculate total storage to free
    3. Delete each file from R2 storage
    4. Delete each file record from MongoDB
    5. Decrease storage_used_mb
    """
    try:
        user_id = user_data.get("uid")
        user_manager = get_user_manager()

        logger.info(f"💀 Emptying files trash for user {user_id}")

        # Get deleted files to calculate storage
        deleted_files = await asyncio.to_thread(
            user_manager.list_deleted_files, user_id=user_id, limit=10000
        )

        # Calculate total storage to free
        total_bytes_freed = sum(
            file_doc.get("file_size", 0) for file_doc in deleted_files
        )
        total_mb_freed = total_bytes_freed / (1024 * 1024)

        # Delete files
        deleted_count = await asyncio.to_thread(
            user_manager.empty_files_trash,
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
                    f"📊 Decreased storage by {total_mb_freed:.2f}MB ({deleted_count} files)"
                )
            except Exception as usage_error:
                logger.error(f"❌ Error updating storage counter: {usage_error}")

        return {
            "success": True,
            "message": f"Permanently deleted {deleted_count} files from trash",
            "deleted_count": deleted_count,
            "storage_freed_mb": round(total_mb_freed, 2),
        }

    except Exception as e:
        logger.error(f"❌ Error emptying files trash: {e}")
        raise HTTPException(status_code=500, detail=str(e))
