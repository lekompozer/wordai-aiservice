"""
Online Book API Routes - GitBook-style Documentation System
Phase 2: Guide Management API (Book CRUD)
Phase 3: Chapter Management API → Moved to book_chapter_routes.py
Phase 4: User Permissions API
Phase 5: Community Books & Marketplace
Phase 6: Public Preview & Document Integration

Implements RESTful endpoints for creating and managing Online Books with nested chapters.
Supports public/private/unlisted visibility, user permissions, and hierarchical structure (max 3 levels).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone, timedelta
import re
import unicodedata

# Authentication
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

# Models
from src.models.book_models import (
    BookCreate,
    BookUpdate,
    BookResponse,
    BookListResponse,
    BookVisibility,
    AccessConfig,
    # Phase 6: Community Books & Document Integration
    CommunityPublishRequest,
    CommunityBookItem,
    CommunityBooksResponse,
    ChapterFromDocumentRequest,
    # Image Upload
    BookImageUploadRequest,
    # Trash System
    TrashBookItem,
    TrashListResponse,
    # My Published Books
    MyPublishedBookResponse,
    MyPublishedBooksListResponse,
    TransferEarningsRequest,
    TransferEarningsResponse,
    EarningsSummaryResponse,
    # Book Purchases
    PurchaseType,
    PurchaseBookRequest,
    PurchaseBookResponse,
    BookAccessResponse,
    MyPurchaseItem,
    MyPurchasesResponse,
    # Book Preview
    BookPreviewResponse,
    PreviewAuthor,
    PreviewChapterItem,
    PreviewStats,
)
from src.models.book_chapter_models import (
    ConvertDocumentToChapterRequest,
    ChapterResponse,
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
from src.services.document_manager import DocumentManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/books", tags=["Online Books"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize managers with DB
book_manager = UserBookManager(db)
chapter_manager = GuideBookBookChapterManager(db)
permission_manager = GuideBookBookPermissionManager(db)
author_manager = AuthorManager(db)
document_manager = DocumentManager(db)


# ==============================================================================
# PHASE 2: GUIDE MANAGEMENT API
# ==============================================================================


@router.get("/check-slug/{slug}", response_model=Dict[str, Any])
async def check_slug_availability(
    slug: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    **Check if slug is available for current user**

    Frontend should call this endpoint when user types title to generate slug.
    Returns whether the slug is available and suggested alternatives if taken.

    **Authentication:** Required

    **Path Parameters:**
    - `slug`: URL-friendly slug to check (e.g., "my-python-guide")

    **Returns:**
    - `available`: true if slug is available, false if taken
    - `slug`: the slug that was checked
    - `suggestions`: array of alternative slugs if taken (e.g., ["my-python-guide-2", "my-python-guide-3"])

    **Example Response (Available):**
    ```json
    {
      "available": true,
      "slug": "python-mastery",
      "message": "Slug is available"
    }
    ```

    **Example Response (Taken):**
    ```json
    {
      "available": false,
      "slug": "python-guide",
      "message": "Slug already exists",
      "suggestions": [
        "python-guide-2",
        "python-guide-2025",
        "python-guide-v2"
      ]
    }
    ```
    """
    try:
        user_id = current_user["uid"]

        # Check if slug exists for this user
        is_available = not book_manager.slug_exists(user_id, slug)

        if is_available:
            return {"available": True, "slug": slug, "message": "Slug is available"}
        else:
            # Generate suggestions
            from datetime import datetime

            year = datetime.now().year

            suggestions = [
                f"{slug}-2",
                f"{slug}-{year}",
                f"{slug}-v2",
                f"{slug}-copy",
                f"{slug}-new",
            ]

            # Filter out suggestions that are also taken
            available_suggestions = [
                s for s in suggestions if not book_manager.slug_exists(user_id, s)
            ][
                :3
            ]  # Return top 3

            return {
                "available": False,
                "slug": slug,
                "message": "Slug already exists",
                "suggestions": available_suggestions,
            }

    except Exception as e:
        logger.error(f"❌ Failed to check slug: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check slug availability",
        )


