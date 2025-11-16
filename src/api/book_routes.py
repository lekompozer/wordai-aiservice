"""
Online Book API Routes - GitBook-style Documentation System
Phase 2: Guide Management API
Phase 3: Chapter Management API
Phase 4: User Permissions API

Implements RESTful endpoints for creating and managing Online Books with nested chapters.
Supports public/private/unlisted visibility, user permissions, and hierarchical structure (max 3 levels).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
import logging

# Authentication
from src.middleware.firebase_auth import get_current_user

# Models
from src.models.book_models import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookListResponse,
    BookVisibility,
    # Phase 6: Community Books & Document Integration
    CommunityPublishRequest,
    CommunityBookItem,
    CommunityBooksResponse,
    ChapterFromDocumentRequest,
    # Image Upload
    BookImageUploadRequest,
)
from src.models.book_chapter_models import (
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    ChapterTreeNode,
    ChapterReorderBulk,
)
from src.models.book_permission_models import (
    PermissionCreate,
    PermissionInvite,
    PermissionResponse,
    PermissionListItem,
    PermissionListResponse,
)
from src.models.public_book_models import (
    PublicBookResponse,
    PublicChapterResponse,
    ViewTrackingRequest,
    ViewTrackingResponse,
    BookDomainResponse,
    PublicAuthorInfo,
    PublicChapterSummary,
    BookStats,
    SEOMetadata,
    ChapterNavigation,
    PublicGuideInfo,
)

# Services
from src.services.book_manager import UserBookManager
from src.services.book_chapter_manager import GuideBookBookChapterManager
from src.services.book_permission_manager import GuideBookBookPermissionManager
from src.services.author_manager import AuthorManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books", tags=["Online Books"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize managers with DB
guide_manager = UserBookManager(db)
chapter_manager = GuideBookBookChapterManager(db)
permission_manager = GuideBookBookPermissionManager(db)
author_manager = AuthorManager(db)


# ==============================================================================
# PHASE 2: GUIDE MANAGEMENT API
# ==============================================================================


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_guide(
    guide_data: BookCreate, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new User Guide

    **Authentication:** Required (Firebase JWT)

    **Request Body:**
    - title: Guide title (1-200 chars)
    - slug: URL-friendly slug (alphanumeric + hyphens)
    - description: Optional description (max 1000 chars)
    - visibility: "public" | "private" | "unlisted"
    - icon: Optional emoji icon
    - color: Optional hex color (#RRGGBB)
    - enable_toc: Enable table of contents (default: true)
    - enable_search: Enable search (default: true)
    - enable_feedback: Enable feedback (default: true)

    **Returns:**
    - 201: Guide created successfully
    - 409: Slug already exists for this user
    - 422: Validation error
    """
    try:
        user_id = current_user["uid"]

        # Check slug uniqueness
        if guide_manager.slug_exists(user_id, guide_data.slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{guide_data.slug}' already exists for this user",
            )

        # Create guide
        guide = guide_manager.create_guide(user_id, guide_data)

        logger.info(
            f"✅ User {user_id} created guide: {guide['book_id']} ({guide_data.title})"
        )
        return guide

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create guide: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create guide",
        )


