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

# Load environment variables
load_dotenv()

from src.middleware.auth import verify_firebase_token

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
    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    folder_id: Optional[str]
    user_id: str
    r2_key: str  # Changed from r2_url to r2_key for private storage
    private_url: str  # Private R2 URL (not accessible without auth)
    download_url: str  # Signed URL for temporary access
    created_at: datetime
    updated_at: datetime


# Allowed file types
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "application/rtf",
}


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
        if s3_client is None:
            raise HTTPException(
                status_code=500, detail="R2 storage not configured properly"
            )

        # Upload without ACL (private by default)
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=file_content,
            ContentType=content_type,
            # Remove ACL="public-read" to make it private
        )

        # Return private R2 URL (not publicly accessible)
        private_url = f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}/{key}"
        logger.info(f"✅ Uploaded to private R2: {key}")
        return private_url

    except Exception as e:
        logger.error(f"Failed to upload to R2: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def generate_signed_url(key: str, expiration: int = 3600) -> str:
    """Generate signed URL for private R2 file access"""
    try:
        if s3_client is None:
            raise HTTPException(status_code=500, detail="R2 client not available")

        # Generate presigned URL for GET request
        signed_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expiration,  # URL expires in 1 hour by default
        )

        return signed_url

    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate access URL: {str(e)}"
        )


def get_private_file_url(key: str) -> str:
    """Get private file URL (not publicly accessible)"""
    return f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}/{key}"


# ===== FOLDER CRUD ENDPOINTS =====


