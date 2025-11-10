"""
Share API Routes
File Sharing System (Phase 2)
"""

import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

from src.middleware.auth import verify_firebase_token
from src.services.share_manager import ShareManager
from src.services.notification_manager import NotificationManager
from config.config import get_mongodb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shares", tags=["File Sharing"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class CreateShareRequest(BaseModel):
    """Create share request"""

    recipient_email: EmailStr
    file_id: str
    file_type: str = Field(..., pattern="^(upload|document|library)$")
    permission: str = Field("view", pattern="^(view|download|edit)$")
    expires_at: Optional[datetime] = None
    send_notification: bool = Field(
        True, description="Send InApp and Email notification to recipient"
    )


class UpdateShareRequest(BaseModel):
    """Update share request"""

    permission: str = Field(..., pattern="^(view|download|edit)$")
    expires_at: Optional[datetime] = None


class ShareResponse(BaseModel):
    """Share response model"""

    share_id: str
    owner_id: str
    recipient_id: str
    recipient_email: str
    file_id: str
    file_type: str
    filename: str
    document_type: Optional[str] = None  # doc/slide/note for documents, null for others
    is_encrypted: Optional[bool] = (
        False  # True for Secret Images/Documents, False otherwise
    )
    permission: str
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ShareLogResponse(BaseModel):
    """Share access log response"""

    log_id: str
    share_id: str
    user_id: str
    action: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    accessed_at: datetime


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_share_manager() -> ShareManager:
    """Get ShareManager instance"""
    db = get_mongodb()
    return ShareManager(db=db)


def get_notification_manager() -> NotificationManager:
    """Get NotificationManager instance"""
    db = get_mongodb()
    return NotificationManager(db=db)


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request"""
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request"""
    return request.headers.get("user-agent")


# ============================================================================
# SHARE MANAGEMENT
# ============================================================================