@router.get("", response_model=BookListResponse)
async def list_guides(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    visibility: Optional[BookVisibility] = Query(
        None, description="Filter by visibility"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List user's guides with pagination and filtering

    **Authentication:** Required

    **Query Parameters:**
    - skip: Pagination offset (default: 0)
    - limit: Results per page (default: 20, max: 100)
    - visibility: Filter by visibility type (optional)

    **Returns:**
    - 200: Paginated list of guides
    """
    try:
        user_id = current_user["uid"]

        # Get guides
        guides = guide_manager.list_user_guides(
            user_id=user_id, skip=skip, limit=limit, visibility=visibility
        )

        # Count total (for pagination)
        total = guide_manager.count_user_guides(user_id=user_id, visibility=visibility)

        logger.info(f"📚 User {user_id} listed guides: {len(guides)} results")

        return {
            "guides": guides,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"❌ Failed to list guides: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list guides",
        )


@router.get("/{book_id}", response_model=BookResponse)
async def get_guide(
    book_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get detailed information about a specific guide

    **Authentication:** Required

    **Returns:**
    - 200: Guide details
    - 403: User doesn't have access to this guide
    - 404: Guide not found
    """
    try:
        user_id = current_user["uid"]

        # Get guide
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # Check access: owner OR has permission
        is_owner = guide["user_id"] == user_id

        if not is_owner:
            # Check if user has permission
            has_permission = permission_manager.check_permission(
                book_id=book_id, user_id=user_id
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this guide",
                )

        logger.info(f"📖 User {user_id} accessed guide: {book_id}")
        return guide

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get guide: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get guide",
        )


@router.patch("/{book_id}", response_model=BookResponse)
async def update_guide(
    book_id: str,
    guide_data: BookUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update guide metadata (partial update supported)

    **Authentication:** Required (Owner only)

    **Request Body:**
    - Any fields from BookCreate (all optional)

    **Returns:**
    - 200: Guide updated successfully
    - 403: User is not the guide owner
    - 404: Guide not found
    - 409: Slug already exists
    """
    try:
        user_id = current_user["uid"]

        # Get guide to verify ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # Check ownership
        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can update guide",
            )

        # Check slug uniqueness if slug is being changed
        if guide_data.slug and guide_data.slug != guide["slug"]:
            if guide_manager.slug_exists(user_id, guide_data.slug):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{guide_data.slug}' already exists for this user",
                )

        # Update guide
        updated_guide = guide_manager.update_guide(book_id, guide_data)

        if not updated_guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        logger.info(f"✏️ User {user_id} updated guide: {book_id}")
        return updated_guide

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update guide: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update guide",
        )


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guide(
    book_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete guide and all associated chapters and permissions

    **Authentication:** Required (Owner only)

    **Cascade Deletion:**
    1. Delete all chapters in guide_chapters collection
    2. Delete all permissions in guide_permissions collection
    3. Delete guide from user_guides collection

    **Returns:**
    - 204: Guide deleted successfully
    - 403: User is not the guide owner
    - 404: Guide not found
    """
    try:
        user_id = current_user["uid"]

        # Get guide to verify ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # Check ownership
        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can delete guide",
            )

        # Delete chapters
        deleted_chapters = chapter_manager.delete_guide_chapters(book_id)

        # Delete permissions
        deleted_permissions = permission_manager.delete_guide_permissions(book_id)

        # Delete guide
        deleted = guide_manager.delete_guide(book_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        logger.info(
            f"🗑️ User {user_id} deleted guide: {book_id} "
            f"(chapters: {deleted_chapters}, permissions: {deleted_permissions})"
        )
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete guide: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete guide",
        )


# ==============================================================================
# PHASE 3: CHAPTER MANAGEMENT API
# ==============================================================================


@router.post(
    "/{book_id}/chapters",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    book_id: str,
    chapter_data: ChapterCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Create a new chapter in a guide

    **Authentication:** Required (Owner only)

    **Request Body:**
    - title: Chapter title (1-200 chars)
    - slug: URL-friendly slug (alphanumeric + hyphens)
    - document_id: Document ID from documents collection
    - parent_id: Parent chapter ID (null for root chapters)
    - order_index: Display order (default: 0)
    - is_published: Publish status (default: true)

    **Validation:**
    - Slug must be unique within guide
    - Parent chapter must exist in same guide (if provided)
    - Max depth: 3 levels (0, 1, 2)
    - Document must exist

    **Returns:**
    - 201: Chapter created successfully
    - 400: Max depth exceeded or validation error
    - 403: User is not the guide owner
    - 404: Guide or parent chapter not found
    - 409: Slug already exists in guide
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can create chapters",
            )

        # Check slug uniqueness within guide
        if chapter_manager.slug_exists(book_id, chapter_data.slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{chapter_data.slug}' already exists in this guide",
            )

        # Verify parent exists if provided
        if chapter_data.parent_id:
            parent = chapter_manager.get_chapter(chapter_data.parent_id)

            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent chapter not found",
                )

            # Verify parent belongs to same guide
            if parent["book_id"] != book_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent chapter must belong to the same guide",
                )

        # Create chapter (depth is auto-calculated)
        chapter = chapter_manager.create_chapter(book_id, chapter_data)

        logger.info(
            f"✅ User {user_id} created chapter in guide {book_id}: "
            f"{chapter['chapter_id']} ({chapter_data.title})"
        )
        return chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chapter",
        )


