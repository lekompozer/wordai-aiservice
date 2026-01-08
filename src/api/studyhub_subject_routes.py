"""
StudyHub Subject API Routes
Milestone 1.1: Subject Core Management
Implements 8 core APIs for subject management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from typing import List, Optional
import logging
from datetime import datetime, timezone

# Authentication
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

# Models
from src.models.studyhub_models import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    SubjectListResponse,
    SubjectStatsResponse,
    CoverUploadResponse,
    SubjectStatus,
    SubjectVisibility,
    SubjectMetadata,
)

# Services
from src.services.studyhub_subject_manager import StudyHubSubjectManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/studyhub/subjects", tags=["StudyHub - Subjects"])

# Initialize DB connection
db_manager = DBManager()


# ==================== API 1: Create Subject ====================
@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new subject (API #1)
    
    - **title**: Subject title (required, max 200 chars)
    - **description**: Subject description (optional, max 2000 chars)
    - **visibility**: public or private (default: private)
    
    Returns newly created subject with status "draft"
    """
    try:
        manager = StudyHubSubjectManager(db_manager.db, current_user["uid"])
        
        subject = await manager.create_subject(
            title=subject_data.title,
            description=subject_data.description,
            visibility=subject_data.visibility,
        )
        
        return subject
        
    except Exception as e:
        logger.error(f"Error creating subject: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subject: {str(e)}"
        )


# ==================== API 2: Get Subject Details ====================
@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: str,
    include_stats: bool = Query(False, description="Include metadata statistics"),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get subject details (API #2)
    
    - **subject_id**: Subject ID
    - **include_stats**: Include metadata (total_modules, total_learners, etc.)
    
    Returns subject details with metadata
    """
    try:
        user_id = current_user["uid"] if current_user else None
        manager = StudyHubSubjectManager(db_manager.db, user_id)
        
        subject = await manager.get_subject(
            subject_id=subject_id,
            include_stats=include_stats,
        )
        
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found"
            )
        
        return subject
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subject: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subject: {str(e)}"
        )


# ==================== API 3: Update Subject ====================
@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    subject_data: SubjectUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update subject (API #3)
    
    - **subject_id**: Subject ID
    - **title**: New title (optional)
    - **description**: New description (optional)
    - **visibility**: New visibility (optional)
    
    Only subject owner can update
    """
    try:
        manager = StudyHubSubjectManager(db_manager.db, current_user["uid"])
        
        subject = await manager.update_subject(
            subject_id=subject_id,
            updates=subject_data.dict(exclude_unset=True),
        )
        
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or you don't have permission"
            )
        
        return subject
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subject: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subject: {str(e)}"
        )


# ==================== API 4: Delete Subject ====================
@router.delete("/{subject_id}", status_code=status.HTTP_200_OK)
async def delete_subject(
    subject_id: str,
    confirm: bool = Query(False, description="Confirm deletion if subject has learners"),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete subject (API #4)
    
    - **subject_id**: Subject ID
    - **confirm**: Required if subject has learners
    
    Soft delete (changes status to archived)
    Only subject owner can delete
    """
    try:
        manager = StudyHubSubjectManager(db_manager.db, current_user["uid"])
        
        result = await manager.delete_subject(
            subject_id=subject_id,
            confirm=confirm,
        )
        
        if not result["success"]:
            if result.get("requires_confirmation"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Subject has {result['learner_count']} learners. Set confirm=true to proceed."
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or you don't have permission"
            )
        
        return {
            "success": True,
            "message": result["message"],
            "subject_id": subject_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting subject: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete subject: {str(e)}"
        )


# ==================== API 5: List Subjects ====================
@router.get("", response_model=SubjectListResponse)
async def list_subjects(
    status_filter: Optional[str] = Query(None, description="Filter by status: draft, published, archived"),
    visibility: Optional[str] = Query(None, description="Filter by visibility: public, private"),
    owner_id: Optional[str] = Query(None, description="Filter by owner user ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("created_at", description="Sort by: created_at, updated_at, title"),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    List subjects with filters (API #5)
    
    - **status**: Filter by status (draft/published/archived)
    - **visibility**: Filter by visibility (public/private)
    - **owner_id**: Filter by owner
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20, max: 100)
    - **sort**: Sort field (default: created_at)
    
    Returns paginated list of subjects
    """
    try:
        user_id = current_user["uid"] if current_user else None
        manager = StudyHubSubjectManager(db_manager.db, user_id)
        
        result = await manager.list_subjects(
            status_filter=status_filter,
            visibility=visibility,
            owner_id=owner_id,
            page=page,
            limit=limit,
            sort=sort,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing subjects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list subjects: {str(e)}"
        )


# ==================== API 6: Get Owner's Subjects ====================
@router.get("/owner/{user_id}", response_model=SubjectListResponse)
async def get_owner_subjects(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user_optional),
):
    """
    Get subjects of a specific owner (API #6)
    
    - **user_id**: Owner user ID
    - **page**: Page number
    - **limit**: Items per page
    
    Returns public subjects + owned subjects if viewing own profile
    """
    try:
        viewer_id = current_user["uid"] if current_user else None
        manager = StudyHubSubjectManager(db_manager.db, viewer_id)
        
        result = await manager.get_owner_subjects(
            owner_id=user_id,
            is_owner=(viewer_id == user_id),
            page=page,
            limit=limit,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting owner subjects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get owner subjects: {str(e)}"
        )


# ==================== API 7: Upload Cover Image ====================
@router.post("/{subject_id}/cover", response_model=CoverUploadResponse)
async def upload_cover(
    subject_id: str,
    file: UploadFile = File(..., description="Cover image file"),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload cover image for subject (API #7)
    
    - **subject_id**: Subject ID
    - **file**: Image file (JPEG, PNG, WebP)
    
    Uploads to CDN, resizes, and optimizes image
    Only subject owner can upload
    """
    try:
        manager = StudyHubSubjectManager(db_manager.db, current_user["uid"])
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )
        
        # Validate file size (max 5MB)
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 5MB limit"
            )
        
        # Upload and update subject
        cover_url = await manager.upload_cover(
            subject_id=subject_id,
            file_content=contents,
            filename=file.filename,
            content_type=file.content_type,
        )
        
        if not cover_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or you don't have permission"
            )
        
        return CoverUploadResponse(
            cover_image_url=cover_url,
            subject_id=subject_id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading cover: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload cover: {str(e)}"
        )


# ==================== API 8: Publish Subject ====================
@router.post("/{subject_id}/publish", response_model=SubjectResponse)
async def publish_subject(
    subject_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Publish subject (API #8)
    
    - **subject_id**: Subject ID
    
    Changes status from draft to published
    Validation: Must have at least 1 module
    Only subject owner can publish
    """
    try:
        manager = StudyHubSubjectManager(db_manager.db, current_user["uid"])
        
        subject = await manager.publish_subject(subject_id=subject_id)
        
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or you don't have permission"
            )
        
        return subject
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing subject: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish subject: {str(e)}"
        )
