"""
Encrypted Library Folders API Routes
Folder management for E2EE Library Images
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.middleware.auth import verify_firebase_token
from src.services.encrypted_folder_manager import EncryptedFolderManager
from config.config import get_mongodb

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/library/encrypted-folders", tags=["Encrypted Library Folders"]
)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class CreateFolderRequest(BaseModel):
    """Request to create a new folder"""

    name: str = Field(..., min_length=1, max_length=255)
    parent_folder_id: Optional[str] = None
    description: Optional[str] = None


class UpdateFolderRequest(BaseModel):
    """Request to update folder metadata"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_folder_id: Optional[str] = None
    description: Optional[str] = None


class FolderResponse(BaseModel):
    """Folder metadata response"""

    folder_id: str
    owner_id: str
    name: str
    description: Optional[str] = None
    parent_folder_id: Optional[str] = None
    path: List[str]  # Full path of folder IDs from root

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    is_deleted: bool


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_folder_manager() -> EncryptedFolderManager:
    """Get EncryptedFolderManager instance"""
    db = get_mongodb()
    return EncryptedFolderManager(db=db)


# ============================================================================
# FOLDER CRUD ENDPOINTS
# ============================================================================


@router.post("/", response_model=FolderResponse)
async def create_folder(
    request: CreateFolderRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Create a new folder for encrypted images

    - **name**: Folder name (required, 1-255 chars)
    - **parent_folder_id**: Parent folder ID (optional, null = root level)
    - **description**: Folder description (optional)
    """
    try:
        user_id = user_data["uid"]
        manager = get_folder_manager()

        folder = manager.create_folder(
            owner_id=user_id,
            name=request.name,
            parent_folder_id=request.parent_folder_id,
            description=request.description,
        )

        return FolderResponse(**folder)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")


@router.get("/", response_model=List[FolderResponse])
async def list_folders(
    parent_folder_id: Optional[str] = None,
    include_deleted: bool = False,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    List all folders owned by current user

    - **parent_folder_id**: Filter by parent folder (null = root level folders)
    - **include_deleted**: Include soft-deleted folders (default: false)
    """
    try:
        user_id = user_data["uid"]
        manager = get_folder_manager()

        folders = manager.list_folders(
            owner_id=user_id,
            parent_folder_id=parent_folder_id,
            include_deleted=include_deleted,
        )

        return [FolderResponse(**folder) for folder in folders]

    except Exception as e:
        logger.error(f"❌ Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing folders: {str(e)}")


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get folder details by ID
    """
    try:
        user_id = user_data["uid"]
        manager = get_folder_manager()

        folder = manager.get_folder(folder_id=folder_id, owner_id=user_id)

        if not folder:
            raise HTTPException(
                status_code=404, detail="Folder not found or you don't have access"
            )

        return FolderResponse(**folder)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting folder: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting folder: {str(e)}")


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    request: UpdateFolderRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update folder metadata

    - **name**: New folder name (optional)
    - **parent_folder_id**: Move to different parent (optional, null = move to root)
    - **description**: Update description (optional)
    """
    try:
        user_id = user_data["uid"]
        manager = get_folder_manager()

        # Build updates dict (only include non-None values)
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.parent_folder_id is not None:
            updates["parent_folder_id"] = request.parent_folder_id
        if request.description is not None:
            updates["description"] = request.description

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        folder = manager.update_folder(
            folder_id=folder_id, owner_id=user_id, updates=updates
        )

        if not folder:
            raise HTTPException(
                status_code=404, detail="Folder not found or you don't have access"
            )

        return FolderResponse(**folder)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Error updating folder: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating folder: {str(e)}")


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    permanent: bool = False,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Delete a folder (soft delete by default)

    - **permanent**: If true, permanently delete. If false, soft delete (can be restored)
    - Soft delete: marks folder as deleted, can be restored
    - Permanent delete: removes folder and all subfolders (images remain, just lose folder reference)
    """
    try:
        user_id = user_data["uid"]
        manager = get_folder_manager()

        if permanent:
            success = manager.delete_folder_permanent(
                folder_id=folder_id, owner_id=user_id
            )
            message = "Folder permanently deleted"
        else:
            success = manager.soft_delete_folder(folder_id=folder_id, owner_id=user_id)
            message = "Folder moved to trash"

        if not success:
            raise HTTPException(
                status_code=404, detail="Folder not found or you don't have access"
            )

        return {"success": True, "message": message, "folder_id": folder_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting folder: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting folder: {str(e)}")


@router.post("/{folder_id}/restore")
async def restore_folder(
    folder_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Restore a soft-deleted folder from trash
    """
    try:
        user_id = user_data["uid"]
        manager = get_folder_manager()

        success = manager.restore_folder(folder_id=folder_id, owner_id=user_id)

        if not success:
            raise HTTPException(
                status_code=404, detail="Folder not found or you don't have access"
            )

        return {
            "success": True,
            "message": "Folder restored from trash",
            "folder_id": folder_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restoring folder: {e}")
        raise HTTPException(status_code=500, detail=f"Error restoring folder: {str(e)}")