@router.get("/{book_id}/chapters", response_model=Dict[str, Any])
async def get_chapter_tree(
    book_id: str,
    include_unpublished: bool = Query(
        False, description="Include unpublished chapters (owner only)"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get hierarchical tree structure of all chapters in a guide

    **Authentication:** Required

    **Query Parameters:**
    - include_unpublished: Include unpublished chapters (default: false)
      * Always true for guide owner
      * Ignored for non-owners

    **Tree Structure:**
    - Max 3 levels: Level 0 (root), Level 1 (sub), Level 2 (sub-sub)
    - Ordered by order_index at each level
    - Unpublished chapters hidden for non-owners

    **Returns:**
    - 200: Chapter tree structure
    - 403: User doesn't have access to guide
    - 404: Guide not found
    """
    try:
        user_id = current_user["uid"]

        # Verify guide access
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # Check access
        is_owner = guide["user_id"] == user_id

        if not is_owner:
            has_permission = permission_manager.check_permission(
                book_id=book_id, user_id=user_id
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this guide",
                )

        # Owner always sees unpublished chapters
        show_unpublished = is_owner or include_unpublished

        # Get chapter tree
        chapters = chapter_manager.get_chapter_tree(
            book_id=book_id, include_unpublished=show_unpublished
        )

        # Count total chapters
        total = chapter_manager.count_chapters(book_id)

        logger.info(
            f"📄 User {user_id} retrieved chapter tree for guide {book_id}: {total} chapters"
        )

        return {
            "book_id": book_id,
            "chapters": chapters,
            "total_chapters": total,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter tree: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chapter tree",
        )


@router.patch(
    "/{book_id}/chapters/{chapter_id}",
    response_model=ChapterResponse,
)
async def update_chapter(
    book_id: str,
    chapter_id: str,
    chapter_data: ChapterUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update chapter metadata or move to different parent

    **Authentication:** Required (Owner only)

    **Request Body:**
    - Any fields from ChapterCreate (all optional)
    - Moving chapter recalculates depth and validates max 3 levels

    **Validation:**
    - Cannot move chapter to its own descendant (circular reference)
    - Slug must be unique within guide (if changed)
    - Max depth validation after parent change

    **Returns:**
    - 200: Chapter updated successfully
    - 400: Circular reference or max depth exceeded
    - 403: User is not the guide owner
    - 404: Chapter not found
    - 409: Slug already exists in guide
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can update chapters",
            )

        # Get existing chapter
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Verify chapter belongs to guide
        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this guide",
            )

        # Check slug uniqueness if changed
        if chapter_data.slug and chapter_data.slug != chapter["slug"]:
            if chapter_manager.slug_exists(book_id, chapter_data.slug):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{chapter_data.slug}' already exists in this guide",
                )

        # Update chapter
        updated_chapter = chapter_manager.update_chapter(chapter_id, chapter_data)

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        logger.info(f"✏️ User {user_id} updated chapter: {chapter_id}")
        return updated_chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chapter",
        )


@router.delete("/{book_id}/chapters/{chapter_id}", response_model=Dict[str, Any])
async def delete_chapter(
    book_id: str,
    chapter_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete chapter and all child chapters recursively

    **Authentication:** Required (Owner only)

    **Cascade Deletion:**
    1. Find all descendant chapters recursively
    2. Delete all descendants from database
    3. Delete the target chapter
    4. Return list of deleted chapter IDs

    **Returns:**
    - 200: Chapter(s) deleted successfully with count
    - 403: User is not the guide owner
    - 404: Chapter not found
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can delete chapters",
            )

        # Get chapter to verify it exists
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Verify chapter belongs to guide
        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this guide",
            )

        # Delete chapter and all children (cascade)
        deleted_ids = chapter_manager.delete_chapter_cascade(chapter_id)

        logger.info(
            f"🗑️ User {user_id} deleted chapter {chapter_id} "
            f"and {len(deleted_ids) - 1} children"
        )

        return {
            "deleted_chapter_id": chapter_id,
            "deleted_children_count": len(deleted_ids) - 1,
            "deleted_chapter_ids": deleted_ids,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chapter",
        )


@router.post("/{book_id}/chapters/reorder", response_model=Dict[str, Any])
async def reorder_chapters(
    book_id: str,
    reorder_data: ChapterReorderBulk,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Bulk reorder chapters (drag-and-drop support)

    **Authentication:** Required (Owner only)

    **Request Body:**
    - updates: Array of chapter updates with new parent_id and order_index

    **Validation:**
    - All chapter_ids must exist in the guide
    - Validates max depth for each chapter after reordering
    - Prevents circular references

    **Returns:**
    - 200: Chapters reordered successfully
    - 400: Invalid chapter IDs, circular reference, or max depth exceeded
    - 403: User is not the guide owner
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can reorder chapters",
            )

        # Reorder chapters
        updated_chapters = chapter_manager.reorder_chapters(
            book_id=book_id, updates=reorder_data.updates
        )

        logger.info(
            f"🔄 User {user_id} reordered {len(updated_chapters)} chapters in guide {book_id}"
        )

        return {
            "updated_count": len(updated_chapters),
            "chapters": updated_chapters,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to reorder chapters: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder chapters",
        )


# ==============================================================================
# PHASE 4: USER PERMISSIONS API
# ==============================================================================


@router.post(
    "/{book_id}/permissions/users",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_permission(
    book_id: str,
    permission_data: PermissionCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Grant user permission to access a private guide

    **Authentication:** Required (Owner only)

    **Request Body:**
    - user_id: Firebase UID of user to grant access
    - access_level: "viewer" | "editor" (default: viewer)
    - expires_at: Optional expiration datetime

    **Returns:**
    - 201: Permission granted successfully
    - 403: User is not the guide owner
    - 404: Guide not found
    - 409: Permission already exists for this user
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can grant permissions",
            )

        # Check if permission already exists
        existing = permission_manager.get_permission(
            book_id=book_id, user_id=permission_data.user_id
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {permission_data.user_id} already has permission for this guide",
            )

        # Grant permission
        permission = permission_manager.grant_permission(
            book_id=book_id,
            user_id=permission_data.user_id,
            granted_by=user_id,
            access_level=permission_data.access_level.value,
            expires_at=permission_data.expires_at,
        )

        logger.info(
            f"✅ User {user_id} granted {permission_data.access_level} permission to {permission_data.user_id} for guide {book_id}"
        )

        return permission

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to grant permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to grant permission",
        )


@router.get("/{book_id}/permissions/users", response_model=PermissionListResponse)
async def list_permissions(
    book_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all users with permissions on a guide

    **Authentication:** Required (Owner only)

    **Query Parameters:**
    - skip: Pagination offset (default: 0)
    - limit: Results per page (default: 50, max: 100)

    **Returns:**
    - 200: List of permissions
    - 403: User is not the guide owner
    - 404: Guide not found
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can list permissions",
            )

        # Get permissions
        permissions = permission_manager.list_permissions(
            book_id=book_id, skip=skip, limit=limit
        )

        total = permission_manager.count_permissions(book_id=book_id)

        logger.info(
            f"📋 User {user_id} listed permissions for guide {book_id}: {len(permissions)} results"
        )

        return {"permissions": permissions, "total": total}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list permissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list permissions",
        )


@router.delete("/{book_id}/permissions/users/{permission_user_id}")
async def revoke_permission(
    book_id: str,
    permission_user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Revoke user permission to access a guide

    **Authentication:** Required (Owner only)

    **Path Parameters:**
    - book_id: Guide identifier
    - permission_user_id: Firebase UID of user to revoke

    **Returns:**
    - 200: Permission revoked successfully
    - 403: User is not the guide owner
    - 404: Guide or permission not found
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can revoke permissions",
            )

        # Check if permission exists
        permission = permission_manager.get_permission(
            book_id=book_id, user_id=permission_user_id
        )

        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission not found for user {permission_user_id}",
            )

        # Revoke permission
        success = permission_manager.revoke_permission(
            book_id=book_id, user_id=permission_user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke permission",
            )

        logger.info(
            f"❌ User {user_id} revoked permission from {permission_user_id} for guide {book_id}"
        )

        return {
            "message": "Permission revoked successfully",
            "revoked": {
                "book_id": book_id,
                "user_id": permission_user_id,
                "revoked_by": user_id,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to revoke permission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke permission",
        )


@router.post(
    "/{book_id}/permissions/invite",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    book_id: str,
    invite_data: PermissionInvite,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Invite user by email to access a guide (creates permission + sends email)

    **Authentication:** Required (Owner only)

    **Request Body:**
    - email: Email address to invite
    - access_level: "viewer" | "editor" (default: viewer)
    - expires_at: Optional expiration datetime
    - message: Optional personal message (max 500 chars)

    **Returns:**
    - 201: Invitation sent successfully
    - 403: User is not the guide owner
    - 404: Guide not found
    - 400: Invalid email
    - 500: Email sending failed

    **Note:** Email invitation requires Brevo service integration
    """
    try:
        user_id = current_user["uid"]

        # Verify guide ownership
        guide = guide_manager.get_guide(book_id)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        if guide["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only guide owner can invite users",
            )

        # Create invitation (stores in guide_permissions with invited_email)
        invitation = permission_manager.create_invitation(
            book_id=book_id,
            email=invite_data.email,
            granted_by=user_id,
            access_level=invite_data.access_level.value,
            expires_at=invite_data.expires_at,
            message=invite_data.message,
        )

        # TODO: Send email via Brevo service
        # from src.services.brevo_service import BrevoService
        # brevo = BrevoService()
        # email_sent = await brevo.send_guide_invitation(
        #     email=invite_data.email,
        #     guide_title=guide["title"],
        #     guide_slug=guide["slug"],
        #     owner_name=current_user.get("name", "Someone"),
        #     message=invite_data.message
        # )

        email_sent = True  # Placeholder - implement Brevo integration later

        logger.info(
            f"📧 User {user_id} invited {invite_data.email} to guide {book_id} (email_sent: {email_sent})"
        )

        return {
            "invitation": invitation,
            "email_sent": email_sent,
            "message": (
                "Invitation sent successfully"
                if email_sent
                else "Invitation created (email service unavailable)"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to invite user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite user",
        )


# ==============================================================================
# PHASE 5: PUBLIC VIEW API (NO AUTH REQUIRED)
# ==============================================================================


@router.get(
    "/public/guides/{slug}",
    response_model=PublicBookResponse,
    status_code=status.HTTP_200_OK,
)
async def get_public_guide(slug: str):
    """
    Get public guide with all chapters (NO AUTHENTICATION REQUIRED)

    **Use Case:** Homepage/TOC for public guides

    **Path Parameters:**
    - slug: Guide slug (URL-friendly identifier)

    **Returns:**
    - 200: Guide with chapters, SEO metadata, author info
    - 404: Guide not found
    - 403: Guide is private (not accessible publicly)

    **Note:** Only public/unlisted guides are accessible
    """
    try:
        # Get guide by slug
        guide = guide_manager.get_guide_by_slug(slug)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # Check visibility - only public/unlisted guides accessible
        if guide.get("visibility") == "private":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This guide is private and cannot be accessed publicly",
            )

        # Get all chapters for this guide (sorted by order)
        chapters = chapter_manager.list_chapters(guide["book_id"])

        # Get author info (mock for now - implement user service later)
        author = PublicAuthorInfo(
            user_id=guide["user_id"],
            display_name=guide.get("author_name", "Unknown Author"),
            avatar_url=guide.get("author_avatar"),
        )

        # Build chapter summaries
        chapter_summaries = [
            PublicChapterSummary(
                chapter_id=ch["chapter_id"],
                title=ch["title"],
                slug=ch["slug"],
                order=ch["order"],
                description=ch.get("description"),
                icon=ch.get("icon"),
            )
            for ch in chapters
        ]

        # Stats
        stats = BookStats(
            total_chapters=len(chapters),
            total_views=guide.get("stats", {}).get("total_views", 0),
            last_updated=guide["updated_at"],
        )

        # SEO metadata
        base_url = "https://wordai.com"
        guide_url = f"{base_url}/g/{slug}"

        seo = SEOMetadata(
            title=f"{guide['title']} - Complete Guide",
            description=guide.get("description", f"Learn about {guide['title']}"),
            og_image=guide.get("cover_image_url"),
            og_url=guide.get("custom_domain", guide_url),
            twitter_card="summary_large_image",
        )

        # Response
        response = PublicBookResponse(
            book_id=guide["book_id"],
            title=guide["title"],
            slug=guide["slug"],
            description=guide.get("description"),
            visibility=guide["visibility"],
            custom_domain=guide.get("custom_domain"),
            is_indexed=guide.get("is_indexed", True),
            cover_image_url=guide.get("cover_image_url"),
            logo_url=guide.get("logo_url"),
            favicon_url=guide.get("favicon_url"),
            author=author,
            chapters=chapter_summaries,
            stats=stats,
            seo=seo,
            branding=guide.get("branding"),
            created_at=guide["created_at"],
            updated_at=guide["updated_at"],
        )

        logger.info(f"📖 Public guide accessed: {slug} ({len(chapters)} chapters)")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public guide: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get public guide",
        )


@router.get(
    "/public/guides/{guide_slug}/chapters/{chapter_slug}",
    response_model=PublicChapterResponse,
    status_code=status.HTTP_200_OK,
)
async def get_public_chapter(guide_slug: str, chapter_slug: str):
    """
    Get public chapter with content and navigation (NO AUTHENTICATION REQUIRED)

    **Use Case:** Chapter content page for public guides

    **Path Parameters:**
    - guide_slug: Guide slug
    - chapter_slug: Chapter slug

    **Returns:**
    - 200: Chapter content with prev/next navigation
    - 404: Guide or chapter not found
    - 403: Guide is private

    **Note:** Includes guide info + prev/next navigation + SEO metadata
    """
    try:
        # Get guide by slug
        guide = guide_manager.get_guide_by_slug(guide_slug)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # Check visibility
        if guide.get("visibility") == "private":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This guide is private and cannot be accessed publicly",
            )

        # Get chapter by slug
        chapter = chapter_manager.get_chapter_by_slug(guide["book_id"], chapter_slug)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Get all chapters for navigation
        all_chapters = chapter_manager.list_chapters(guide["book_id"])
        all_chapters_sorted = sorted(all_chapters, key=lambda x: x["order"])

        # Find prev/next chapters
        current_index = next(
            (
                i
                for i, ch in enumerate(all_chapters_sorted)
                if ch["chapter_id"] == chapter["chapter_id"]
            ),
            -1,
        )

        prev_chapter = None
        next_chapter = None

        if current_index > 0:
            prev_ch = all_chapters_sorted[current_index - 1]
            prev_chapter = PublicChapterSummary(
                chapter_id=prev_ch["chapter_id"],
                title=prev_ch["title"],
                slug=prev_ch["slug"],
                order=prev_ch["order"],
                description=prev_ch.get("description"),
                icon=prev_ch.get("icon"),
            )

        if current_index < len(all_chapters_sorted) - 1:
            next_ch = all_chapters_sorted[current_index + 1]
            next_chapter = PublicChapterSummary(
                chapter_id=next_ch["chapter_id"],
                title=next_ch["title"],
                slug=next_ch["slug"],
                order=next_ch["order"],
                description=next_ch.get("description"),
                icon=next_ch.get("icon"),
            )

        # Navigation
        navigation = ChapterNavigation(previous=prev_chapter, next=next_chapter)

        # Guide info
        guide_info = PublicGuideInfo(
            book_id=guide["book_id"],
            title=guide["title"],
            slug=guide["slug"],
            logo_url=guide.get("logo_url"),
            custom_domain=guide.get("custom_domain"),
        )

        # SEO metadata
        base_url = guide.get("custom_domain") or "https://wordai.com"
        chapter_url = f"{base_url}/g/{guide_slug}/{chapter_slug}"

        seo = SEOMetadata(
            title=f"{chapter['title']} - {guide['title']}",
            description=chapter.get("description", f"Read {chapter['title']}"),
            og_image=guide.get("cover_image_url"),
            og_url=chapter_url,
            twitter_card="summary_large_image",
        )

        # Response
        response = PublicChapterResponse(
            chapter_id=chapter["chapter_id"],
            book_id=guide["book_id"],
            title=chapter["title"],
            slug=chapter["slug"],
            order=chapter["order"],
            description=chapter.get("description"),
            icon=chapter.get("icon"),
            content=chapter["content"],
            guide_info=guide_info,
            navigation=navigation,
            seo=seo,
            created_at=chapter["created_at"],
            updated_at=chapter["updated_at"],
        )

        logger.info(f"📄 Public chapter accessed: {guide_slug}/{chapter_slug}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get public chapter",
        )


