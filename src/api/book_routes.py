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
from datetime import datetime, timezone

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
    ChapterCreate,
    ChapterUpdate,
    ChapterContentUpdate,
    ConvertDocumentToChapterRequest,
    ChapterResponse,
    ChapterTreeNode,
    ChapterReorderBulk,
    TogglePreviewRequest,
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
    slug: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
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
            return {
                "available": True,
                "slug": slug,
                "message": "Slug is available"
            }
        else:
            # Generate suggestions
            from datetime import datetime
            year = datetime.now().year

            suggestions = [
                f"{slug}-2",
                f"{slug}-{year}",
                f"{slug}-v2",
                f"{slug}-copy",
                f"{slug}-new"
            ]

            # Filter out suggestions that are also taken
            available_suggestions = [
                s for s in suggestions
                if not book_manager.slug_exists(user_id, s)
            ][:3]  # Return top 3

            return {
                "available": False,
                "slug": slug,
                "message": "Slug already exists",
                "suggestions": available_suggestions
            }

    except Exception as e:
        logger.error(f"❌ Failed to check slug: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check slug availability"
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
        books, total = book_manager.list_trash(user_id, skip=0, limit=10000, sort_by="deleted_at")

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
# MY PUBLISHED BOOKS API (Creator Dashboard)
# ==============================================================================


@router.get("/my-published", response_model=MyPublishedBooksListResponse)
async def list_my_published_books(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query(
        "published_at", description="Sort by: published_at | revenue | views | rating"
    ),
    sort_order: str = Query("desc", description="Sort order: asc | desc"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **List my published books with earnings stats**

    Get all books I've published to community marketplace with detailed stats:
    - Revenue (total, owner share, system fee)
    - Purchases (one-time, forever, PDF downloads)
    - Engagement (views, readers, ratings)

    **Authentication:** Required

    **Query Parameters:**
    - `skip`: Pagination offset (default: 0)
    - `limit`: Results per page (default: 20, max: 100)
    - `category`: Filter by category
    - `sort_by`: Sort field (published_at | revenue | views | rating)
    - `sort_order`: Sort direction (asc | desc)

    **Returns:**
    - 200: List of my published books with stats
    """
    try:
        user_id = current_user["uid"]

        # Build query for published books (including trashed ones per DELETE_PROTECTION_FLOW)
        query = {
            "user_id": user_id,
            # NOTE: No is_deleted filter! Trashed published books still show here
            "community_config.is_public": True,
        }

        # Filter by category
        if category:
            query["community_config.category"] = category

        # Determine sort field
        sort_field_map = {
            "published_at": "community_config.published_at",
            "revenue": "stats.total_revenue_points",
            "views": "community_config.total_views",
            "rating": "community_config.average_rating",
        }
        sort_field = sort_field_map.get(sort_by, "community_config.published_at")
        sort_direction = -1 if sort_order == "desc" else 1

        # Count total
        total = db.online_books.count_documents(query)

        # Get books
        books_cursor = (
            db.online_books.find(query)
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(limit)
        )

        books = []
        for book in books_cursor:
            # Get community config
            community_config = book.get("community_config", {})
            access_config = book.get("access_config", {})
            stats = book.get("stats", {})

            # Calculate stats
            total_revenue = stats.get("total_revenue_points", 0)
            owner_reward = stats.get("owner_reward_points", 0)
            system_fee = stats.get("system_fee_points", 0)

            # Get author info (first author or user)
            authors = book.get("authors", [])
            author_name = None
            if authors:
                # TODO: Query author name from authors collection
                author_name = authors[0]  # For now, use author_id

            books.append(
                MyPublishedBookResponse(
                    book_id=book["book_id"],
                    title=book["title"],
                    slug=book["slug"],
                    description=book.get("description"),
                    author_name=author_name,
                    authors=authors,
                    category=community_config.get("category"),
                    tags=community_config.get("tags", []),
                    difficulty_level=community_config.get("difficulty_level"),
                    cover_image_url=community_config.get("cover_image_url"),
                    access_config=access_config if access_config else None,
                    stats={
                        "total_one_time_purchases": stats.get(
                            "one_time_purchases", 0
                        ),
                        "total_forever_purchases": stats.get("forever_purchases", 0),
                        "total_pdf_downloads": stats.get("pdf_downloads", 0),
                        "total_purchases": community_config.get("total_purchases", 0),
                        "total_revenue_points": total_revenue,
                        "owner_reward_points": owner_reward,
                        "system_fee_points": system_fee,
                        "pending_transfer_points": owner_reward,  # All earnings pending for now
                        "total_views": community_config.get("total_views", 0),
                        "total_readers": community_config.get("total_purchases", 0),
                        "average_rating": community_config.get("average_rating", 0.0),
                        "rating_count": community_config.get("rating_count", 0),
                    },
                    is_deleted=book.get("is_deleted", False),  # DELETE_PROTECTION_FLOW
                    published_at=community_config.get("published_at"),
                    updated_at=book.get("updated_at"),
                )
            )

        logger.info(
            f"📊 User {user_id} listed {len(books)}/{total} published books "
            f"(category={category}, sort={sort_by})"
        )

        return MyPublishedBooksListResponse(
            books=books,
            total=total,
            pagination={"skip": skip, "limit": limit},
        )

    except Exception as e:
        logger.error(f"❌ Failed to list my published books: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list my published books",
        )


@router.get("/earnings", response_model=EarningsSummaryResponse)
async def get_earnings_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Get earnings summary for all published books**

    Returns aggregated earnings data across all books published by current user:
    - Total revenue, owner reward, platform fee
    - Breakdown by access type (one-time, forever, PDF)
    - Top earning book

    **Authentication:** Required

    **Returns:**
    - 200: Earnings summary with breakdown
    """
    try:
        user_id = current_user["uid"]

        # Query all published books
        query = {
            "user_id": user_id,
            "is_deleted": False,
            "community_config.is_public": True,
        }

        published_books = list(db.online_books.find(query))

        # Calculate totals
        total_books = len(published_books)
        total_revenue = 0
        owner_reward = 0
        platform_fee = 0

        # Breakdown (TODO: implement actual tracking)
        one_time_revenue = 0
        forever_revenue = 0
        pdf_revenue = 0

        # Find top earning book
        top_book = None
        max_revenue = 0

        for book in published_books:
            stats = book.get("stats", {})
            book_revenue = stats.get("total_revenue_points", 0)
            book_owner_reward = stats.get("owner_reward_points", 0)
            book_system_fee = stats.get("system_fee_points", 0)

            total_revenue += book_revenue
            owner_reward += book_owner_reward
            platform_fee += book_system_fee

            # Aggregate revenue breakdown by purchase type
            one_time_revenue += stats.get("one_time_revenue", 0)
            forever_revenue += stats.get("forever_revenue", 0)
            pdf_revenue += stats.get("pdf_revenue", 0)

            # Track top earning book
            if book_revenue > max_revenue:
                max_revenue = book_revenue
                top_book = {
                    "book_id": book["book_id"],
                    "title": book["title"],
                    "revenue": book_revenue,
                }

        logger.info(
            f"📊 User {user_id} earnings summary: {total_books} books, "
            f"{total_revenue} total revenue, {owner_reward} owner reward"
        )

        return EarningsSummaryResponse(
            total_books_published=total_books,
            total_revenue=total_revenue,
            owner_reward=owner_reward,
            platform_fee=platform_fee,
            breakdown={
                "one_time_revenue": one_time_revenue,
                "forever_revenue": forever_revenue,
                "pdf_revenue": pdf_revenue,
            },
            top_earning_book=top_book,
        )

    except Exception as e:
        logger.error(f"❌ Failed to get earnings summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get earnings summary",
        )


@router.post("/earnings/transfer", response_model=TransferEarningsResponse)
async def transfer_book_earnings(
    request: TransferEarningsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Transfer book earnings to user wallet**

    Transfer owner's reward points from book revenue to user's main wallet.

    **Authentication:** Required

    **Request Body:**
    - `book_id`: Book ID to transfer earnings from
    - `amount_points`: Amount to transfer (optional, default: all pending)

    **Returns:**
    - 200: Transfer successful with transaction details
    - 403: Not book owner
    - 404: Book not found
    - 400: Insufficient balance
    """
    try:
        user_id = current_user["uid"]
        book_id = request.book_id

        # Get book
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
                detail="Only book owner can transfer earnings",
            )

        # Get current stats
        stats = book.get("stats", {})
        owner_reward_points = stats.get("owner_reward_points", 0)

        # Determine transfer amount
        transfer_amount = request.amount_points or owner_reward_points

        if transfer_amount > owner_reward_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Available: {owner_reward_points} points",
            )

        if transfer_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No earnings to transfer",
            )

        # TODO: Implement actual wallet transfer
        # For now, just return mock response
        import uuid
        from datetime import datetime

        transaction_id = f"tx_{uuid.uuid4().hex[:16]}"

        # Update book stats (reduce owner_reward_points)
        db.online_books.update_one(
            {"book_id": book_id},
            {"$inc": {"stats.owner_reward_points": -transfer_amount}},
        )

        # Get user's current wallet balance (mock for now)
        # TODO: Integrate with actual wallet service
        new_wallet_balance = 10000 + transfer_amount  # Mock balance

        logger.info(
            f"💰 User {user_id} transferred {transfer_amount} points from book {book_id}"
        )

        return TransferEarningsResponse(
            book_id=book_id,
            transferred_points=transfer_amount,
            new_wallet_balance=new_wallet_balance,
            transaction_id=transaction_id,
            timestamp=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to transfer earnings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transfer earnings",
        )


@router.get("/my-purchases", response_model=MyPurchasesResponse)
async def list_my_purchases(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    purchase_type: Optional[PurchaseType] = Query(
        None, description="Filter by purchase type"
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **List all books I've purchased**

    Returns list of purchased books with access status, even if book is deleted.
    Per DELETE_PROTECTION_FLOW: trashed books with purchases remain accessible.

    **Authentication:** Required

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 20, max: 100)
    - `purchase_type`: Filter by type (one_time, forever, pdf_download)

    **Returns:**
    - 200: List of my purchases with book info and access status

    **Access Status:**
    - `active`: Currently accessible
    - `expired`: One-time purchase expired
    - `book_deleted_unpublished`: Book unpublished from Community (no access)
    """
    try:
        user_id = current_user["uid"]
        skip = (page - 1) * limit

        # Build query
        query = {"user_id": user_id}
        if purchase_type:
            query["purchase_type"] = purchase_type.value

        # Count total
        total = db.book_purchases.count_documents(query)

        # Get purchases
        purchases_cursor = (
            db.book_purchases.find(query)
            .sort("purchased_at", -1)
            .skip(skip)
            .limit(limit)
        )

        items = []
        now = datetime.now(timezone.utc)

        for purchase in purchases_cursor:
            book_id = purchase["book_id"]

            # Get book info (even if deleted!)
            book = db.online_books.find_one({"book_id": book_id})

            if not book:
                # Book permanently deleted
                access_status = "book_deleted_unpublished"
                book_title = "Deleted Book"
                book_slug = ""
                book_cover = None
                book_is_deleted = True
            else:
                # Check access status
                book_is_deleted = book.get("is_deleted", False)
                is_published = book.get("community_config", {}).get("is_public", False)

                if not is_published:
                    # Book unpublished - no access
                    access_status = "book_deleted_unpublished"
                elif purchase["purchase_type"] == PurchaseType.ONE_TIME.value:
                    # Check expiry
                    expires_at = purchase.get("access_expires_at")
                    if expires_at and expires_at > now:
                        access_status = "active"
                    else:
                        access_status = "expired"
                else:
                    # Forever or PDF - always active if published
                    access_status = "active"

                book_title = book["title"]
                book_slug = book["slug"]
                book_cover = book.get("cover_image_url")

            items.append(
                MyPurchaseItem(
                    purchase_id=purchase["purchase_id"],
                    book_id=book_id,
                    book_title=book_title,
                    book_slug=book_slug,
                    book_cover_url=book_cover,
                    book_is_deleted=book_is_deleted,
                    purchase_type=PurchaseType(purchase["purchase_type"]),
                    points_spent=purchase["points_spent"],
                    purchased_at=purchase["purchased_at"],
                    access_expires_at=purchase.get("access_expires_at"),
                    access_status=access_status,
                )
            )

        total_pages = (total + limit - 1) // limit

        logger.info(
            f"📚 User {user_id} listed {len(items)}/{total} purchases (page {page})"
        )

        return MyPurchasesResponse(
            purchases=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"❌ Failed to list my purchases: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list my purchases",
        )


@router.post("/{book_id}/purchase", response_model=PurchaseBookResponse)
async def purchase_book(
    book_id: str,
    request: PurchaseBookRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Purchase book access with points**

    Buy one-time, forever, or PDF download access to a book.

    **Authentication:** Required

    **Path Parameters:**
    - `book_id`: Book ID to purchase

    **Request Body:**
    - `purchase_type`: "one_time" | "forever" | "pdf_download"

    **Returns:**
    - 200: Purchase successful with access details
    - 400: Insufficient balance or invalid purchase type
    - 404: Book not found
    - 409: Already purchased (for forever access)
    """
    try:
        user_id = current_user["uid"]
        purchase_type = request.purchase_type

        # Get book
        book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is published and has point-based access
        visibility = book.get("visibility")
        if visibility != "point_based":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Book is not available for purchase",
            )

        # Get access config
        access_config = book.get("access_config", {})
        if not access_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Book access config not found",
            )

        # Determine points cost
        points_map = {
            PurchaseType.ONE_TIME: access_config.get("one_time_view_points", 0),
            PurchaseType.FOREVER: access_config.get("forever_view_points", 0),
            PurchaseType.PDF_DOWNLOAD: access_config.get("download_pdf_points", 0),
        }

        points_cost = points_map.get(purchase_type, 0)
        if points_cost <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase type '{purchase_type}' not enabled for this book",
            )

        # Check if user already has forever access
        if purchase_type == PurchaseType.FOREVER:
            existing_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.FOREVER,
                }
            )
            if existing_purchase:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You already have forever access to this book",
                )

        # Check user's subscription and balance (from user_subscriptions collection)
        subscription = db.user_subscriptions.find_one({"user_id": user_id})
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User subscription not found",
            )

        user_balance = subscription.get("points_remaining", 0)

        if user_balance < points_cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Required: {points_cost} points, Available: {user_balance}",
            )

        # Calculate revenue split (80% owner, 20% platform)
        total_revenue = points_cost
        owner_reward = int(points_cost * 0.8)
        system_fee = points_cost - owner_reward

        # Deduct points from buyer's subscription
        from datetime import datetime, timedelta, timezone

        result = db.user_subscriptions.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "points_remaining": -points_cost,
                    "points_used": points_cost,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deduct points",
            )

        # Create purchase record
        import uuid

        purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"
        purchase_time = datetime.utcnow()

        # Set expiry for one-time purchases (24 hours)
        access_expires_at = None
        if purchase_type == PurchaseType.ONE_TIME:
            access_expires_at = purchase_time + timedelta(hours=24)

        purchase_record = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "book_id": book_id,
            "purchase_type": purchase_type,
            "points_spent": points_cost,
            "access_expires_at": access_expires_at,
            "purchased_at": purchase_time,
        }

        db.book_purchases.insert_one(purchase_record)

        # Update book stats with purchase type breakdown
        stats_update = {
            "$inc": {
                "stats.total_revenue_points": total_revenue,
                "stats.owner_reward_points": owner_reward,
                "stats.system_fee_points": system_fee,
                "community_config.total_purchases": 1,
            }
        }

        # Increment specific purchase type counters
        if purchase_type == PurchaseType.ONE_TIME:
            stats_update["$inc"]["stats.one_time_purchases"] = 1
            stats_update["$inc"]["stats.one_time_revenue"] = total_revenue
        elif purchase_type == PurchaseType.FOREVER:
            stats_update["$inc"]["stats.forever_purchases"] = 1
            stats_update["$inc"]["stats.forever_revenue"] = total_revenue
        elif purchase_type == PurchaseType.PDF_DOWNLOAD:
            stats_update["$inc"]["stats.pdf_downloads"] = 1
            stats_update["$inc"]["stats.pdf_revenue"] = total_revenue

        db.online_books.update_one({"book_id": book_id}, stats_update)

        # Credit owner's earnings (80% revenue split - can be withdrawn to cash)
        owner_id = book.get("user_id")
        if owner_id and owner_id != user_id:  # Don't credit if buying own book
            owner_earnings_result = db.user_subscriptions.update_one(
                {"user_id": owner_id},
                {
                    "$inc": {"earnings_points": owner_reward},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                },
                upsert=False  # Don't create if doesn't exist
            )

            if owner_earnings_result.modified_count > 0:
                logger.info(
                    f"💰 Credited {owner_reward} earnings points to book owner {owner_id} "
                    f"(80% of {points_cost} points purchase)"
                )
            else:
                logger.warning(
                    f"⚠️ Failed to credit earnings to owner {owner_id} - subscription not found"
                )

        logger.info(
            f"📚 User {user_id} purchased {purchase_type} access to book {book_id} for {points_cost} points"
        )

        return PurchaseBookResponse(
            success=True,
            purchase_id=purchase_id,
            book_id=book_id,
            purchase_type=purchase_type,
            points_spent=points_cost,
            remaining_balance=user_balance - points_cost,
            access_expires_at=access_expires_at,
            timestamp=purchase_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to purchase book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to purchase book",
        )


@router.get("/{book_id}/access", response_model=BookAccessResponse)
async def check_book_access(
    book_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Check user's access to a book**

    Returns whether user has access, access type, expiry, and download permissions.

    **Authentication:** Required

    **Path Parameters:**
    - `book_id`: Book ID to check access

    **Returns:**
    - 200: Access status details
    - 404: Book not found
    """
    try:
        user_id = current_user["uid"]
        from datetime import datetime, timezone

        # Get book (DELETE_PROTECTION_FLOW: Check purchases even if book deleted)
        book = db.online_books.find_one({"book_id": book_id})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is unpublished (no access for buyers)
        is_published = book.get("community_config", {}).get("is_public", False)
        if not is_published and book.get("user_id") != user_id:
            # Book unpublished and user not owner
            return BookAccessResponse(
                has_access=False,
                access_type=None,
                expires_at=None,
                can_download_pdf=False,
                is_owner=False,
                purchase_details=None,
            )

        # Check if user is owner
        is_owner = book.get("user_id") == user_id
        if is_owner:
            return BookAccessResponse(
                has_access=True,
                access_type="owner",
                expires_at=None,
                can_download_pdf=True,
                is_owner=True,
                purchase_details=None,
            )

        # Check book visibility
        visibility = book.get("visibility")

        # Public books - free access
        if visibility == "public":
            return BookAccessResponse(
                has_access=True,
                access_type="public",
                expires_at=None,
                can_download_pdf=False,  # Need to purchase PDF separately
                is_owner=False,
                purchase_details=None,
            )

        # Point-based books - check purchases
        if visibility == "point_based":
            # Check for forever access
            forever_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.FOREVER,
                }
            )

            if forever_purchase:
                # Check if user also has PDF access
                pdf_purchase = db.book_purchases.find_one(
                    {
                        "user_id": user_id,
                        "book_id": book_id,
                        "purchase_type": PurchaseType.PDF_DOWNLOAD,
                    }
                )

                return BookAccessResponse(
                    has_access=True,
                    access_type="forever",
                    expires_at=None,
                    can_download_pdf=pdf_purchase is not None,
                    is_owner=False,
                    purchase_details={
                        "purchase_id": forever_purchase.get("purchase_id"),
                        "purchased_at": forever_purchase.get("purchased_at"),
                        "points_spent": forever_purchase.get("points_spent"),
                    },
                )

            # Check for active one-time access
            one_time_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.ONE_TIME,
                }
            )

            if one_time_purchase:
                expires_at = one_time_purchase.get("access_expires_at")
                now = datetime.now(timezone.utc)

                # Check if not expired
                if expires_at and expires_at > now:
                    return BookAccessResponse(
                        has_access=True,
                        access_type="one_time",
                        expires_at=expires_at,
                        can_download_pdf=False,
                        is_owner=False,
                        purchase_details={
                            "purchase_id": one_time_purchase.get("purchase_id"),
                            "purchased_at": one_time_purchase.get("purchased_at"),
                            "points_spent": one_time_purchase.get("points_spent"),
                        },
                    )

        # No access
        return BookAccessResponse(
            has_access=False,
            access_type=None,
            expires_at=None,
            can_download_pdf=False,
            is_owner=False,
            purchase_details=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to check book access: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check book access",
        )


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
            deleted_permissions = permission_manager.delete_guide_permissions(book_id)
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
    Create a new chapter in a book

    **Authentication:** Required (Owner only)

    **Request Body:**
    - title: Chapter title (1-200 chars) [REQUIRED]
    - slug: URL-friendly slug (auto-generated from title if not provided)
    - document_id: Document ID from documents collection (auto-created if not provided)
    - parent_id: Parent chapter ID (null for root chapters)
    - order_index: Display order (default: 0)
    - order: Alias for order_index (for backward compatibility)
    - is_published: Publish status (default: true)

    **Auto-Generation:**
    - If slug not provided: Generated from title (Vietnamese-safe)
    - If document_id not provided: Creates empty document automatically

    **Validation:**
    - Slug must be unique within book
    - Parent chapter must exist in same book (if provided)
    - Max depth: 3 levels (0, 1, 2)

    **Returns:**
    - 201: Chapter created successfully
    - 400: Max depth exceeded or validation error
    - 403: User is not the book owner
    - 404: Guide or parent chapter not found
    - 409: Slug already exists in book
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
                detail="Only book owner can create chapters",
            )

        # Auto-generate slug if not provided
        if not chapter_data.slug:
            import re
            import unicodedata

            # Convert title to slug: normalize, lowercase, replace spaces with hyphens
            slug = chapter_data.title.lower()
            # Normalize unicode characters (Vietnamese → ASCII)
            slug = (
                unicodedata.normalize("NFKD", slug)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            # Replace spaces and special chars with hyphens
            slug = re.sub(r"[^a-z0-9]+", "-", slug)
            # Remove leading/trailing hyphens
            slug = slug.strip("-")

            # Ensure uniqueness by appending number if needed
            original_slug = slug
            counter = 1
            while chapter_manager.slug_exists(book_id, slug):
                slug = f"{original_slug}-{counter}"
                counter += 1

            chapter_data.slug = slug
        else:
            # Check slug uniqueness within book if provided
            if chapter_manager.slug_exists(book_id, chapter_data.slug):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{chapter_data.slug}' already exists in this book",
                )

        # Verify parent exists if provided
        if chapter_data.parent_id:
            parent = chapter_manager.get_chapter(chapter_data.parent_id)

            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent chapter not found",
                )

            # Verify parent belongs to same book
            if parent["book_id"] != book_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Parent chapter must belong to the same book",
                )

        # Auto-create empty document if not provided
        if not chapter_data.document_id:
            document_id = document_manager.create_document(
                user_id=user_id,
                title=chapter_data.title,
                content_html="<p></p>",  # Empty content
                content_text="",
                source_type="created",
                document_type="doc",
            )
            chapter_data.document_id = document_id
            logger.info(
                f"✅ Auto-created empty document: {document_id} for chapter: {chapter_data.title}"
            )

        # Create chapter (depth is auto-calculated)
        chapter = chapter_manager.create_chapter(book_id, chapter_data)

        logger.info(
            f"✅ User {user_id} created chapter in book {book_id}: "
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
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    Get hierarchical tree structure of all chapters in a book

    **Authentication:** Optional (public access for published Community books)

    **Public Access:**
    - If book is published to Community (is_public=true): Returns chapter TOC
    - Chapter list includes is_preview_free flag
    - No authentication required

    **Authenticated Access:**
    - Owner: Full access, can see unpublished chapters
    - Shared users: Access based on permissions
    - Buyers: Access based on purchase

    **Query Parameters:**
    - include_unpublished: Include unpublished chapters (default: false)
      * Always true for book owner
      * Ignored for non-owners

    **Tree Structure:**
    - Max 3 levels: Level 0 (root), Level 1 (sub), Level 2 (sub-sub)
    - Ordered by order_index at each level
    - Unpublished chapters hidden for non-owners

    **Returns:**
    - 200: Chapter tree structure
    - 403: User doesn't have access to book
    - 404: Book not found
    """
    try:
        # Verify book exists
        book = book_manager.get_book(book_id)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check if book is public (published to Community)
        is_public = book.get("community_config", {}).get("is_public", False)

        # If no user and book not public, require authentication
        if not current_user and not is_public:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for this book",
            )

        # Determine access level
        is_owner = False
        has_access = is_public  # Public books are accessible by default

        if current_user:
            user_id = current_user["uid"]
            is_owner = book["user_id"] == user_id

            if is_owner:
                has_access = True
            elif not is_public:
                # Private book - check permissions
                has_permission = permission_manager.check_permission(
                    book_id=book_id, user_id=user_id
                )
                has_access = has_permission

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this book",
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
            f"📄 {'User ' + current_user['uid'] if current_user else 'Anonymous'} retrieved chapter tree for book {book_id}: {total} chapters"
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
    - Slug must be unique within book (if changed)
    - Max depth validation after parent change

    **Returns:**
    - 200: Chapter updated successfully
    - 400: Circular reference or max depth exceeded
    - 403: User is not the book owner
    - 404: Chapter not found
    - 409: Slug already exists in book
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
                detail="Only book owner can update chapters",
            )

        # Get existing chapter
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Verify chapter belongs to book
        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this book",
            )

        # Check slug uniqueness if changed
        if chapter_data.slug and chapter_data.slug != chapter["slug"]:
            if chapter_manager.slug_exists(book_id, chapter_data.slug):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Slug '{chapter_data.slug}' already exists in this book",
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


@router.patch(
    "/{book_id}/chapters/{chapter_id}/preview",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle chapter preview status",
)
async def toggle_chapter_preview(
    book_id: str,
    chapter_id: str,
    preview_data: TogglePreviewRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Toggle Free Preview Status for Chapter**

    Allows book owner to mark/unmark chapters as free preview on Community Books.
    Free preview chapters can be read without purchase on the preview page.

    **Authentication:** Required (Owner only)

    **Use Cases:**
    - Mark first chapter as free to attract readers
    - Unmark chapter to make it paid-only
    - Change preview strategy based on engagement

    **Path Parameters:**
    - `book_id`: Book ID
    - `chapter_id`: Chapter ID to toggle

    **Request Body:**
    - `is_preview_free`: true to allow free preview, false to require purchase

    **Returns:**
    - 200: Updated chapter with new preview status
    - 403: User is not book owner
    - 404: Book or chapter not found
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
                detail="Only book owner can toggle chapter preview status",
            )

        # Verify chapter belongs to book
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this book",
            )

        # Update preview status
        update_data = ChapterUpdate(is_preview_free=preview_data.is_preview_free)
        updated_chapter = chapter_manager.update_chapter(chapter_id, update_data)

        if not updated_chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update chapter",
            )

        action = "enabled" if preview_data.is_preview_free else "disabled"
        logger.info(
            f"👁️ User {user_id} {action} free preview for chapter {chapter_id} in book {book_id}"
        )

        return updated_chapter

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to toggle chapter preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle chapter preview",
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
    - 403: User is not the book owner
    - 404: Chapter not found
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
                detail="Only book owner can delete chapters",
            )

        # Get chapter to verify it exists
        chapter = chapter_manager.get_chapter(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Verify chapter belongs to book
        if chapter["book_id"] != book_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chapter does not belong to this book",
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


@router.patch(
    "/{book_id}/chapters/{chapter_id}/content",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update chapter content (inline or document-linked)"
)
async def update_chapter_content(
    book_id: str,
    chapter_id: str,
    content_data: ChapterContentUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Update chapter content (handles both inline and document-linked chapters)**

    **Authentication:** Required (Owner only)

    **Content Storage:**
    - **Inline chapters** (`content_source='inline'`): Updates `book_chapters.content_html`
    - **Document-linked chapters** (`content_source='document'`): Updates `documents.content_html`

    **Request Body:**
    - `content_html`: HTML content (required)
    - `content_json`: Optional JSON content (TipTap editor format)

    **Returns:**
    - 200: Content updated successfully
    - 403: User is not the book owner
    - 404: Chapter or book not found
    - 500: Update failed
    """
    try:
        user_id = current_user["uid"]

        # Verify book ownership
        book = db.online_books.find_one(
            {"book_id": book_id, "user_id": user_id, "is_deleted": False}
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Book not found or access denied"
            )

        # Update chapter content (handles both inline and document-linked)
        success = chapter_manager.update_chapter_content(
            chapter_id=chapter_id,
            content_html=content_data.content_html,
            content_json=content_data.content_json
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found or content not updated"
            )

        return {
            "success": True,
            "message": "Chapter content updated successfully",
            "chapter_id": chapter_id,
            "content_length": len(content_data.content_html)
        }

    except ValueError as e:
        logger.error(f"❌ Invalid chapter content update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update chapter content: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chapter content"
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
    - All chapter_ids must exist in the book
    - Validates max depth for each chapter after reordering
    - Prevents circular references

    **Returns:**
    - 200: Chapters reordered successfully
    - 400: Invalid chapter IDs, circular reference, or max depth exceeded
    - 403: User is not the book owner
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
                detail="Only book owner can reorder chapters",
            )

        # Reorder chapters
        updated_chapters = chapter_manager.reorder_chapters(
            book_id=book_id, updates=reorder_data.updates
        )

        logger.info(
            f"🔄 User {user_id} reordered {len(updated_chapters)} chapters in book {book_id}"
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
    Get public book with all chapters (NO AUTHENTICATION REQUIRED)

    **Use Case:** Homepage/TOC for public guides

    **Path Parameters:**
    - slug: Guide slug (URL-friendly identifier)

    **Returns:**
    - 200: Guide with chapters, SEO metadata, author info
    - 404: Book not found
    - 403: Guide is private (not accessible publicly)

    **Note:** Only public/unlisted guides are accessible
    """
    try:
        # Get book by slug
        book = book_manager.get_book_by_slug(slug)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check visibility - only public/unlisted guides accessible
        if book.get("visibility") == "private":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This book is private and cannot be accessed publicly",
            )

        # Get all chapters for this book (sorted by order)
        chapters = chapter_manager.list_chapters(book["book_id"])

        # Get author info (mock for now - implement user service later)
        author = PublicAuthorInfo(
            user_id=book["user_id"],
            display_name=book.get("author_name", "Unknown Author"),
            avatar_url=book.get("author_avatar"),
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
            total_views=book.get("stats", {}).get("total_views", 0),
            last_updated=book["updated_at"],
        )

        # SEO metadata
        base_url = "https://wordai.com"
        guide_url = f"{base_url}/g/{slug}"

        seo = SEOMetadata(
            title=f"{book['title']} - Complete Guide",
            description=book.get("description", f"Learn about {book['title']}"),
            og_image=book.get("cover_image_url"),
            og_url=book.get("custom_domain", guide_url),
            twitter_card="summary_large_image",
        )

        # Response
        response = PublicBookResponse(
            book_id=book["book_id"],
            title=book["title"],
            slug=book["slug"],
            description=book.get("description"),
            visibility=book["visibility"],
            custom_domain=book.get("custom_domain"),
            is_indexed=book.get("is_indexed", True),
            cover_image_url=book.get("cover_image_url"),
            logo_url=book.get("logo_url"),
            favicon_url=book.get("favicon_url"),
            author=author,
            chapters=chapter_summaries,
            stats=stats,
            seo=seo,
            branding=book.get("branding"),
            created_at=book["created_at"],
            updated_at=book["updated_at"],
        )

        logger.info(f"📖 Public book accessed: {slug} ({len(chapters)} chapters)")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get public book: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get public book",
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

    **Note:** Includes book info + prev/next navigation + SEO metadata
    """
    try:
        # Get book by slug
        book = book_manager.get_book_by_slug(guide_slug)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check visibility
        if book.get("visibility") == "private":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This book is private and cannot be accessed publicly",
            )

        # Get chapter by slug
        chapter = chapter_manager.get_chapter_by_slug(book["book_id"], chapter_slug)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found",
            )

        # Get all chapters for navigation
        all_chapters = chapter_manager.list_chapters(book["book_id"])
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
            book_id=book["book_id"],
            title=book["title"],
            slug=book["slug"],
            logo_url=book.get("logo_url"),
            custom_domain=book.get("custom_domain"),
        )

        # SEO metadata
        base_url = book.get("custom_domain") or "https://wordai.com"
        chapter_url = f"{base_url}/g/{guide_slug}/{chapter_slug}"

        seo = SEOMetadata(
            title=f"{chapter['title']} - {book['title']}",
            description=chapter.get("description", f"Read {chapter['title']}"),
            og_image=book.get("cover_image_url"),
            og_url=chapter_url,
            twitter_card="summary_large_image",
        )

        # Response
        response = PublicChapterResponse(
            chapter_id=chapter["chapter_id"],
            book_id=book["book_id"],
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
    Track book/chapter view analytics (NO AUTHENTICATION REQUIRED)

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
    - 404: Book not found

    **Note:** Rate limited to 10 requests/minute per IP
    """
    try:
        # Get book by slug
        book = book_manager.get_book_by_slug(slug)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # TODO: Implement analytics tracking
        # For now, just increment view count in book stats
        # In production, store in separate guide_views collection

        # Mock view tracking
        view_id = f"view_{book['book_id']}_{view_data.session_id or 'anon'}"
        guide_views = book.get("stats", {}).get("total_views", 0) + 1
        chapter_views = None

        if view_data.chapter_slug:
            chapter = chapter_manager.get_chapter_by_slug(
                book["book_id"], view_data.chapter_slug
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
async def get_book_by_domain(domain: str):
    """
    Get book by custom domain (NO AUTHENTICATION REQUIRED)

    **Use Case:** Next.js middleware uses this to route custom domain requests

    **Path Parameters:**
    - domain: Custom domain (e.g., "python.example.com")

    **Returns:**
    - 200: Guide info for domain
    - 404: No book found for this domain

    **Example Flow:**
    1. Request comes to python.example.com
    2. Middleware calls /api/v1/guides/by-domain/python.example.com
    3. Gets book slug
    4. Rewrites to /g/{slug}
    """
    try:
        # Get book by custom domain
        book = book_manager.get_book_by_domain(domain)

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No book found for domain '{domain}'",
            )

        response = BookDomainResponse(
            book_id=book["book_id"],
            slug=book["slug"],
            title=book["title"],
            custom_domain=book["custom_domain"],
            visibility=book["visibility"],
            is_active=book.get("is_active", True),
        )

        logger.info(f"🌐 Domain lookup: {domain} → {book['slug']}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get book by domain: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get book by domain",
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
    1. Provide `authors` array (e.g., ["@michael"]) or legacy `author_id` (will be converted)
    2. If author exists: Use existing author (must be owned by user)
    3. If author NOT exists: Auto-create with data from `new_authors` or auto-generate

    **Requirements:**
    - User must be the book owner
    - Either `authors` (array) or `author_id` (string) is required
    - Sets visibility (public or point_based) and access_config
    - Sets community_config.is_public = true

    **Request Body:**
    - authors: Array of author IDs (e.g., ["@john_doe"]) [RECOMMENDED]
    - author_id: (DEPRECATED) Single author ID - use `authors` instead
    - new_authors: Optional dict with author data for new authors
      * Format: {"@new_author": {"name": "...", "bio": "...", "avatar_url": "..."}}
    - visibility: "public" (free) or "point_based" (paid)
    - access_config: Required if visibility=point_based
    - category, tags, difficulty_level, short_description, cover_image_url
    """
    user_id = user["uid"]

    try:
        # Verify ownership
        book = book_manager.get_book(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Handle Author: Use existing or auto-create new
        # After backward compatibility fix, authors is always a list
        author_id = publish_data.authors[0]  # Primary author

        # Check if author already exists
        existing_author = author_manager.get_author(author_id)

        if existing_author:
            # Use existing author - verify ownership
            if existing_author["user_id"] != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't own this author profile",
                )
            logger.info(f"📚 Using existing author: {author_id}")

        else:
            # Auto-create new author
            # Check if author data provided in new_authors
            new_author_data = publish_data.new_authors.get(author_id) if publish_data.new_authors else None

            if new_author_data:
                # Use provided author data
                author_name = new_author_data.get("name")
                author_bio = new_author_data.get("bio", "")
                author_avatar_url = new_author_data.get("avatar_url", "")
            else:
                # Auto-generate author data
                # Fallback: use user's display name or extract from email
                author_name = user.get("name") or user.get("email", "").split("@")[0]
                # Clean up the @username to make a nice display name
                if author_id.startswith("@"):
                    fallback_name = (
                        author_id[1:].replace("_", " ").replace("-", " ").title()
                    )
                    author_name = fallback_name
                author_bio = ""
                author_avatar_url = ""

            author_data = {
                "author_id": author_id,
                "name": author_name,
                "bio": author_bio,
                "avatar_url": author_avatar_url,
                "social_links": {},
            }

            try:
                created_author = author_manager.create_author(user_id, author_data)
                if not created_author:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Failed to create author",
                    )
                logger.info(f"✅ Auto-created new author: {author_id} ({author_name})")
            except Exception as e:
                logger.error(f"❌ Failed to create author: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create author: {str(e)}",
                )

        # Publish to community with author
        updated_book = book_manager.publish_to_community(
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
        book = book_manager.get_book(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Remove book from author's list (if has author)
        if book.get("author_id"):
            author_manager.remove_book_from_author(book["author_id"], book_id)

        # Unpublish from community
        updated_book = book_manager.unpublish_from_community(
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
        books, total = book_manager.list_community_books(
            category=category,
            tags=tags_list,
            difficulty=difficulty,
            sort_by=sort_by,
            skip=skip,
            limit=limit,
        )

        # Transform books to CommunityBookItem format
        items = []
        for book in books:
            community_config = book.get("community_config", {})
            access_config = book.get("access_config") or {}  # Handle None case

            # Get author info (ensure object format)
            authors_list = book.get("authors", [])
            primary_author_id = authors_list[0] if authors_list else None
            author_obj = None

            if primary_author_id:
                # Try to get from book_authors collection
                author_doc = db.book_authors.find_one({"author_id": primary_author_id})
                if author_doc:
                    author_obj = {
                        "author_id": author_doc["author_id"],
                        "name": author_doc["name"],
                        "avatar_url": author_doc.get("avatar_url"),
                    }
                else:
                    # Fallback: use author_id as name
                    author_obj = {
                        "author_id": primary_author_id,
                        "name": primary_author_id.replace("@", "")
                        .replace("_", " ")
                        .title(),
                    }

            item = CommunityBookItem(
                book_id=book.get("book_id"),
                title=book.get("title"),
                slug=book.get("slug"),
                short_description=community_config.get("short_description"),
                cover_image_url=book.get("cover_image_url"),
                category=community_config.get("category", "uncategorized"),
                tags=community_config.get("tags", []),  # Always array
                difficulty_level=community_config.get("difficulty_level", "beginner"),
                forever_view_points=access_config.get("forever_view_points", 0),
                total_views=community_config.get("total_views", 0),
                total_purchases=community_config.get("total_purchases", 0),
                average_rating=community_config.get("average_rating", 0.0),
                rating_count=community_config.get("rating_count", 0),
                author=author_obj,  # Object with author_id, name, avatar_url
                published_at=community_config.get("published_at"),
            )
            items.append(item)

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


@router.get(
    "/{book_id}/preview",
    response_model=BookPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get book preview (public, no auth required)",
)
async def get_book_preview(
    book_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    **Book Preview Page (Public Endpoint)**

    Returns full book information for preview page including:
    - Book details (title, description, cover, author)
    - Table of contents (chapter list)
    - Free preview chapters
    - Purchase options
    - Stats and ratings

    **No authentication required** - Anyone can view preview.
    If user is authenticated, also returns their purchase status.

    **Data Consistency Guarantees:**
    - `tags`: Always array (never null)
    - `author`: Always object with user_id and display_name
    - `stats`: Always object with default 0 values
    - `access_config`: Null for free books, object for paid books

    **Path Parameters:**
    - `book_id`: Book ID to preview

    **Returns:**
    - 200: Book preview data
    - 404: Book not found or not published to Community
    """
    try:
        # Get book (must be published to Community)
        book = db.online_books.find_one({
            "book_id": book_id,
            "community_config.is_public": True,
        })

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or not published to Community",
            )

        # Get author info (primary author)
        authors_list = book.get("authors", [])
        primary_author_id = authors_list[0] if authors_list else None

        if primary_author_id:
            # Get author details from authors collection
            author_doc = db.book_authors.find_one({"author_id": primary_author_id})
            if author_doc:
                author = PreviewAuthor(
                    author_id=author_doc["author_id"],
                    name=author_doc["name"],
                    avatar_url=author_doc.get("avatar_url"),
                    bio=author_doc.get("bio"),
                )
            else:
                # Fallback if author not found
                author = PreviewAuthor(
                    author_id=primary_author_id,
                    name=primary_author_id.replace("@", "").replace("_", " ").title(),
                )
        else:
            # No author - use book owner
            author = PreviewAuthor(
                author_id=f"@{book.get('user_id', 'unknown')}",
                name="Unknown Author",
            )

        # Get chapters (table of contents)
        chapters_cursor = db.book_chapters.find(
            {"book_id": book_id, "is_published": True}
        ).sort("order_index", 1)

        chapters = []
        for chapter in chapters_cursor:
            chapters.append(
                PreviewChapterItem(
                    chapter_id=chapter["chapter_id"],
                    title=chapter["title"],
                    slug=chapter["slug"],
                    order_index=chapter.get("order_index", 0),
                    depth=chapter.get("depth", 0),
                    is_preview_free=chapter.get("is_preview_free", False),
                )
            )

        # Get community config and stats
        community_config = book.get("community_config", {})
        stats_data = book.get("stats", {})

        # Build stats object (guaranteed non-null with defaults)
        stats = PreviewStats(
            total_views=community_config.get("total_views", 0),
            total_purchases=stats_data.get("forever_purchases", 0)
            + stats_data.get("one_time_purchases", 0)
            + stats_data.get("pdf_downloads", 0),
            forever_purchases=stats_data.get("forever_purchases", 0),
            one_time_purchases=stats_data.get("one_time_purchases", 0),
            pdf_downloads=stats_data.get("pdf_downloads", 0),
            average_rating=community_config.get("average_rating", 0.0),
            rating_count=community_config.get("rating_count", 0),
        )

        # Get access config (null for free books)
        access_config = book.get("access_config")
        if access_config:
            access_config = AccessConfig(**access_config)

        # Check user's access if authenticated
        user_access = None
        if current_user:
            user_id = current_user["uid"]
            is_owner = book.get("user_id") == user_id

            if is_owner:
                user_access = {
                    "has_access": True,
                    "access_type": "owner",
                    "expires_at": None,
                }
            else:
                # Check purchases
                forever_purchase = db.book_purchases.find_one({
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.FOREVER.value,
                })

                if forever_purchase:
                    user_access = {
                        "has_access": True,
                        "access_type": "forever",
                        "expires_at": None,
                    }
                else:
                    # Check one-time purchase
                    one_time_purchase = db.book_purchases.find_one({
                        "user_id": user_id,
                        "book_id": book_id,
                        "purchase_type": PurchaseType.ONE_TIME.value,
                    })

                    if one_time_purchase:
                        expires_at = one_time_purchase.get("access_expires_at")
                        is_expired = expires_at and expires_at < datetime.now(timezone.utc)

                        user_access = {
                            "has_access": not is_expired,
                            "access_type": "one_time",
                            "expires_at": expires_at.isoformat() if expires_at else None,
                        }

        # Build response
        response = BookPreviewResponse(
            book_id=book["book_id"],
            title=book["title"],
            slug=book["slug"],
            description=book.get("description"),
            cover_image_url=book.get("cover_image_url"),
            icon=book.get("icon"),
            color=book.get("color"),
            author=author,
            authors=authors_list,
            category=community_config.get("category"),
            tags=community_config.get("tags", []),  # Always array
            difficulty_level=community_config.get("difficulty_level"),
            access_config=access_config,
            chapters=chapters,
            stats=stats,
            published_at=community_config.get("published_at"),
            updated_at=book.get("updated_at"),
            user_access=user_access,
        )

        logger.info(
            f"📖 Preview page viewed for book {book_id} by user {current_user['uid'] if current_user else 'anonymous'}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get book preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get book preview",
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
        book = book_manager.get_book(book_id, user_id)
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
    summary="Get chapter content (public for preview chapters, auth for paid)",
)
async def get_chapter_with_content(
    book_id: str,
    chapter_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    **Get chapter content with access control**

    Returns chapter content based on access permissions:
    - **Free preview chapters** (`is_preview_free: true`): Public access, no auth required
    - **Paid books**: Requires purchase or ownership
    - **Private books**: Owner only

    **Access Logic:**
    1. If `is_preview_free: true` → Allow anyone (even anonymous)
    2. If user is owner → Full access
    3. If user has purchased book → Full access
    4. If book is free (0 points) → Allow authenticated users
    5. Otherwise → 403 Forbidden

    **Authentication:** Optional (required for non-preview chapters)
    """
    try:
        # Get chapter first to check if it's a preview chapter
        chapter = chapter_manager.get_chapter_with_content(chapter_id)

        if not chapter or chapter.get("book_id") != book_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter not found"
            )

        # Check if this is a free preview chapter
        is_preview_free = chapter.get("is_preview_free", False)

        if is_preview_free:
            # Free preview - allow anonymous access
            logger.info(
                f"📖 Preview chapter accessed: {chapter_id} (anonymous: {current_user is None})"
            )
            return ChapterResponse(**chapter)

        # For non-preview chapters, authentication is required
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this chapter",
            )

        user_id = current_user["uid"]

        # Get book to check access permissions
        book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found",
            )

        # Check access permissions
        is_owner = book.get("user_id") == user_id

        if is_owner:
            # Owner has full access
            logger.info(f"📄 Owner {user_id} accessed chapter: {chapter_id}")
            return ChapterResponse(**chapter)

        # Check if book is public/free
        visibility = book.get("visibility", "private")
        community_config = book.get("community_config", {})
        is_published = community_config.get("is_public", False)

        if visibility == "public" or (is_published and visibility == "point_based"):
            # Check if it's a free book (0 points for all access types)
            access_config = book.get("access_config", {})
            one_time_points = access_config.get("one_time_view_points", 0)
            forever_points = access_config.get("forever_view_points", 0)

            if one_time_points == 0 and forever_points == 0:
                # Free book - allow all authenticated users
                logger.info(f"📖 Free book accessed by {user_id}: chapter {chapter_id}")
                return ChapterResponse(**chapter)

        # Check if user has purchased access
        # Check forever access
        forever_purchase = db.book_purchases.find_one({
            "user_id": user_id,
            "book_id": book_id,
            "purchase_type": PurchaseType.FOREVER.value,
        })

        if forever_purchase:
            logger.info(f"📄 User {user_id} accessed chapter (forever access): {chapter_id}")
            return ChapterResponse(**chapter)

        # Check one-time access (valid for 7 days)
        one_time_purchase = db.book_purchases.find_one({
            "user_id": user_id,
            "book_id": book_id,
            "purchase_type": PurchaseType.ONE_TIME.value,
        })

        if one_time_purchase:
            expires_at = one_time_purchase.get("access_expires_at")
            if expires_at and expires_at > datetime.now(timezone.utc):
                logger.info(f"📄 User {user_id} accessed chapter (one-time access): {chapter_id}")
                return ChapterResponse(**chapter)

        # No access - user needs to purchase
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Purchase required to access this chapter",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter content: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chapter content",
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


@router.delete("/{book_id}/delete-image/{image_type}", tags=["Book Images"])
async def delete_book_image(
    book_id: str,
    image_type: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Delete book image (cover, logo, or favicon)**

    This endpoint removes the image URL from the book and optionally deletes the file from R2 storage.

    **Supported Image Types:**
    - `cover`: Remove cover_image_url
    - `logo`: Remove logo_url
    - `favicon`: Remove favicon_url

    **Path Parameters:**
    - `book_id`: Book ID (required)
    - `image_type`: Type of image to delete: "cover" | "logo" | "favicon" (required)

    **What happens:**
    1. Verifies user owns the book
    2. Clears the image URL field in database (cover_image_url, logo_url, or favicon_url)
    3. Optionally deletes the file from R2 storage (if URL is from our CDN)

    **Returns:**
    - Success message with deleted image type
    - Updated book with null image URL

    **Use Cases:**
    - User wants to change the image (delete old one first)
    - User wants to remove the image completely
    - Cleaning up unused images

    **Example:**
    ```javascript
    // Delete cover image
    await fetch('/api/v1/books/{book_id}/delete-image/cover', {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer <token>' }
    })
    ```
    """
    try:
        user_id = user["uid"]

        # Validate image_type
        valid_types = ["cover", "logo", "favicon"]
        if image_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image_type. Allowed: {', '.join(valid_types)}",
            )

        logger.info(f"🗑️ User {user_id} deleting {image_type} for book {book_id}")

        # Get book and verify ownership
        book = book_manager.get_book(book_id, user_id)
        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or you don't have access",
            )

        # Map image_type to field name
        field_map = {
            "cover": "cover_image_url",
            "logo": "logo_url",
            "favicon": "favicon_url",
        }
        field_name = field_map[image_type]

        # Get current image URL
        current_url = book.get(field_name)

        if not current_url:
            logger.info(f"ℹ️ No {image_type} to delete for book {book_id}")
            return {
                "success": True,
                "message": f"No {image_type} image to delete",
                "image_type": image_type,
                "book_id": book_id,
            }

        # Update book to remove image URL
        update_data = {field_name: None}
        updated_book = book_manager.update_book(book_id, user_id, update_data)

        if not updated_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete image",
            )

        # TODO: Optionally delete file from R2 storage
        # For now, we just clear the URL in database
        # File will remain in R2 but won't be referenced
        # Can implement cleanup job later to remove unreferenced files

        logger.info(f"✅ Deleted {image_type} for book {book_id}: {current_url}")

        return {
            "success": True,
            "message": f"Successfully deleted {image_type} image",
            "image_type": image_type,
            "book_id": book_id,
            "deleted_url": current_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete image: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete image: {str(e)}",
        )


# ==============================================================================
# COMMUNITY MARKETPLACE - DISCOVERY & STATS APIS
# ==============================================================================


@router.get("/community/tags", tags=["Community Books"])
async def get_popular_tags(limit: int = Query(20, ge=1, le=100)):
    """
    **Get popular tags from community books**

    Returns list of most used tags in community marketplace.

    **Query Parameters:**
    - `limit`: Number of tags to return (default: 20, max: 100)

    **Returns:**
    ```json
    {
      "tags": [
        {"tag": "python", "count": 150},
        {"tag": "javascript", "count": 120},
        {"tag": "tutorial", "count": 95}
      ],
      "total": 50
    }
    ```

    **Use Case**: Display popular tags for filtering and discovery
    """
    try:
        # Aggregate tags from all published books
        pipeline = [
            {"$match": {"community_config.is_public": True}},
            {"$unwind": "$community_config.tags"},
            {
                "$group": {
                    "_id": "$community_config.tags",
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": limit},
            {"$project": {"tag": "$_id", "count": 1, "_id": 0}},
        ]

        tags = list(db.online_books.aggregate(pipeline))
        total = len(tags)

        logger.info(f"📊 Retrieved {total} popular tags")
        return {"tags": tags, "total": total}

    except Exception as e:
        logger.error(f"❌ Failed to get popular tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve popular tags",
        )


@router.get("/community/top", tags=["Community Books"])
async def get_top_books(
    period: str = Query("month", description="week | month | all"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    **Get top performing books**

    Returns top books by views and purchases in specified period.

    **Query Parameters:**
    - `period`: Time period - "week" | "month" | "all" (default: month)
    - `limit`: Number of books to return (default: 10, max: 50)

    **Returns:**
    ```json
    {
      "books": [
        {
          "book_id": "...",
          "title": "...",
          "slug": "...",
          "author_id": "@john_doe",
          "author_name": "John Doe",
          "cover_image_url": "...",
          "total_views": 1500,
          "total_purchases": 250,
          "average_rating": 4.8,
          "published_at": "..."
        }
      ],
      "period": "month",
      "total": 10
    }
    ```
    """
    try:
        # Build match query based on period
        from datetime import datetime, timedelta

        match_query = {"community_config.is_public": True}

        if period == "week":
            week_ago = datetime.utcnow() - timedelta(days=7)
            match_query["community_config.published_at"] = {"$gte": week_ago}
        elif period == "month":
            month_ago = datetime.utcnow() - timedelta(days=30)
            match_query["community_config.published_at"] = {"$gte": month_ago}
        # "all" - no time filter

        pipeline = [
            {"$match": match_query},
            {
                "$addFields": {
                    "score": {
                        "$add": [
                            "$community_config.total_views",
                            {"$multiply": ["$community_config.total_purchases", 5]},
                        ]
                    }
                }
            },
            {"$sort": {"score": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "book_id": {"$toString": "$_id"},
                    "title": 1,
                    "slug": 1,
                    "author_id": 1,
                    "author_name": "$community_config.author_name",
                    "cover_image_url": "$community_config.cover_image_url",
                    "total_views": "$community_config.total_views",
                    "total_purchases": "$community_config.total_purchases",
                    "average_rating": "$community_config.average_rating",
                    "published_at": "$community_config.published_at",
                    "_id": 0,
                }
            },
        ]

        books = list(db.online_books.aggregate(pipeline))

        logger.info(f"📈 Retrieved {len(books)} top books for period: {period}")
        return {"books": books, "period": period, "total": len(books)}

    except Exception as e:
        logger.error(f"❌ Failed to get top books: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve top books",
        )


@router.get("/community/top-authors", tags=["Community Books"])
async def get_top_authors(
    period: str = Query("month", description="week | month | all"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    **Get top performing authors**

    Returns top authors by book views and revenue in specified period.

    **Query Parameters:**
    - `period`: Time period - "week" | "month" | "all" (default: month)
    - `limit`: Number of authors to return (default: 10, max: 50)

    **Returns:**
    ```json
    {
      "authors": [
        {
          "author_id": "@john_doe",
          "name": "John Doe",
          "avatar_url": "...",
          "total_books": 5,
          "total_followers": 120,
          "total_revenue_points": 45000,
          "average_rating": 4.7
        }
      ],
      "period": "month",
      "total": 10
    }
    ```
    """
    try:
        from datetime import datetime, timedelta

        # Build match query based on period
        match_query = {}

        if period == "week":
            week_ago = datetime.utcnow() - timedelta(days=7)
            match_query["created_at"] = {"$gte": week_ago}
        elif period == "month":
            month_ago = datetime.utcnow() - timedelta(days=30)
            match_query["created_at"] = {"$gte": month_ago}
        # "all" - no time filter

        # Get authors sorted by total_books and total_revenue_points
        authors_cursor = (
            db.authors.find(match_query)
            .sort([("total_books", -1), ("total_revenue_points", -1)])
            .limit(limit)
        )

        authors = []
        for author in authors_cursor:
            authors.append(
                {
                    "author_id": author["author_id"],
                    "name": author["name"],
                    "avatar_url": author.get("avatar_url"),
                    "total_books": author.get("total_books", 0),
                    "total_followers": author.get("total_followers", 0),
                    "total_revenue_points": author.get("total_revenue_points", 0),
                    "average_rating": author.get("average_rating", 0.0),
                }
            )

        logger.info(f"🏆 Retrieved {len(authors)} top authors for period: {period}")
        return {"authors": authors, "period": period, "total": len(authors)}

    except Exception as e:
        logger.error(f"❌ Failed to get top authors: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve top authors",
        )


# ============================================================================
# DOCUMENT TO CHAPTER CONVERSION
# ============================================================================


@router.post(
    "/documents/{document_id}/convert-to-chapter",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convert document to book chapter"
)
async def convert_document_to_chapter(
    document_id: str,
    request_data: ConvertDocumentToChapterRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Convert an existing document to a chapter in a book**

    **Authentication:** Required (must own both document and book)

    **Content Modes:**
    - **Copy mode** (`copy_content=true`): Creates inline chapter with copied content
      - Content duplicated from document to chapter
      - Chapter becomes independent (editing chapter won't affect document)
      - Document remains unchanged

    - **Link mode** (`copy_content=false`): Creates linked chapter
      - Chapter references original document
      - Editing chapter updates the original document
      - Document content not duplicated

    **Request Body:**
    - `book_id`: Target book ID (required)
    - `title`: Chapter title (optional, uses document name if not provided)
    - `order_index`: Position in chapter list (default: 0)
    - `parent_id`: Parent chapter for nesting (optional)
    - `copy_content`: Copy content vs link to document (default: true)

    **Returns:**
    - 201: Chapter created successfully
    - 400: Invalid request or document/book not found
    - 403: User doesn't own document or book
    - 500: Conversion failed
    """
    try:
        user_id = current_user["uid"]

        # Convert document to chapter
        chapter = chapter_manager.convert_document_to_chapter(
            document_id=document_id,
            book_id=request_data.book_id,
            user_id=user_id,
            title=request_data.title,
            order_index=request_data.order_index,
            parent_id=request_data.parent_id,
            copy_content=request_data.copy_content,
        )

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to convert document to chapter"
            )

        logger.info(
            f"✅ Converted document {document_id} to chapter {chapter['chapter_id']} "
            f"in book {request_data.book_id} (mode: {'copy' if request_data.copy_content else 'link'})"
        )

        return ChapterResponse(**chapter)

    except ValueError as e:
        logger.error(f"❌ Invalid document conversion: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to convert document to chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert document to chapter"
        )
