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
    file_type: str = Field(..., regex="^(upload|document|library)$")
    permission: str = Field("view", regex="^(view|download|edit)$")
    expires_at: Optional[datetime] = None


class UpdateShareRequest(BaseModel):
    """Update share request"""

    permission: str = Field(..., regex="^(view|download|edit)$")
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
    """
    try:
        user_id = user_data.get("uid")
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

    **Query parameters:**
    - `file_type`: Filter by file type (upload, document, library)
    - `is_active`: Filter by active status (default: true)
    - `limit`: Max results (default: 100)
    - `offset`: Pagination offset (default: 0)
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