@router.post(
    "/public/guides/{slug}/views",
    response_model=ViewTrackingResponse,
    status_code=status.HTTP_200_OK,
)
async def track_view(slug: str, view_data: ViewTrackingRequest):
    """
    Track guide/chapter view analytics (NO AUTHENTICATION REQUIRED)

    **Use Case:** Frontend calls this to track views (optional)

    **Path Parameters:**
    - slug: Guide slug

    **Request Body:**
    - chapter_slug: Optional chapter slug (if viewing specific chapter)
    - referrer: Optional referrer URL
    - user_agent: Optional user agent string
    - session_id: Optional session ID (to prevent double-counting)

    **Returns:**
    - 200: View tracked successfully
    - 404: Guide not found

    **Note:** Rate limited to 10 requests/minute per IP
    """
    try:
        # Get guide by slug
        guide = guide_manager.get_guide_by_slug(slug)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guide not found",
            )

        # TODO: Implement analytics tracking
        # For now, just increment view count in guide stats
        # In production, store in separate guide_views collection

        # Mock view tracking
        view_id = f"view_{guide['book_id']}_{view_data.session_id or 'anon'}"
        guide_views = guide.get("stats", {}).get("total_views", 0) + 1
        chapter_views = None

        if view_data.chapter_slug:
            chapter = chapter_manager.get_chapter_by_slug(
                guide["book_id"], view_data.chapter_slug
            )
            if chapter:
                chapter_views = chapter.get("stats", {}).get("total_views", 0) + 1

        logger.info(f"📊 View tracked: {slug} (session: {view_data.session_id})")

        return ViewTrackingResponse(
            success=True,
            view_id=view_id,
            guide_views=guide_views,
            chapter_views=chapter_views,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to track view: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track view",
        )