@router.post("/create", response_model=ShareResponse)
async def create_share(
    share_request: CreateShareRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Create a new file share

    **Permission levels:**
    - `view`: Can view file details only
    - `download`: Can view and download file
    - `edit`: Can view, download, and edit file (documents only)

    **File types:**
    - `upload`: Upload Files (Type 1)
    - `document`: Documents (Type 2)
    - `library`: Library Files (Type 3)

    **Notification:**
    - Set `send_notification: true` to send InApp + Email notification to recipient
    """
    try:
        user_id = user_data.get("uid")
        user_name = user_data.get("name", user_data.get("email", "Someone"))

        share_manager = get_share_manager()

        share = await asyncio.to_thread(
            share_manager.create_share,
            owner_id=user_id,
            recipient_email=share_request.recipient_email,
            file_id=share_request.file_id,
            file_type=share_request.file_type,
            permission=share_request.permission,
            expires_at=share_request.expires_at,
        )

        logger.info(
            f"✅ Share created: {share['share_id']} by {user_id} to {share_request.recipient_email}"
        )

        # Send notification if requested
        if share_request.send_notification:
            try:
                notification_manager = get_notification_manager()

                # Create InApp notification
                notification = await asyncio.to_thread(
                    notification_manager.create_share_notification,
                    recipient_id=share.get("recipient_id"),
                    owner_id=user_id,
                    owner_name=user_name,
                    file_id=share.get("file_id"),
                    filename=share.get("filename"),
                    file_type=share.get("file_type"),
                    permission=share.get("permission"),
                    share_id=share.get("share_id"),
                )

                if notification:
                    logger.info(
                        f"✅ InApp notification sent to {share_request.recipient_email}"
                    )

                # Send Email notification via Brevo
                # Get recipient info from users collection
                from config.config import get_mongodb

                db = get_mongodb()
                recipient = db["users"].find_one({"uid": share.get("recipient_id")})
                recipient_name = (
                    recipient.get("name", recipient.get("email", "User"))
                    if recipient
                    else "User"
                )

                await asyncio.to_thread(
                    notification_manager.send_share_email_notification,
                    recipient_email=share_request.recipient_email,
                    recipient_name=recipient_name,
                    owner_name=user_name,
                    filename=share.get("filename"),
                    permission=share.get("permission"),
                )

                logger.info(
                    f"✅ Email notification sent to {share_request.recipient_email}"
                )

            except Exception as notif_error:
                logger.error(f"⚠️ Failed to send notification: {notif_error}")
                # Continue even if notification fails

        return ShareResponse(**share)

    except ValueError as e:
        logger.warning(f"⚠️ Create share failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error creating share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-shares", response_model=List[ShareResponse])
async def list_my_shares(
    file_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List files I have shared with others

    **Query parameters:**
    - `file_type`: Filter by file type (upload, document, library)
    - `is_active`: Filter by active status (true/false)
    - `limit`: Max results (default: 100)
    - `offset`: Pagination offset (default: 0)
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        shares = await asyncio.to_thread(
            share_manager.list_my_shares,
            owner_id=user_id,
            file_type=file_type,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

        return [ShareResponse(**share) for share in shares]

    except Exception as e:
        logger.error(f"❌ Error listing my shares: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-with-me", response_model=List[ShareResponse])
async def list_shared_with_me(
    file_type: Optional[str] = None,
    is_active: bool = True,
    limit: int = 100,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List files shared with me by others

    **Returns:** List of shares with complete information:
    - `share_id` - Use this to access the file via `/api/shares/{share_id}/access`
    - `file_id` - The actual file ID (lib_*, file_*, doc_*)
    - `file_type` - Type of file (upload, document, library)
    - `filename` - Name of the file
    - `permission` - Your permission level (view, download, edit)
    - `owner_id` - Who shared the file with you
    - `is_active` - Whether share is still active
    - `expires_at` - When the share expires (null = never)

    **Query parameters:**
    - `file_type`: Filter by file type (upload, document, library)
    - `is_active`: Filter by active status (default: true)
    - `limit`: Max results (default: 100)
    - `offset`: Pagination offset (default: 0)

    **Frontend Usage:**
    ```typescript
    // 1. Get list of shared files
    const shares = await fetch('/api/shares/shared-with-me').then(r => r.json());

    // 2. User clicks on a file
    const selectedShare = shares[0];

    // 3. Access the file using share_id (NOT file_id!)
    const fileData = await fetch(`/api/shares/${selectedShare.share_id}/access`)
      .then(r => r.json());

    // 4. Now you have view_url/download_url based on permission
    if (fileData.view_url) {
      showFileViewer(fileData.view_url);
    }
    if (fileData.download_url) {
      showDownloadButton(fileData.download_url);
    }
    ```

    **Example Response:**
    ```json
    [
      {
        "share_id": "share_xyz789",
        "owner_id": "firebase_uid_owner",
        "recipient_id": "firebase_uid_me",
        "recipient_email": "me@example.com",
        "file_id": "lib_abc123",
        "file_type": "library",
        "filename": "contract.pdf",
        "permission": "download",
        "is_active": true,
        "expires_at": null,
        "created_at": "2025-10-08T10:00:00Z",
        "updated_at": "2025-10-08T10:00:00Z"
      }
    ]
    ```
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        shares = await asyncio.to_thread(
            share_manager.list_shared_with_me,
            recipient_id=user_id,
            file_type=file_type,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

        return [ShareResponse(**share) for share in shares]

    except Exception as e:
        logger.error(f"❌ Error listing shared with me: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{share_id}", response_model=ShareResponse)
async def get_share(
    share_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get share details by share ID

    User must be either the owner or recipient of the share.
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        share = await asyncio.to_thread(
            share_manager.get_share_by_id, share_id=share_id, user_id=user_id
        )

        if not share:
            raise HTTPException(status_code=404, detail="Share not found")

        return ShareResponse(**share)

    except ValueError as e:
        logger.warning(f"⚠️ Get share failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error getting share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{share_id}/access")
async def access_shared_file(
    share_id: str,
    request: Request,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Access a shared file and get file details + URLs for viewing/downloading

    This unified endpoint handles all file types (upload, document, library)
    and returns appropriate file details with URLs based on permissions.

    **Path Parameters:**
    - `share_id`: Share ID

    **Permissions & URLs:**
    - `view`: Returns `view_url` for preview (no download capability)
    - `download`: Returns both `view_url` AND `download_url`
    - `edit`: Returns both URLs (+ editable content for documents)

    **Frontend Implementation:**
    - `view` permission: Use `view_url` to display file in iframe/viewer (disable download)
    - `download` permission: Show download button using `download_url`
    - `edit` permission: Enable editing + download

    **Example Response (view permission):**
    ```json
    {
        "share_id": "share_xyz",
        "file_id": "lib_abc123",
        "file_type": "library",
        "filename": "contract.pdf",
        "file_size": 52428,
        "permission": "view",
        "view_url": "https://r2...?signature=...",
        "expires_in": 3600,
        "accessed_at": "2025-10-08T10:00:00Z"
    }
    ```

    **Example Response (download permission):**
    ```json
    {
        "share_id": "share_xyz",
        "file_id": "lib_abc123",
        "file_type": "library",
        "filename": "contract.pdf",
        "file_size": 52428,
        "permission": "download",
        "view_url": "https://r2...?signature=...",
        "download_url": "https://r2...?signature=...",
        "expires_in": 3600,
        "download_expires_in": 3600,
        "accessed_at": "2025-10-08T10:00:00Z"
    }
    ```
    """
    try:
        from src.services.user_manager import get_user_manager
        from src.services.library_manager import LibraryManager
        from src.services.document_manager import DocumentManager
        from config.config import get_r2_client, R2_BUCKET_NAME

        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        logger.info(f"🔍 User {user_id} accessing shared file via share {share_id}")

        # 1. Get and verify share
        share = await asyncio.to_thread(
            share_manager.get_share_by_id, share_id=share_id, user_id=user_id
        )

        if not share:
            raise HTTPException(status_code=404, detail="Share not found")

        # Verify user is recipient
        if share.get("recipient_id") != user_id:
            raise HTTPException(
                status_code=403, detail="You don't have permission to access this file"
            )

        # Check if share is active
        if not share.get("is_active", False):
            raise HTTPException(status_code=403, detail="Share has been revoked")

        # Check expiration
        expires_at = share.get("expires_at")
        if expires_at and datetime.now() > expires_at:
            raise HTTPException(status_code=403, detail="Share has expired")

        file_id = share.get("file_id")
        file_type = share.get("file_type")
        permission = share.get("permission")

        # 2. Log access
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        await asyncio.to_thread(
            share_manager.log_share_access,
            share_id=share_id,
            user_id=user_id,
            action="view",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 3. Get file details based on type
        file_details = {}
        view_url = None  # URL for preview/viewing (all permissions)
        download_url = None  # URL for downloading (download/edit only)

        if file_type == "library":
            # Library file
            db = get_mongodb()
            s3_client = get_r2_client()
            library_manager = LibraryManager(db=db, s3_client=s3_client)

            library_file = await asyncio.to_thread(
                library_manager.get_library_file,
                library_id=file_id,
                user_id=share.get("owner_id"),  # Owner's file
            )

            if not library_file:
                raise HTTPException(status_code=404, detail="Library file not found")

            file_details = {
                "file_id": library_file.get("library_id"),
                "filename": library_file.get("filename"),
                "original_name": library_file.get(
                    "original_name", library_file.get("filename")
                ),
                "file_size": library_file.get("file_size"),
                "file_type_mime": library_file.get("file_type"),
                "category": library_file.get("category"),
                "description": library_file.get("description"),
                "tags": library_file.get("tags", []),
                "uploaded_at": library_file.get("uploaded_at"),
            }

            # Check if this is an encrypted file (Secret Image)
            is_encrypted = library_file.get("is_encrypted", False)
            if is_encrypted:
                # Add encryption metadata for Secret Images
                encrypted_file_keys = library_file.get("encrypted_file_keys", {})

                # Get recipient's encrypted file key
                recipient_encrypted_key = encrypted_file_keys.get(user_id)

                if not recipient_encrypted_key:
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have decryption key for this secret image",
                    )

                file_details["is_encrypted"] = True
                file_details["encrypted_file_key"] = recipient_encrypted_key
                file_details["encryption_iv_original"] = library_file.get(
                    "encryption_iv_original"
                )
                file_details["encryption_iv_thumbnail"] = library_file.get(
                    "encryption_iv_thumbnail"
                )
                file_details["encryption_iv_exif"] = library_file.get(
                    "encryption_iv_exif"
                )
                file_details["encrypted_exif"] = library_file.get("encrypted_exif")

                # Image dimensions
                file_details["image_width"] = library_file.get("image_width")
                file_details["image_height"] = library_file.get("image_height")
                file_details["thumbnail_width"] = library_file.get("thumbnail_width")
                file_details["thumbnail_height"] = library_file.get("thumbnail_height")

                # R2 paths for encrypted files
                file_details["r2_image_path"] = library_file.get("r2_image_path")
                file_details["r2_thumbnail_path"] = library_file.get(
                    "r2_thumbnail_path"
                )

                # Generate presigned URLs for encrypted files
                r2_image_path = library_file.get("r2_image_path")
                r2_thumbnail_path = library_file.get("r2_thumbnail_path")

                if r2_image_path:
                    view_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": R2_BUCKET_NAME, "Key": r2_image_path},
                        ExpiresIn=3600,
                    )

                if r2_thumbnail_path:
                    file_details["thumbnail_url"] = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": R2_BUCKET_NAME, "Key": r2_thumbnail_path},
                        ExpiresIn=3600,
                    )

                # Download URL only for download/edit permissions
                if permission in ["download", "edit"]:
                    download_url = view_url  # Same URL, frontend controls behavior
            else:
                # Regular library file (not encrypted)
                file_details["is_encrypted"] = False

                # Generate signed URL - ALWAYS (for all permissions)
                r2_key = library_file.get("r2_key")
                if r2_key:
                    view_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": R2_BUCKET_NAME, "Key": r2_key},
                        ExpiresIn=3600,
                    )

                    # Download URL only for download/edit permissions
                    if permission in ["download", "edit"]:
                        download_url = view_url  # Same URL, frontend controls behavior

        elif file_type == "upload":
            # Upload file
            user_manager = get_user_manager()

            upload_file = await asyncio.to_thread(
                user_manager.get_file_by_id,
                file_id=file_id,
                user_id=share.get("owner_id"),
            )

            if not upload_file:
                raise HTTPException(status_code=404, detail="Upload file not found")

            file_details = {
                "file_id": upload_file.get("file_id"),
                "filename": upload_file.get("filename"),
                "original_name": upload_file.get("original_name"),
                "file_size": upload_file.get("file_size"),
                "file_type_mime": upload_file.get("file_type"),
                "folder_id": upload_file.get("folder_id"),
                "uploaded_at": upload_file.get("uploaded_at"),
            }

            # Generate signed URL - ALWAYS (for all permissions)
            r2_key = upload_file.get("r2_key")
            if r2_key:
                s3_client = get_r2_client()
                view_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": R2_BUCKET_NAME, "Key": r2_key},
                    ExpiresIn=3600,
                )

                # Download URL only for download/edit permissions
                if permission in ["download", "edit"]:
                    download_url = view_url  # Same URL, frontend controls behavior

        elif file_type == "document":
            # Document
            db = get_mongodb()
            document_manager = DocumentManager(db=db)

            document = await asyncio.to_thread(
                document_manager.get_document,
                document_id=file_id,
                user_id=share.get("owner_id"),
            )

            if not document:
                raise HTTPException(status_code=404, detail="Document not found")

            file_details = {
                "file_id": document.get("document_id"),
                "filename": document.get("title"),
                "original_name": document.get("title"),
                "file_size": document.get("file_size_bytes", 0),
                "file_type_mime": "text/html",
                "document_type": document.get("document_type"),  # doc/slide/note
                "source_type": document.get("source_type", "file"),  # created/file
                "created_at": document.get("created_at"),
                "updated_at": document.get("last_saved_at"),
            }

            # For documents, always include content for viewing
            # (frontend can make it read-only based on permission)
            file_details["content_html"] = document.get("content_html", "")
            file_details["content_text"] = document.get("content_text", "")

            # Documents don't have R2 URLs, content is in MongoDB
            view_url = None  # Content is in response body
            download_url = None if permission == "view" else "embedded"

        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown file type: {file_type}"
            )

        # 4. Build response
        response = {
            "share_id": share_id,
            "file_type": file_type,
            "permission": permission,
            "owner_id": share.get("owner_id"),
            "accessed_at": datetime.now().isoformat(),
            **file_details,
        }

        # Add URLs based on availability
        if view_url:
            response["view_url"] = view_url
            response["expires_in"] = 3600

        if download_url:
            response["download_url"] = download_url
            if download_url != "embedded":  # Don't add expires_in for embedded content
                response["download_expires_in"] = 3600

        logger.info(
            f"✅ User {user_id} accessed {file_type} file {file_id} via share {share_id} "
            f"(permission: {permission}, view_url: {bool(view_url)}, download_url: {bool(download_url)})"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error accessing shared file: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{share_id}", response_model=Dict[str, Any])
async def update_share(
    share_id: str,
    update_request: UpdateShareRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update share permissions or expiration

    Only the file owner can update shares.
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        success = await asyncio.to_thread(
            share_manager.update_share_permission,
            share_id=share_id,
            owner_id=user_id,
            permission=update_request.permission,
            expires_at=update_request.expires_at,
        )

        if success:
            return {
                "success": True,
                "message": f"Share {share_id} updated successfully",
            }
        else:
            return {"success": False, "message": "No changes made"}

    except ValueError as e:
        logger.warning(f"⚠️ Update share failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error updating share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{share_id}/revoke", response_model=Dict[str, Any])
async def revoke_share(
    share_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Revoke a file share

    Only the file owner can revoke shares.
    Sets `is_active` to false, preventing further access.
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        success = await asyncio.to_thread(
            share_manager.revoke_share, share_id=share_id, owner_id=user_id
        )

        if success:
            return {
                "success": True,
                "message": f"Share {share_id} revoked successfully",
            }
        else:
            return {"success": False, "message": "Share not found or already revoked"}

    except ValueError as e:
        logger.warning(f"⚠️ Revoke share failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error revoking share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SHARE ACCESS & VALIDATION
# ============================================================================


@router.post("/{share_id}/validate", response_model=Dict[str, Any])
async def validate_share_access(
    share_id: str,
    required_permission: str = "view",
    request: Request = None,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Validate access to a shared file

    Checks if user has required permission level and logs access.

    **Required permission levels:**
    - `view`: View file details
    - `download`: Download file
    - `edit`: Edit file content
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        # Validate access
        share = await asyncio.to_thread(
            share_manager.validate_share_access,
            share_id=share_id,
            user_id=user_id,
            required_permission=required_permission,
        )

        # Log access
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)

        await asyncio.to_thread(
            share_manager.log_share_access,
            share_id=share_id,
            user_id=user_id,
            action=required_permission,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "access_granted": True,
            "share_id": share_id,
            "permission": share.get("permission"),
            "file_id": share.get("file_id"),
            "file_type": share.get("file_type"),
        }

    except ValueError as e:
        logger.warning(f"⚠️ Share validation failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error validating share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ACCESS LOGS
# ============================================================================


@router.get("/{share_id}/logs", response_model=List[ShareLogResponse])
async def get_share_logs(
    share_id: str,
    limit: int = 100,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get access logs for a share

    Only the file owner can view access logs.
    Shows who accessed the shared file and when.
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        logs = await asyncio.to_thread(
            share_manager.get_share_logs,
            share_id=share_id,
            owner_id=user_id,
            limit=limit,
            offset=offset,
        )

        return [ShareLogResponse(**log) for log in logs]

    except ValueError as e:
        logger.warning(f"⚠️ Get share logs failed: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error getting share logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# INITIALIZATION
# ============================================================================


@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_share_indexes(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Create MongoDB indexes for file_shares and share_access_logs collections

    **Run this once during deployment.**
    """
    try:
        share_manager = get_share_manager()
        success = await asyncio.to_thread(share_manager.create_indexes)

        if success:
            return {
                "success": True,
                "message": "Share indexes created successfully",
            }
        else:
            return {"success": False, "message": "Failed to create indexes"}

    except Exception as e:
        logger.error(f"❌ Error creating share indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# USER & FILE SHARES UTILITY
# ============================================================================


class CheckEmailRequest(BaseModel):
    """Check email request"""

    email: EmailStr


@router.post("/check-email", response_model=Dict[str, Any])
async def check_email_exists(
    request: CheckEmailRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Check if user email exists in the system

    **Request Body:**
    ```json
    {
        "email": "user@example.com"
    }
    ```

    **Response:**
    ```json
    {
        "exists": true,
        "user_id": "firebase_uid",
        "email": "user@example.com",
        "name": "John Doe",
        "display_name": "John"
    }
    ```
    """
    try:
        share_manager = get_share_manager()
        user = await asyncio.to_thread(
            share_manager.check_user_exists_by_email, email=request.email
        )

        if user:
            return {
                "exists": True,
                "user_id": user.get("user_id"),
                "email": user.get("email"),
                "name": user.get("name", ""),
                "display_name": user.get("display_name", ""),
            }
        else:
            return {
                "exists": False,
                "message": f"User with email {request.email} not found",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FileShareResponse(BaseModel):
    """File share response with recipient info"""

    share_id: str
    recipient_id: str
    recipient_email: str
    recipient_name: str
    recipient_display_name: str
    permission: str
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@router.get("/file/{file_id}/shares", response_model=List[FileShareResponse])
async def list_file_shares(
    file_id: str,
    limit: int = 100,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get list of all users who have access to a specific file
    Only file owner can view this list

    **Path Parameters:**
    - `file_id`: File ID (file_id, document_id, or library_id)

    **Query Parameters:**
    - `limit`: Maximum number of results (default: 100)
    - `offset`: Pagination offset (default: 0)

    **Response:**
    ```json
    [
        {
            "share_id": "share_xyz789",
            "recipient_id": "firebase_uid",
            "recipient_email": "user@example.com",
            "recipient_name": "John Doe",
            "recipient_display_name": "John",
            "permission": "download",
            "is_active": true,
            "expires_at": "2025-12-31T23:59:59Z",
            "created_at": "2025-10-07T10:00:00Z",
            "updated_at": "2025-10-07T10:00:00Z"
        }
    ]
    ```
    """
    try:
        user_id = user_data.get("uid")
        share_manager = get_share_manager()

        logger.info(f"📋 Listing shares for file {file_id} by owner {user_id}")

        shares = await asyncio.to_thread(
            share_manager.list_file_shares,
            file_id=file_id,
            owner_id=user_id,
            limit=limit,
            offset=offset,
        )

        # Convert to response model
        result = []
        for share in shares:
            result.append(FileShareResponse(**share))

        logger.info(f"✅ Found {len(result)} shares for file {file_id}")
        return result

    except Exception as e:
        logger.error(f"❌ Error listing file shares: {e}")
        raise HTTPException(status_code=500, detail=str(e))