@router.post("/folders", response_model=FolderResponse)
async def create_folder(
    folder: FolderCreate, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Create new folder"""
    try:
        user_id = user_data.get("uid")
        folder_id = f"folder_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # In real app, save to database
        # For now, return mock response
        folder_data = {
            "id": folder_id,
            "name": folder.name,
            "description": folder.description,
            "parent_id": folder.parent_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "file_count": 0,
        }

        logger.info(
            f"✅ Created folder {folder.name} for user {user_data.get('email')}"
        )

        return FolderResponse(**folder_data)

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
    """List folders for user"""
    try:
        user_id = user_data.get("uid")

        # Mock data - in real app, fetch from database
        mock_folders = [
            {
                "id": "folder_default001",
                "name": "Documents",
                "description": "Default documents folder",
                "parent_id": parent_id,
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "file_count": 0,
            }
        ]

        return [FolderResponse(**folder) for folder in mock_folders]

    except Exception as e:
        logger.error(f"❌ Failed to list folders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list folders")


@router.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Get folder details"""
    try:
        user_id = user_data.get("uid")

        # Mock data
        folder_data = {
            "id": folder_id,
            "name": "Sample Folder",
            "description": "Sample folder description",
            "parent_id": None,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "file_count": 0,
        }

        return FolderResponse(**folder_data)

    except Exception as e:
        logger.error(f"❌ Failed to get folder: {e}")
        raise HTTPException(status_code=404, detail="Folder not found")


@router.put("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Update folder"""
    try:
        user_id = user_data.get("uid")
        now = datetime.utcnow()

        # Mock updated data
        folder_data = {
            "id": folder_id,
            "name": folder_update.name or "Updated Folder",
            "description": folder_update.description,
            "parent_id": None,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": now,
            "file_count": 0,
        }

        logger.info(f"✅ Updated folder {folder_id} for user {user_data.get('email')}")

        return FolderResponse(**folder_data)

    except Exception as e:
        logger.error(f"❌ Failed to update folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to update folder")


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Delete folder"""
    try:
        user_id = user_data.get("uid")

        # In real app: check if folder is empty, delete from database

        logger.info(f"✅ Deleted folder {folder_id} for user {user_data.get('email')}")

        return {"success": True, "message": "Folder deleted successfully"}

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

        # Validate file type
        ext, content_type = get_file_extension_and_type(
            file.filename, file.content_type
        )

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Generate unique filename
        file_id = f"file_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename.replace(' ', '_')}"

        # R2 key structure: files/{user_id}/{folder_id}/{file_id}/{filename}
        if folder_id:
            r2_key = f"files/{user_id}/{folder_id}/{file_id}/{safe_filename}"
        else:
            r2_key = f"files/{user_id}/root/{file_id}/{safe_filename}"

        # Upload to R2 private storage
        private_url = await upload_to_r2(file_content, r2_key, content_type)

        # Generate signed URL for download (expires in 1 hour)
        download_url = generate_signed_url(r2_key, expiration=3600)

        # Create file record
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

        # In real app: save file record to database

        logger.info(
            f"✅ Uploaded file {file.filename} ({file_size} bytes) for user {user_email}"
        )
        logger.info(f"   R2 Key: {r2_key}")
        logger.info(f"   Private URL: {private_url}")

        return FileResponse(**file_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files", response_model=List[FileResponse])
async def list_files(
    folder_id: Optional[str] = Query(None, description="Folder ID to list files from"),
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """List files for user (from R2 storage)"""
    try:
        user_id = user_data.get("uid")

        if s3_client is None:
            logger.warning("R2 client not available, returning empty list")
            return []

        # Build S3 prefix based on folder_id
        if folder_id:
            prefix = f"files/{user_id}/{folder_id}/"
        else:
            prefix = f"files/{user_id}/root/"

        logger.info(f"🔍 Listing files with prefix: {prefix}")

        # List objects from R2
        try:
            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix=prefix, MaxKeys=100
            )

            files = []

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Skip if it's just a folder marker
                    if key.endswith("/"):
                        continue

                    # Parse file info from key
                    # Format: files/{user_id}/{folder_id}/{file_id}/{filename}
                    key_parts = key.split("/")
                    if len(key_parts) >= 4:
                        folder_part = key_parts[2]  # folder_id or 'root'
                        file_id = key_parts[3]
                        filename = key_parts[4] if len(key_parts) > 4 else key_parts[3]

                        # Extract original name (remove timestamp prefix)
                        original_name = filename
                        if "_" in filename and len(filename.split("_", 1)) > 1:
                            timestamp_part, name_part = filename.split("_", 1)
                            if len(timestamp_part) == 15:  # YYYYMMDD_HHMMSS format
                                original_name = name_part

                        # Get file extension
                        file_ext = Path(filename).suffix.lower()

                        # Generate signed URL for download
                        download_url = generate_signed_url(key, expiration=3600)
                        private_url = get_private_file_url(key)

                        # Create file response
                        file_data = {
                            "id": file_id,
                            "filename": filename,
                            "original_name": original_name,
                            "file_type": file_ext,
                            "file_size": obj["Size"],
                            "folder_id": folder_part if folder_part != "root" else None,
                            "user_id": user_id,
                            "r2_key": key,
                            "private_url": private_url,
                            "download_url": download_url,
                            "created_at": obj["LastModified"],
                            "updated_at": obj["LastModified"],
                        }

                        files.append(FileResponse(**file_data))

            logger.info(f"✅ Found {len(files)} files in folder {folder_id or 'root'}")
            return files

        except Exception as s3_error:
            logger.error(f"❌ R2 list error: {s3_error}")
            return []

    except Exception as e:
        logger.error(f"❌ Failed to list files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


@router.get("/files/all", response_model=List[FileResponse])
async def list_all_files(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """List all files for user (across all folders)"""
    try:
        user_id = user_data.get("uid")

        if s3_client is None:
            logger.warning("R2 client not available, returning empty list")
            return []

        # List all files for user
        prefix = f"files/{user_id}/"
        logger.info(f"🔍 Listing all files with prefix: {prefix}")

        try:
            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME,
                Prefix=prefix,
                MaxKeys=1000,  # Increased limit for all files
            )

            files = []

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Skip if it's just a folder marker
                    if key.endswith("/"):
                        continue

                    # Parse file info from key
                    key_parts = key.split("/")
                    if len(key_parts) >= 4:
                        folder_part = key_parts[2]
                        file_id = key_parts[3]
                        filename = key_parts[4] if len(key_parts) > 4 else key_parts[3]

                        # Extract original name
                        original_name = filename
                        if "_" in filename and len(filename.split("_", 1)) > 1:
                            timestamp_part, name_part = filename.split("_", 1)
                            if len(timestamp_part) == 15:
                                original_name = name_part

                        file_ext = Path(filename).suffix.lower()

                        # Generate signed URL for download
                        download_url = generate_signed_url(key, expiration=3600)
                        private_url = get_private_file_url(key)

                        file_data = {
                            "id": file_id,
                            "filename": filename,
                            "original_name": original_name,
                            "file_type": file_ext,
                            "file_size": obj["Size"],
                            "folder_id": folder_part if folder_part != "root" else None,
                            "user_id": user_id,
                            "r2_key": key,
                            "private_url": private_url,
                            "download_url": download_url,
                            "created_at": obj["LastModified"],
                            "updated_at": obj["LastModified"],
                        }

                        files.append(FileResponse(**file_data))

            # Sort by created date (newest first)
            files.sort(key=lambda x: x.created_at, reverse=True)

            logger.info(f"✅ Found {len(files)} total files for user")
            return files

        except Exception as s3_error:
            logger.error(f"❌ R2 list error: {s3_error}")
            return []

    except Exception as e:
        logger.error(f"❌ Failed to list all files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """Get file details by searching R2 storage"""
    try:
        user_id = user_data.get("uid")

        if s3_client is None:
            raise HTTPException(status_code=503, detail="Storage service unavailable")

        # Search for file across all folders for this user
        prefix = f"files/{user_id}/"
        logger.info(f"🔍 Searching for file {file_id} with prefix: {prefix}")

        try:
            response = s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix=prefix, MaxKeys=1000
            )

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    # Check if this key contains our file_id
                    if f"/{file_id}/" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 4:
                            folder_part = key_parts[2]
                            found_file_id = key_parts[3]
                            filename = (
                                key_parts[4] if len(key_parts) > 4 else key_parts[3]
                            )

                            if found_file_id == file_id:
                                # Extract original name
                                original_name = filename
                                if "_" in filename and len(filename.split("_", 1)) > 1:
                                    timestamp_part, name_part = filename.split("_", 1)
                                    if len(timestamp_part) == 15:
                                        original_name = name_part

                                file_ext = Path(filename).suffix.lower()

                                # Generate signed URL for download
                                download_url = generate_signed_url(key, expiration=3600)
                                private_url = get_private_file_url(key)

                                file_data = {
                                    "id": file_id,
                                    "filename": filename,
                                    "original_name": original_name,
                                    "file_type": file_ext,
                                    "file_size": obj["Size"],
                                    "folder_id": (
                                        folder_part if folder_part != "root" else None
                                    ),
                                    "user_id": user_id,
                                    "r2_key": key,
                                    "private_url": private_url,
                                    "download_url": download_url,
                                    "created_at": obj["LastModified"],
                                    "updated_at": obj["LastModified"],
                                }

                                logger.info(f"✅ Found file {file_id}: {filename}")
                                return FileResponse(**file_data)

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
                if f"/{file_id}/" in key:
                    file_key = key
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
        prefix = f"files/{user_id}/"
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

                    # Check if this key contains our file_id
                    if f"/{file_id}/" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 4:
                            found_file_id = key_parts[3]
                            if found_file_id == file_id:
                                file_key = key
                                filename = (
                                    key_parts[4] if len(key_parts) > 4 else key_parts[3]
                                )
                                break

            if not file_key:
                logger.warning(f"❌ File {file_id} not found for deletion")
                raise HTTPException(status_code=404, detail="File not found")

            # Delete the file from R2
            s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=file_key)

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

                    # Check if this key contains our file_id
                    if f"/{file_id}/" in key:
                        key_parts = key.split("/")
                        if len(key_parts) >= 4:
                            found_file_id = key_parts[3]
                            if found_file_id == file_id:
                                file_key = key
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