@router.get(
    "/by-domain/{domain}",
    response_model=BookDomainResponse,
    status_code=status.HTTP_200_OK,
)
async def get_guide_by_domain(domain: str):
    """
    Get guide by custom domain (NO AUTHENTICATION REQUIRED)

    **Use Case:** Next.js middleware uses this to route custom domain requests

    **Path Parameters:**
    - domain: Custom domain (e.g., "python.example.com")

    **Returns:**
    - 200: Guide info for domain
    - 404: No guide found for this domain

    **Example Flow:**
    1. Request comes to python.example.com
    2. Middleware calls /api/v1/guides/by-domain/python.example.com
    3. Gets guide slug
    4. Rewrites to /g/{slug}
    """
    try:
        # Get guide by custom domain
        guide = guide_manager.get_guide_by_domain(domain)

        if not guide:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No guide found for domain '{domain}'",
            )

        response = BookDomainResponse(
            book_id=guide["book_id"],
            slug=guide["slug"],
            title=guide["title"],
            custom_domain=guide["custom_domain"],
            visibility=guide["visibility"],
            is_active=guide.get("is_active", True),
        )

        logger.info(f"🌐 Domain lookup: {domain} → {guide['slug']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get guide by domain: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get guide by domain",
        )


# ==============================================================================
# PHASE 6: COMMUNITY BOOKS & DOCUMENT INTEGRATION
# ==============================================================================