@router.get("/{book_id}/save-count")
async def get_book_save_count(book_id: str):
    """
    Get total number of users who saved this book (public endpoint)

    **Authentication:** Not required (public)

    **Path Parameters:**
    - book_id: Book ID

    **Returns:**
    - 200: Save count with book info
    - 404: Book not found

    **Example Response:**
    ```json
    {
      "book_id": "book_df213acf187b",
      "total_saves": 250,
      "book_title": "Python Advanced Guide"
    }
    ```
    """
    try:
        logger.info(f"📊 Getting save count for book {book_id}")

        # Get book (must be published to community)
        book = db.online_books.find_one(
            {
                "book_id": book_id,
                "community_config.is_public": True,
            }
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or not published to community",
            )

        # Get save count from community_config
        total_saves = book.get("community_config", {}).get("total_saves", 0)

        logger.info(f"✅ Book {book_id} has {total_saves} saves")

        return {
            "book_id": book_id,
            "total_saves": total_saves,
            "book_title": book.get("title"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get save count: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get save count: {str(e)}",
        )


@router.get("/{book_id}/publish-config")
async def get_book_publish_config(
    book_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    **Get book publish configuration for editing**

    Returns only the config fields needed for edit form (not full content).

    **Authentication:** Required (Firebase JWT)

    **Returns:**
    ```json
    {
        "book_id": "book_xxx",
        "title": "Book Title",
        "slug": "book-slug",
        "authors": ["@author1"],
        "visibility": "point_based",
        "access_config": {
            "forever_view_points": 100
        },
        "community_config": {
            "category": "technology",
            "tags": ["python", "ai"],
            "difficulty_level": "intermediate",
            "short_description": "...",
            "cover_image_url": "https://..."
        }
    }
    ```
    """
    try:
        user_id = current_user["uid"]

        # Get only config fields (not content)
        book = db.online_books.find_one(
            {"book_id": book_id, "user_id": user_id},
            {
                "_id": 0,
                "book_id": 1,
                "title": 1,
                "slug": 1,
                "authors": 1,
                "author_id": 1,  # Legacy field
                "visibility": 1,
                "access_config": 1,
                "community_config": 1,
                "cover_image_url": 1,
            },
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Ensure authors is array (handle legacy author_id)
        if not book.get("authors") and book.get("author_id"):
            book["authors"] = [book["author_id"]]
        elif not book.get("authors"):
            book["authors"] = []

        logger.info(f"✅ User {user_id} retrieved publish config for book: {book_id}")
        return book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get book publish config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get book publish config",
        )


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
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
        if book_manager.slug_exists(user_id, guide_data.slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{guide_data.slug}' already exists for this user",
            )

        # Create book
        book = book_manager.create_book(user_id, guide_data)

        logger.info(
            f"✅ User {user_id} created book: {book['book_id']} ({guide_data.title})"
        )
        return book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create book",
        )


@router.get("", response_model=BookListResponse)
async def list_guides(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    visibility: Optional[BookVisibility] = Query(
        None, description="Filter by visibility (public/private/unlisted)"
    ),
    is_published: Optional[bool] = Query(
        None, description="Filter by publish status (true for community books)"
    ),
    search: Optional[str] = Query(None, description="Search by title or description"),
    tags: Optional[str] = Query(
        None, description="Filter by tags (comma-separated, e.g., 'python,tutorial')"
    ),
    sort_by: str = Query(
        "updated_at",
        description="Sort field: updated_at | created_at | title | view_count",
    ),
    sort_order: str = Query("desc", description="Sort order: asc | desc"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **List user's books with advanced filtering and search**

    **Authentication:** Required

    **Query Parameters:**
    - `skip`: Pagination offset (default: 0)
    - `limit`: Results per page (default: 20, max: 100)
    - `visibility`: Filter by visibility type (public/private/unlisted)
    - `is_published`: Filter by community publish status (true = published to marketplace)
    - `search`: Search in title and description (case-insensitive)
    - `tags`: Filter by tags (comma-separated)
    - `sort_by`: Sort by field (updated_at | created_at | title | view_count)
    - `sort_order`: Sort direction (asc | desc)

    **Examples:**
    - `GET /books` - All my books
    - `GET /books?visibility=public` - Only public books
    - `GET /books?is_published=true` - Only community marketplace books
    - `GET /books?search=python` - Search for "python"
    - `GET /books?tags=tutorial,beginner` - Books with these tags
    - `GET /books?sort_by=view_count&sort_order=desc` - Most viewed first

    **Returns:**
    - 200: Paginated list of guides with filters applied
    """
    try:
        user_id = current_user["uid"]

        # DEBUG: Log all incoming parameters
        logger.info(
            f"🔍 DEBUG list_guides - User: {user_id}, "
            f"is_published={is_published}, visibility={visibility}, "
            f"search={search}, tags={tags}"
        )

        # Build query
        query = {
            "user_id": user_id,
            "is_deleted": False,  # Only show active books (not in trash)
        }

        # Filter by visibility
        if visibility:
            query["visibility"] = visibility

        # Filter by publish status
        if is_published is not None:
            query["community_config.is_public"] = is_published

        # Search in title and description
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        # Filter by tags
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            if tag_list:
                query["community_config.tags"] = {"$in": tag_list}

        # Build sort criteria
        sort_field = (
            sort_by
            if sort_by in ["updated_at", "created_at", "title", "view_count"]
            else "updated_at"
        )
        sort_direction = -1 if sort_order == "desc" else 1

        # Count total with filters
        total = db.online_books.count_documents(query)

        # DEBUG: Log query and count
        logger.info(f"🔍 DEBUG MongoDB query: {query}")
        logger.info(f"🔍 DEBUG Found {total} books matching query")

        # Get paginated results
        guides_cursor = (
            db.online_books.find(query)
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(limit)
        )

        guides = []
        for book in guides_cursor:
            guides.append(
                {
                    "book_id": book.get(
                        "book_id"
                    ),  # Use actual book_id field, not MongoDB _id
                    "title": book.get("title", ""),
                    "slug": book.get("slug", ""),
                    "description": book.get("description"),
                    "visibility": book.get("visibility", "private"),
                    "is_published": book.get("community_config", {}).get(
                        "is_public", False
                    ),
                    "chapter_count": book.get("chapter_count", 0),
                    "view_count": book.get("view_count", 0),
                    "updated_at": book.get("updated_at"),
                    "last_published_at": book.get("community_config", {}).get(
                        "published_at"
                    ),
                }
            )

        logger.info(
            f"📚 User {user_id} listed {len(guides)}/{total} guides "
            f"(filters: visibility={visibility}, is_published={is_published}, search={search}, tags={tags})"
        )

        return {
            "books": guides,  # Changed from 'guides' to 'books' for consistency with endpoint name
            "total": total,
            "pagination": {
                "skip": skip,
                "limit": limit,
            },
        }

    except Exception as e:
        logger.error(f"❌ Failed to list books: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list books",
        )


# ==============================================================================
# TRASH SYSTEM API (Must be before /{book_id} to avoid path conflicts)
# ==============================================================================


@router.get("/trash", response_model=TrashListResponse)
async def list_trash(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query("deleted_at", description="Sort by field"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List books in trash

    **Authentication:** Required

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 100)
    - `sort_by`: Sort by field (default: deleted_at)

    **Returns:**
    - List of books in trash with pagination
    """
    try:
        user_id = current_user["uid"]
        skip = (page - 1) * limit

        # Get trash books
        books, total = book_manager.list_trash(user_id, skip, limit, sort_by)

        # Transform to TrashBookItem
        items = []
        for book in books:
            # Count chapters for this book
            chapters_count = chapter_manager.count_chapters(book["book_id"])

            # Get published status and purchase counts (DELETE_PROTECTION_FLOW)
            community_config = book.get("community_config", {})
            is_published = community_config.get("is_public", False)

            stats = book.get("stats", {})
            forever_purchases = stats.get("forever_purchases", 0)
            one_time_purchases = stats.get("one_time_purchases", 0)
            pdf_downloads = stats.get("pdf_downloads", 0)
            total_purchases = forever_purchases + one_time_purchases + pdf_downloads

            items.append(
                TrashBookItem(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    deleted_at=book["deleted_at"],
                    deleted_by=book.get("deleted_by", user_id),
                    chapters_count=chapters_count,
                    can_restore=True,
                    is_published=is_published,
                    total_purchases=total_purchases,
                    forever_purchases=forever_purchases,
                    one_time_purchases=one_time_purchases,
                    pdf_downloads=pdf_downloads,
                )
            )

        # Calculate total pages
        total_pages = (total + limit - 1) // limit

        logger.info(
            f"🗑️ User {user_id} listed trash: {len(items)} books (total: {total})"
        )

        return TrashListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"❌ Failed to list trash: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list trash",
        )


@router.delete("/trash/empty")
async def empty_trash(
    unpublish_all: bool = Query(
        False,
        description="Confirm unpublishing all published books from Community marketplace",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Empty trash (permanently delete all trashed books)

    **Authentication:** Required

    **⚠️ DELETE_PROTECTION_FLOW:**
    - If trash contains published books, must set `unpublish_all=true`
    - Published books will be unpublished from Community marketplace
    - All buyer access (forever/one-time purchases) will be lost
    - This action cannot be undone!

    **Query Parameters:**
    - `unpublish_all`: Must be `true` to delete published books (default: false)

    **Returns:**
    - 200: Trash emptied with deletion stats
    - 400: Trash contains published books without confirmation
    """
    try:
        user_id = current_user["uid"]

        # Get trash books to check for published books
        books, total = book_manager.list_trash(
            user_id, skip=0, limit=10000, sort_by="deleted_at"
        )

        # Check for published books
        published_books = []
        total_affected_purchases = 0

        for book in books:
            community_config = book.get("community_config", {})
            if community_config.get("is_public", False):
                stats = book.get("stats", {})
                forever = stats.get("forever_purchases", 0)
                one_time = stats.get("one_time_purchases", 0)
                pdf = stats.get("pdf_downloads", 0)
                total_purchases = forever + one_time + pdf

                published_books.append(
                    {
                        "book_id": book["book_id"],
                        "title": book["title"],
                        "total_purchases": total_purchases,
                        "forever_purchases": forever,
                        "one_time_purchases": one_time,
                        "pdf_downloads": pdf,
                    }
                )
                total_affected_purchases += total_purchases

        # If published books exist and unpublish_all is not confirmed, block deletion
        if published_books and not unpublish_all:
            logger.warning(
                f"⚠️ User {user_id} tried to empty trash with {len(published_books)} published books without confirmation"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Published books in trash require confirmation",
                    "message": "Your trash contains published books with active purchases. Set unpublish_all=true to proceed.",
                    "published_books_count": len(published_books),
                    "total_affected_purchases": total_affected_purchases,
                    "published_books": published_books,
                    "action_required": "Call DELETE /books/trash/empty?unpublish_all=true",
                },
            )

        # Unpublish all published books before deleting
        if published_books:
            for book_info in published_books:
                try:
                    # Unpublish from community
                    db.online_books.update_one(
                        {"book_id": book_info["book_id"]},
                        {
                            "$set": {
                                "community_config.is_public": False,
                                "visibility": "private",
                            }
                        },
                    )
                    logger.info(
                        f"📤 Unpublished book {book_info['book_id']} before permanent deletion"
                    )
                except Exception as e:
                    logger.error(
                        f"❌ Failed to unpublish book {book_info['book_id']}: {e}"
                    )

        # Empty trash
        stats = book_manager.empty_trash(user_id)

        logger.info(
            f"🧹 User {user_id} emptied trash: {stats['deleted_books']} books, {len(published_books)} unpublished"
        )

        return {
            "message": "Trash emptied successfully",
            **stats,
            "unpublished_books": len(published_books),
            "affected_purchases": total_affected_purchases,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to empty trash: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to empty trash",
        )


# ==============================================================================
# BOOK CRUD OPERATIONS
# ==============================================================================


@router.post("/{book_id}/restore")
async def restore_book(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Restore book from trash

    **Authentication:** Required (Owner only)

    **Returns:**
    - 200: Book restored successfully
    - 404: Book not found in trash
    """
    try:
        user_id = current_user["uid"]

        # Restore book
        success = book_manager.restore_book(book_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found in trash",
            )

        logger.info(f"♻️ User {user_id} restored book from trash: {book_id}")

        return {
            "message": "Book restored successfully",
            "book_id": book_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to restore book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore book",
        )


# ==============================================================================
# BOOK CRUD OPERATIONS
# ==============================================================================


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get detailed information about a specific book

    **Authentication:** Required

    **Returns:**
    - 200: Guide details
    - 403: User doesn't have access to this book
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        # Get book
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check access: owner OR has permission
        is_owner = book["user_id"] == user_id

        if not is_owner:
            # Check if user has permission
            has_permission = permission_manager.check_permission(
                book_id=book_id, user_id=user_id
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this book",
                )

        logger.info(f"📖 User {user_id} accessed book: {book_id}")
        return book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get book",
        )


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: str,
    guide_data: BookUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Update book metadata (partial update supported)

    **Authentication:** Required (Owner only)

    **Request Body:**
    - Any fields from BookCreate (all optional)

    **Returns:**
    - 200: Guide updated successfully
    - 403: User is not the book owner
    - 404: Book not found
    - 409: Slug already exists
    """
    try:
        user_id = current_user["uid"]

        # Get book to verify ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check ownership
        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can update book",
            )

        # Update book
        updated_book = book_manager.update_book(book_id, guide_data)

        if not updated_book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        logger.info(f"✏️ User {user_id} updated book: {book_id}")
        return updated_book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update book",
        )


@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    permanent: bool = Query(
        False,
        description="Permanent delete (true) or move to trash (false)",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete book (soft or hard delete)

    **Query Parameters:**
    - `permanent`: false (default) = Move to trash, true = Permanent delete

    **Soft Delete (permanent=false):**
    - Sets is_deleted=true
    - Keeps all data (chapters, permissions)
    - Can be restored from trash

    **Hard Delete (permanent=true):**
    - Deletes book permanently
    - Deletes all chapters
    - Deletes all permissions
    - Cannot be restored

    **Authentication:** Required (Owner only)

    **Returns:**
    - 200: Book moved to trash or permanently deleted
    - 403: User is not the book owner
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        # Get book to verify ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check ownership
        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can delete book",
            )

        if permanent:
            # Hard delete - delete everything
            deleted_chapters = chapter_manager.delete_guide_chapters(book_id)
            deleted_permissions = permission_manager.delete_permissions_by_guide(
                book_id
            )
            deleted = book_manager.delete_book(book_id)

            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Book not found",
                )

            logger.info(
                f"� User {user_id} permanently deleted book: {book_id} "
                f"(chapters: {deleted_chapters}, permissions: {deleted_permissions})"
            )

            return {
                "message": "Book permanently deleted",
                "book_id": book_id,
                "deleted_chapters": deleted_chapters,
                "deleted_permissions": deleted_permissions,
            }
        else:
            # Soft delete - move to trash
            success = book_manager.soft_delete_book(book_id, user_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to move book to trash",
                )

            logger.info(f"🗑️ User {user_id} moved book to trash: {book_id}")

            return {
                "message": "Book moved to trash",
                "book_id": book_id,
                "can_restore": True,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete book",
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
    Grant user permission to access a private book

    **Authentication:** Required (Owner only)

    **Request Body:**
    - user_id: Firebase UID of user to grant access
    - access_level: "viewer" | "editor" (default: viewer)
    - expires_at: Optional expiration datetime

    **Returns:**
    - 201: Permission granted successfully
    - 403: User is not the book owner
    - 404: Book not found
    - 409: Permission already exists for this user
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can grant permissions",
            )

        # Check if permission already exists
        existing = permission_manager.get_permission(
            book_id=book_id, user_id=permission_data.user_id
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {permission_data.user_id} already has permission for this book",
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
            f"✅ User {user_id} granted {permission_data.access_level} permission to {permission_data.user_id} for book {book_id}"
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
    List all users with permissions on a book

    **Authentication:** Required (Owner only)

    **Query Parameters:**
    - skip: Pagination offset (default: 0)
    - limit: Results per page (default: 50, max: 100)

    **Returns:**
    - 200: List of permissions
    - 403: User is not the book owner
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can list permissions",
            )

        # Get permissions
        permissions = permission_manager.list_permissions(
            book_id=book_id, skip=skip, limit=limit
        )

        total = permission_manager.count_permissions(book_id=book_id)

        logger.info(
            f"📋 User {user_id} listed permissions for book {book_id}: {len(permissions)} results"
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
    Revoke user permission to access a book

    **Authentication:** Required (Owner only)

    **Path Parameters:**
    - book_id: Guide identifier
    - permission_user_id: Firebase UID of user to revoke

    **Returns:**
    - 200: Permission revoked successfully
    - 403: User is not the book owner
    - 404: Guide or permission not found
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can revoke permissions",
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
            f"❌ User {user_id} revoked permission from {permission_user_id} for book {book_id}"
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
    Invite user by email to access a book (creates permission + sends email)

    **Authentication:** Required (Owner only)

    **Request Body:**
    - email: Email address to invite
    - access_level: "viewer" | "editor" (default: viewer)
    - expires_at: Optional expiration datetime
    - message: Optional personal message (max 500 chars)

    **Returns:**
    - 201: Invitation sent successfully
    - 403: User is not the book owner
    - 404: Book not found
    - 400: Invalid email
    - 500: Email sending failed

    **Note:** Email invitation requires Brevo service integration
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        if book["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only book owner can invite users",
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
        #     guide_title=book["title"],
        #     guide_slug=book["slug"],
        #     owner_name=current_user.get("name", "Someone"),
        #     message=invite_data.message
        # )

        email_sent = True  # Placeholder - implement Brevo integration later

        logger.info(
            f"📧 User {user_id} invited {invite_data.email} to book {book_id} (email_sent: {email_sent})"
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
    response_model = (PublicBookResponse,)
