"""
StudyHub Module API Routes
Milestone 1.2: Module & Content Management
Implements 8 APIs for module and content management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging
from datetime import datetime, timezone

# Authentication
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

# Models
from src.models.studyhub_models import (
    ModuleCreate,
    ModuleUpdate,
    ModuleResponse,
    ModuleReorderRequest,
    ModuleContentCreate,
    ModuleContentResponse,
)

# Services
from src.services.studyhub_module_manager import StudyHubModuleManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/studyhub", tags=["StudyHub - Modules & Content"])

# Initialize DB connection
db_manager = DBManager()


# ==================== API 9: Create Module ====================
@router.post(
    "/subjects/{subject_id}/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_module(
    subject_id: str,
    module_data: ModuleCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new module in subject (API #9)

    - **subject_id**: Subject ID
    - **title**: Module title (required, max 200 chars)
    - **description**: Module description (optional, max 2000 chars)

    Auto-assigns order_index (last + 1)
    Only subject owner can create modules
    """
    try:
        manager = StudyHubModuleManager(db_manager.db, current_user["uid"])

        module = await manager.create_module(
            subject_id=subject_id,
            title=module_data.title,
            description=module_data.description,
        )

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or you don't have permission",
            )

        return module

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating module: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create module: {str(e)}",
        )


# ==================== API 10: Get Modules List ====================
@router.get("/subjects/{subject_id}/modules", response_model=List[ModuleResponse])
async def get_modules(
    subject_id: str,
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get all modules in subject (API #10)

    - **subject_id**: Subject ID

    Returns modules sorted by order_index
    Includes content_count for each module
    """
    try:
        user_id = current_user["uid"] if current_user else None
        manager = StudyHubModuleManager(db_manager.db, user_id)

        modules = await manager.get_modules(subject_id=subject_id)

        return modules

    except Exception as e:
        logger.error(f"Error getting modules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get modules: {str(e)}",
        )


# ==================== API 11: Update Module ====================
@router.put("/modules/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: str,
    module_data: ModuleUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update module (API #11)

    - **module_id**: Module ID
    - **title**: New title (optional)
    - **description**: New description (optional)

    Only subject owner can update modules
    """
    try:
        manager = StudyHubModuleManager(db_manager.db, current_user["uid"])

        module = await manager.update_module(
            module_id=module_id,
            updates=module_data.dict(exclude_unset=True),
        )

        if not module:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found or you don't have permission",
            )

        return module

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating module: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update module: {str(e)}",
        )


# ==================== API 12: Delete Module ====================
@router.delete("/modules/{module_id}", status_code=status.HTTP_200_OK)
async def delete_module(
    module_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete module (API #12)

    - **module_id**: Module ID

    Cascades delete all contents in module
    Re-indexes remaining modules
    Only subject owner can delete modules
    """
    try:
        manager = StudyHubModuleManager(db_manager.db, current_user["uid"])

        success = await manager.delete_module(module_id=module_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found or you don't have permission",
            )

        return {
            "success": True,
            "message": "Module deleted successfully",
            "module_id": module_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting module: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete module: {str(e)}",
        )


# ==================== API 13: Reorder Module ====================
@router.post("/modules/{module_id}/reorder", response_model=List[ModuleResponse])
async def reorder_module(
    module_id: str,
    reorder_data: ModuleReorderRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Reorder module position (API #13)

    - **module_id**: Module ID
    - **new_order_index**: New position (0-based)

    Updates order of all modules in subject
    Returns updated list of all modules
    Only subject owner can reorder modules
    """
    try:
        manager = StudyHubModuleManager(db_manager.db, current_user["uid"])

        modules = await manager.reorder_module(
            module_id=module_id,
            new_order_index=reorder_data.new_order_index,
        )

        if not modules:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found or you don't have permission",
            )

        return modules

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering module: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reorder module: {str(e)}",
        )


# ==================== API 14: Add Content to Module ====================
@router.post(
    "/modules/{module_id}/content",
    response_model=ModuleContentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_content(
    module_id: str,
    content_data: ModuleContentCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Add content to module (API #14)

    - **module_id**: Module ID
    - **content_type**: Type of content (document/link/video/book/test/slides)
    - **title**: Content title
    - **data**: Content-specific data
    - **is_required**: Required for completion (default: false)

    Auto-assigns order_index (last + 1)
    Only subject owner can add content
    """
    try:
        manager = StudyHubModuleManager(db_manager.db, current_user["uid"])

        content = await manager.add_content(
            module_id=module_id,
            content_type=content_data.content_type,
            title=content_data.title,
            data=content_data.data.dict(exclude_unset=True),
            is_required=content_data.is_required,
        )

        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found or you don't have permission",
            )

        return content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add content: {str(e)}",
        )


# ==================== API 15: Get Module Contents ====================
@router.get("/modules/{module_id}/content", response_model=List[ModuleContentResponse])
async def get_module_contents(
    module_id: str,
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get all contents in module (API #15)

    - **module_id**: Module ID

    Returns contents sorted by order_index
    """
    try:
        user_id = current_user["uid"] if current_user else None
        manager = StudyHubModuleManager(db_manager.db, user_id)

        contents = await manager.get_contents(module_id=module_id)

        return contents

    except Exception as e:
        logger.error(f"Error getting contents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get contents: {str(e)}",
        )


# ==================== API 16: Delete Content ====================
@router.delete(
    "/modules/{module_id}/content/{content_id}", status_code=status.HTTP_200_OK
)
async def delete_content(
    module_id: str,
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete content from module (API #16)

    - **module_id**: Module ID
    - **content_id**: Content ID

    Re-indexes remaining contents
    Only subject owner can delete content
    """
    try:
        manager = StudyHubModuleManager(db_manager.db, current_user["uid"])

        success = await manager.delete_content(
            module_id=module_id,
            content_id=content_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found or you don't have permission",
            )

        return {
            "success": True,
            "message": "Content deleted successfully",
            "content_id": content_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete content: {str(e)}",
        )