@router.post(
    "/{book_id}/publish-community",
    response_model=BookResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish book to community marketplace",
)
async def publish_book_to_community(
    book_id: str,
    publish_data: CommunityPublishRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Phase 6: Publish book to community marketplace**

    Publishes a book to the public community marketplace with author.

    **Author Flow:**
    1. If `author_id` provided: Use existing author (must be owned by user)
    2. If `author_name` provided: Create new author with auto-generated @ID
    3. Must provide either `author_id` OR `author_name`

    **Requirements:**
    - User must be the book owner
    - Either author_id (existing) or author_name (create new) required
    - Sets visibility (public or point_based) and access_config
    - Sets community_config.is_public = true

    **Request Body:**
    - author_id: Existing author ID (e.g., @john_doe) OR
    - author_name: Name for new author (will auto-generate @ID)
    - author_bio: Optional bio for new author
    - author_avatar_url: Optional avatar for new author
    - visibility: "public" (free) or "point_based" (paid)
    - access_config: Required if visibility=point_based
    - category, tags, difficulty_level, short_description
    """
    user_id = user["uid"]

    try:
        # Verify ownership
        book = guide_manager.get_guide(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Handle Author: Use existing or create new
        author_id = None

        if publish_data.author_id:
            # Use existing author
            existing_author = author_manager.get_author(publish_data.author_id)
            if not existing_author:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Author not found: {publish_data.author_id}",
                )

            # Verify ownership
            if existing_author["user_id"] != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't own this author profile",
                )

            author_id = publish_data.author_id
            logger.info(f"📚 Using existing author: {author_id}")

        elif publish_data.author_name:
            # Create new author with user-provided @ID
            # User must provide author_id when creating new author
            if not publish_data.author_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="author_id is required when creating new author. Please provide a unique @username (e.g., @john_doe)",
                )

            # Check if author_id already exists
            existing = author_manager.get_author(publish_data.author_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Author ID already taken: {publish_data.author_id}. Please choose a different @username.",
                )

            # Create author with user-provided ID
            author_data = {
                "author_id": publish_data.author_id,  # USER-PROVIDED
                "name": publish_data.author_name,
                "bio": publish_data.author_bio,
                "avatar_url": publish_data.author_avatar_url,
                "social_links": {},
            }

            try:
                created_author = author_manager.create_author(user_id, author_data)
                if not created_author:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to create author",
                    )
                author_id = publish_data.author_id
                logger.info(f"✅ Created new author: {author_id}")
            except Exception as e:
                logger.error(f"❌ Failed to create author: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create author: {str(e)}",
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either author_id (existing) or both author_id + author_name (new) must be provided",
            )

        # Publish to community with author
        updated_book = guide_manager.publish_to_community(
            book_id=book_id,
            user_id=user_id,
            publish_data=publish_data.dict(),
            author_id=author_id,
        )

        if not updated_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to publish book to community",
            )

        # Add book to author's published books list
        author_manager.add_book_to_author(author_id, book_id)

        logger.info(
            f"✅ User {user_id} published book {book_id} to community by author {author_id}"
        )
        return BookResponse(**updated_book)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to publish book to community: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish book to community",
        )


@router.patch(
    "/{book_id}/unpublish-community",
    response_model=BookResponse,
    status_code=status.HTTP_200_OK,
    summary="Unpublish book from community marketplace",
)
async def unpublish_book_from_community(
    book_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Phase 6: Unpublish book from community marketplace**

    Removes book from public community marketplace.

    Requirements:
    - User must be the book owner
    - Sets community_config.is_public = false
    """
    user_id = user["uid"]

    try:
        # Verify ownership
        book = guide_manager.get_guide(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Remove book from author's list (if has author)
        if book.get("author_id"):
            author_manager.remove_book_from_author(book["author_id"], book_id)

        # Unpublish from community
        updated_book = guide_manager.unpublish_from_community(
            book_id=book_id, user_id=user_id
        )

        if not updated_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to unpublish book from community",
            )

        logger.info(f"✅ User {user_id} unpublished book from community: {book_id}")
        return BookResponse(**updated_book)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to unpublish book from community: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unpublish book from community",
        )


@router.get(
    "/community/books",
    response_model=CommunityBooksResponse,
    status_code=status.HTTP_200_OK,
    summary="Browse community books (public marketplace)",
)
async def list_community_books(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty level"),
    sort_by: str = Query("popular", description="Sort by: popular, newest, rating"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    **Phase 6: Browse community books (public marketplace)**

    Lists public books in the community marketplace with filtering and sorting.

    Query Parameters:
    - category: Filter by category
    - tags: Comma-separated tags (e.g., "python,tutorial")
    - difficulty: beginner, intermediate, or advanced
    - sort_by: popular (views + purchases), newest (published_at), rating (avg rating)
    - page: Page number (1-indexed)
    - limit: Items per page (max 100)

    No authentication required (public endpoint).
    """
    try:
        skip = (page - 1) * limit
        tags_list = tags.split(",") if tags else None

        # Get community books
        books, total = guide_manager.list_community_books(
            category=category,
            tags=tags_list,
            difficulty=difficulty,
            sort_by=sort_by,
            skip=skip,
            limit=limit,
        )

        # Convert to response model
        items = [CommunityBookItem(**book) for book in books]

        response = CommunityBooksResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit,
        )

        logger.info(
            f"📚 Listed community books: {len(items)} results (page {page}/{response.total_pages})"
        )
        return response

    except Exception as e:
        logger.error(f"❌ Failed to list community books: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list community books",
        )


@router.post(
    "/{book_id}/chapters/from-document",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chapter from existing document",
)
async def create_chapter_from_document(
    book_id: str,
    request: ChapterFromDocumentRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Phase 6: Create chapter from existing document**

    Creates a chapter that references an existing document (no content duplication).

    - Chapter stores document_id reference
    - Content is loaded dynamically from documents collection
    - Document's used_in_books array is updated
    - content_source = "document" (vs "inline")

    Request Body:
    - document_id: UUID of existing document
    - title: Chapter title
    - order_index: Position in chapter list
    - parent_id: Optional parent chapter for nesting
    - icon: Chapter icon (emoji)
    - is_published: Publish immediately (default: false)
    """
    user_id = user["uid"]

    try:
        # Verify book ownership
        book = guide_manager.get_guide(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Create chapter from document
        chapter = chapter_manager.create_chapter_from_document(
            book_id=book_id,
            document_id=request.document_id,
            title=request.title,
            order_index=request.order_index,
            parent_id=request.parent_id,
            icon=request.icon,
            is_published=request.is_published,
        )

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create chapter from document (document may not exist)",
            )

        logger.info(
            f"✅ User {user_id} created chapter from document: {chapter['chapter_id']} → doc:{request.document_id}"
        )
        return ChapterResponse(**chapter)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create chapter from document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chapter from document",
        )


@router.get(
    "/{book_id}/chapters/{chapter_id}/content",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chapter with content (supports document references)",
)
async def get_chapter_with_content(
    book_id: str,
    chapter_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Phase 6: Get chapter with content (supports document references)**

    Gets chapter with content loaded dynamically.

    - If content_source = "inline": Returns content_html/content_json from chapter
    - If content_source = "document": Loads content from documents collection

    This allows chapters to reference documents without duplicating content.
    """
    user_id = user["uid"]

    try:
        # Verify book access
        book = guide_manager.get_guide(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Get chapter with content
        chapter = chapter_manager.get_chapter_with_content(chapter_id)

        if not chapter or chapter.get("book_id") != book_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        logger.info(
            f"📄 User {user_id} retrieved chapter content: {chapter_id} (source: {chapter.get('content_source', 'inline')})"
        )
        return ChapterResponse(**chapter)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter with content: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chapter with content",
        )


# ==============================================================================
# IMAGE UPLOAD API (Presigned URL for Book Images)
# ==============================================================================


@router.post("/upload-image/presigned-url", tags=["Book Images"])
async def get_book_image_presigned_url(
    request: BookImageUploadRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Generate presigned URL for book image upload (cover, logo, favicon)**

    This endpoint generates a presigned URL for uploading book images directly to R2 storage.

    **Supported Image Types:**
    - `cover`: Book cover image (cover_image_url)
    - `logo`: Book logo (logo_url)
    - `favicon`: Book favicon (favicon_url)

    **Flow:**
    1. Frontend calls this endpoint with filename, content_type, image_type, and file_size_mb
    2. Backend validates image format and size (max 10MB)
    3. Backend generates presigned URL (valid for 5 minutes)
    4. Frontend uploads file directly to presigned URL using PUT request
    5. Frontend updates book with the returned file_url

    **Image Constraints:**
    - Max file size: 10MB per image
    - Allowed formats: JPEG, PNG, WebP, SVG, GIF
    - Recommended sizes:
      - Cover: 1200x630px (og:image standard)
      - Logo: 512x512px (square)
      - Favicon: 32x32px or 64x64px

    **Returns:**
    - `presigned_url`: URL for uploading file (use PUT request with file content)
    - `file_url`: Public CDN URL to use in book update (cover_image_url, logo_url, or favicon_url)
    - `expires_in`: Presigned URL expiration time in seconds (300 = 5 minutes)
    - `image_type`: Type of image (cover, logo, favicon)

    **Example Usage:**
    ```python
    # 1. Get presigned URL
    response = await fetch('/api/v1/books/upload-image/presigned-url', {
        method: 'POST',
        body: JSON.stringify({
            filename: 'my-book-cover.jpg',
            content_type: 'image/jpeg',
            image_type: 'cover',
            file_size_mb: 2.5
        })
    })
    const { presigned_url, file_url } = await response.json()

    # 2. Upload file to presigned URL
    await fetch(presigned_url, {
        method: 'PUT',
        body: fileBlob,
        headers: { 'Content-Type': 'image/jpeg' }
    })

    # 3. Update book with file_url
    await fetch('/api/v1/books/{book_id}', {
        method: 'PATCH',
        body: JSON.stringify({ cover_image_url: file_url })
    })
    ```
    """
    try:
        from src.services.r2_storage_service import get_r2_service

        user_id = user["uid"]
        logger.info(
            f"🖼️ Generating presigned URL for book {request.image_type}: {request.filename} ({request.file_size_mb}MB) - User: {user_id}"
        )

        # Get R2 service
        r2_service = get_r2_service()

        # Generate folder path based on image type
        folder_map = {
            "cover": "book-covers",
            "logo": "book-logos",
            "favicon": "book-favicons",
        }
        folder = folder_map[request.image_type]

        # Generate presigned URL with custom folder
        result = r2_service.generate_presigned_upload_url(
            filename=request.filename,
            content_type=request.content_type,
            folder=folder,  # Store in organized folders
        )

        logger.info(
            f"✅ Generated presigned URL for {request.image_type}: {result['file_url']}"
        )

        # Return presigned URL
        return {
            "success": True,
            "presigned_url": result["presigned_url"],
            "file_url": result["file_url"],
            "image_type": request.image_type,
            "file_size_mb": request.file_size_mb,
            "expires_in": result["expires_in"],
        }

    except ValueError as e:
        logger.error(f"❌ R2 configuration error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Image upload service not configured properly",
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate upload URL: {str(e)}",
        )
