"""
Online Book Public & Community API Routes
Handles public access, community marketplace, and discovery features.

PHASE 5: Public View API (No Auth Required)
- Public book/chapter viewing
- Custom domain routing
- View tracking analytics

PHASE 6: Community Books & Document Integration
- Publish/unpublish to community
- Community marketplace browsing
- Book preview pages
- Document to chapter conversion
- Image upload (covers, logos, favicons)
- Discovery APIs (tags, top books, top authors)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone, timedelta

# Authentication
from src.middleware.firebase_auth import get_current_user, get_current_user_optional

# Models
from src.models.book_models import (
    BookResponse,
    # Community & Discovery
    CommunityPublishRequest,
    CommunityBookItem,
    CommunityBooksResponse,
    ChapterFromDocumentRequest,
    # Image Upload
    BookImageUploadRequest,
    # Book Preview
    BookPreviewResponse,
    PreviewAuthor,
    PreviewChapterItem,
    PreviewStats,
    # Purchases
    PurchaseType,
)
from src.models.book_chapter_models import (
    ConvertDocumentToChapterRequest,
    ChapterResponse,
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
from src.services.author_manager import AuthorManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger("chatbot")

router = APIRouter(prefix="/api/v1/books", tags=["Online Books Public & Community"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize managers with DB
book_manager = UserBookManager(db)
chapter_manager = GuideBookBookChapterManager(db)
author_manager = AuthorManager(db)


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
    2. Middleware calls /api/v1/books/by-domain/python.example.com
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
            new_author_data = (
                publish_data.new_authors.get(author_id)
                if publish_data.new_authors
                else None
            )

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

        # Remove book from author's list (if has authors)
        authors_list = book.get("authors", [])
        if not authors_list and book.get("author_id"):
            # Fallback to legacy author_id field
            authors_list = [book.get("author_id")]

        for author_id in authors_list:
            author_manager.remove_book_from_author(author_id, book_id)

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

    **Returns books with slug field for SEO-friendly URLs**
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

            # Get 2 most recent chapters
            recent_chapters = []
            chapters = list(
                db.book_chapters.find(
                    {"book_id": book.get("book_id")},
                    {
                        "chapter_id": 1,
                        "title": 1,
                        "slug": 1,
                        "order_index": 1,
                        "created_at": 1,
                        "_id": 0,
                    },
                )
                .sort([("created_at", -1), ("order_index", -1)])
                .limit(2)
            )
            for chapter in chapters:
                recent_chapters.append(
                    {
                        "chapter_id": chapter["chapter_id"],
                        "title": chapter["title"],
                        "slug": chapter["slug"],
                        "order_index": chapter.get("order_index", 0),
                        "created_at": chapter.get("created_at"),
                    }
                )

            item = CommunityBookItem(
                book_id=book.get("book_id"),
                title=book.get("title"),
                slug=book.get("slug"),  # ✅ SLUG INCLUDED
                short_description=community_config.get("short_description"),
                cover_image_url=community_config.get("cover_image_url")
                or book.get("cover_image_url"),
                category=community_config.get("category", "uncategorized"),
                tags=community_config.get("tags", []),  # Always array
                difficulty_level=community_config.get("difficulty_level", "beginner"),
                forever_view_points=access_config.get("forever_view_points", 0),
                total_views=community_config.get("total_views", 0),
                total_purchases=community_config.get("total_purchases", 0),
                average_rating=community_config.get("average_rating", 0.0),
                rating_count=community_config.get("rating_count", 0),
                author=author_obj,  # Object with author_id, name, avatar_url
                recent_chapters=recent_chapters,  # 2 most recent chapters
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


def _build_book_preview_response(
    book: Dict[str, Any], current_user: Optional[Dict[str, Any]]
) -> BookPreviewResponse:
    """Helper to build book preview response from book document"""
    book_id = book["book_id"]

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
        total_saves=community_config.get("total_saves", 0),
        average_rating=community_config.get("average_rating", 0.0),
        rating_count=community_config.get("rating_count", 0),
    )

    # Get access config (null for free books)
    access_config = book.get("access_config")
    if access_config:
        from src.models.book_models import AccessConfig

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
            forever_purchase = db.book_purchases.find_one(
                {
                    "user_id": user_id,
                    "book_id": book_id,
                    "purchase_type": PurchaseType.FOREVER.value,
                }
            )

            if forever_purchase:
                user_access = {
                    "has_access": True,
                    "access_type": "forever",
                    "expires_at": None,
                }
            else:
                # Check one-time purchase
                one_time_purchase = db.book_purchases.find_one(
                    {
                        "user_id": user_id,
                        "book_id": book_id,
                        "purchase_type": PurchaseType.ONE_TIME.value,
                    }
                )

                if one_time_purchase:
                    expires_at = one_time_purchase.get("access_expires_at")
                    # Ensure expires_at is timezone-aware for comparison
                    if expires_at and expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    is_expired = expires_at and expires_at < datetime.now(timezone.utc)

                    user_access = {
                        "has_access": not is_expired,
                        "access_type": "one_time",
                        "expires_at": (expires_at.isoformat() if expires_at else None),
                    }

    # Build response
    community_config = book.get("community_config", {})
    return BookPreviewResponse(
        book_id=book["book_id"],
        title=book["title"],
        slug=book["slug"],  # ✅ SLUG INCLUDED
        description=book.get("description"),
        cover_image_url=community_config.get("cover_image_url")
        or book.get("cover_image_url"),
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

    **Path Parameters:**
    - `book_id`: Book ID to preview

    **Returns:**
    - 200: Book preview data (includes slug for SEO)
    - 404: Book not found or not published to Community
    """
    try:
        # Get book (must be published to Community)
        book = db.online_books.find_one(
            {
                "book_id": book_id,
                "community_config.is_public": True,
            }
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Book not found or not published to Community",
            )

        response = _build_book_preview_response(book, current_user)

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


@router.get(
    "/slug/{slug}/preview",
    response_model=BookPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get book preview by slug (public, no auth required)",
)
async def get_book_preview_by_slug(
    slug: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
):
    """
    **Book Preview Page - Slug-based URL (Public Endpoint)**

    Same as /{book_id}/preview but uses slug instead of book_id.
    Enables SEO-friendly URLs like: /books/slug/word-ai-user-manual/preview

    **URL Structure:**
    - Frontend: https://wordai.pro/online-books?view=book-preview&bookSlug=word-ai-user-manual
    - API: https://ai.wordai.pro/api/v1/books/slug/word-ai-user-manual/preview

    Returns full book information for preview page including:
    - Book details (title, description, cover, author)
    - Table of contents (chapter list with slugs)
    - Free preview chapters
    - Purchase options
    - Stats and ratings

    **No authentication required** - Anyone can view preview.
    If user is authenticated, also returns their purchase status.

    **Path Parameters:**
    - `slug`: Book slug (e.g., "word-ai-user-manual")

    **Returns:**
    - 200: Book preview data (all chapters include slug)
    - 404: Book not found or not published to Community
    """
    try:
        # Find book by slug (must be published to Community)
        book = db.online_books.find_one(
            {
                "slug": slug,
                "community_config.is_public": True,
            }
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book with slug '{slug}' not found or not published to Community",
            )

        response = _build_book_preview_response(book, current_user)

        logger.info(
            f"📖 Preview page (slug) viewed for book '{slug}' by user {current_user['uid'] if current_user else 'anonymous'}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get book preview by slug: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get book preview",
        )


# Continue in next part due to length...


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


# ==============================================================================
# VIEW TRACKING HELPER
# ==============================================================================


def track_book_view(book_id: str, user_id: Optional[str], browser_id: Optional[str]):
    """
    Track book view for community books (auto-increment total_views)

    Rules:
    - 1 view per book per day per unique user/browser
    - Authenticated user: tracked by user_id
    - Anonymous user: tracked by browser_id (from frontend)
    - Only for community books (community_config.is_public = true)

    Args:
        book_id: Book ID to track
        user_id: Firebase user ID (if authenticated)
        browser_id: Browser fingerprint ID (if anonymous)

    Returns:
        bool: True if view was counted, False if already viewed today
    """
    try:
        # Must have either user_id or browser_id
        if not user_id and not browser_id:
            return False

        # Check if book is community book
        book = db.online_books.find_one(
            {"book_id": book_id, "community_config.is_public": True}
        )
        if not book:
            return False  # Not a community book, don't track

        # Create unique viewer identifier
        viewer_id = user_id if user_id else f"browser_{browser_id}"

        # Get today's date range (00:00:00 to 23:59:59 UTC)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end = today_start + timedelta(days=1)

        # Check if already viewed today
        existing_view = db.book_view_sessions.find_one(
            {
                "book_id": book_id,
                "viewer_id": viewer_id,
                "viewed_at": {"$gte": today_start, "$lt": today_end},
            }
        )

        if existing_view:
            # Already viewed today - don't count
            return False

        # First view today - record it
        db.book_view_sessions.insert_one(
            {
                "book_id": book_id,
                "viewer_id": viewer_id,
                "user_id": user_id,  # Store for analytics (can be None)
                "browser_id": browser_id,  # Store for analytics (can be None)
                "viewed_at": datetime.now(timezone.utc),
                "expires_at": today_end,  # TTL cleanup
            }
        )

        # Increment book's total views
        db.online_books.update_one(
            {"book_id": book_id}, {"$inc": {"community_config.total_views": 1}}
        )

        logger.info(f"📊 View tracked: book={book_id}, viewer={viewer_id}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to track view: {e}", exc_info=True)
        return False


# ==============================================================================
# CHAPTER CONTENT API WITH VIEW TRACKING
# ==============================================================================


@router.get(
    "/{book_id}/chapters/{chapter_id}/content",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chapter content (public for preview chapters, auth for paid)",
)
async def get_chapter_with_content(
    book_id: str,
    chapter_id: str,
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    browser_id: Optional[str] = Query(
        None, description="Browser fingerprint ID for anonymous users"
    ),
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

    **View Tracking:** Automatically tracks views for community books
    - 1 view per book per day per user/browser
    - Pass `browser_id` query param for anonymous users
    """
    try:
        # Get chapter first to check if it's a preview chapter
        chapter = chapter_manager.get_chapter_with_content(chapter_id)

        if not chapter or chapter.get("book_id") != book_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        # Track view for community books (before access check for public chapters)
        user_id = current_user["uid"] if current_user else None
        track_book_view(book_id, user_id, browser_id)

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
            access_config = book.get("access_config") or {}
            one_time_points = access_config.get("one_time_view_points", 0)
            forever_points = access_config.get("forever_view_points", 0)

            if one_time_points == 0 and forever_points == 0:
                # Free book - allow all authenticated users
                logger.info(f"📖 Free book accessed by {user_id}: chapter {chapter_id}")
                return ChapterResponse(**chapter)

        # Check if user has purchased access
        # Check forever access
        forever_purchase = db.book_purchases.find_one(
            {
                "user_id": user_id,
                "book_id": book_id,
                "purchase_type": PurchaseType.FOREVER.value,
            }
        )

        if forever_purchase:
            logger.info(
                f"📄 User {user_id} accessed chapter (forever access): {chapter_id}"
            )
            return ChapterResponse(**chapter)

        # Check one-time access (valid for 7 days)
        one_time_purchase = db.book_purchases.find_one(
            {
                "user_id": user_id,
                "book_id": book_id,
                "purchase_type": PurchaseType.ONE_TIME.value,
            }
        )

        if one_time_purchase:
            expires_at = one_time_purchase.get("access_expires_at")
            # Ensure expires_at is timezone-aware for comparison
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at > datetime.now(timezone.utc):
                logger.info(
                    f"📄 User {user_id} accessed chapter (one-time access): {chapter_id}"
                )
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


@router.get(
    "/slug/{book_slug}/chapters/{chapter_slug}/content",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chapter content by slug (public for preview chapters, auth for paid)",
)
async def get_chapter_content_by_slug(
    book_slug: str,
    chapter_slug: str,
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    browser_id: Optional[str] = Query(
        None, description="Browser fingerprint ID for anonymous users"
    ),
):
    """
    **Get chapter content using slugs (SEO-friendly URLs)**

    Same as /{book_id}/chapters/{chapter_id}/content but uses slugs instead of IDs.
    Enables SEO-friendly URLs like: /books/slug/word-ai-user-manual/chapters/document-management/content

    **URL Structure:**
    - Frontend: https://wordai.pro/online-books/read/word-ai-user-manual/document-management
    - API: https://ai.wordai.pro/api/v1/books/slug/word-ai-user-manual/chapters/document-management/content

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

    **Path Parameters:**
    - `book_slug`: Book slug (e.g., "word-ai-user-manual")
    - `chapter_slug`: Chapter slug (e.g., "document-management")

    **Authentication:** Optional (required for non-preview chapters)
    """
    try:
        # Find book by slug (must be published to Community for public access)
        book = db.online_books.find_one(
            {
                "slug": book_slug,
                "is_deleted": False,
            }
        )

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book with slug '{book_slug}' not found",
            )

        book_id = book["book_id"]

        # Find chapter by slug within this book
        chapter_doc = db.book_chapters.find_one(
            {
                "book_id": book_id,
                "slug": chapter_slug,
            }
        )

        if not chapter_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter with slug '{chapter_slug}' not found in book '{book_slug}'",
            )

        chapter_id = chapter_doc["chapter_id"]

        # Get full chapter content
        chapter = chapter_manager.get_chapter_with_content(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chapter content not found",
            )

        # Track view for community books (before access check for public chapters)
        user_id = current_user["uid"] if current_user else None
        track_book_view(book_id, user_id, browser_id)

        # Check if this is a free preview chapter
        is_preview_free = chapter.get("is_preview_free", False)

        if is_preview_free:
            # Free preview - allow anonymous access
            logger.info(
                f"📖 Preview chapter (slug) accessed: {book_slug}/{chapter_slug} (anonymous: {current_user is None})"
            )
            return ChapterResponse(**chapter)

        # For non-preview chapters, authentication is required
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this chapter",
            )

        user_id = current_user["uid"]

        # Check access permissions
        is_owner = book.get("user_id") == user_id

        if is_owner:
            # Owner has full access
            logger.info(
                f"📄 Owner {user_id} accessed chapter (slug): {book_slug}/{chapter_slug}"
            )
            return ChapterResponse(**chapter)

        # Check if book is public/free
        visibility = book.get("visibility", "private")
        community_config = book.get("community_config", {})
        is_published = community_config.get("is_public", False)

        if visibility == "public" or (is_published and visibility == "point_based"):
            # Check if it's a free book (0 points for all access types)
            access_config = book.get("access_config") or {}
            one_time_points = access_config.get("one_time_view_points", 0)
            forever_points = access_config.get("forever_view_points", 0)

            if one_time_points == 0 and forever_points == 0:
                # Free book - allow all authenticated users
                logger.info(
                    f"📖 Free book (slug) accessed by {user_id}: {book_slug}/{chapter_slug}"
                )
                return ChapterResponse(**chapter)

        # Check if user has purchased access
        # Check forever access
        forever_purchase = db.book_purchases.find_one(
            {
                "user_id": user_id,
                "book_id": book_id,
                "purchase_type": PurchaseType.FOREVER.value,
            }
        )

        if forever_purchase:
            logger.info(
                f"📄 User {user_id} accessed chapter (slug, forever): {book_slug}/{chapter_slug}"
            )
            return ChapterResponse(**chapter)

        # Check one-time access (valid for 7 days)
        one_time_purchase = db.book_purchases.find_one(
            {
                "user_id": user_id,
                "book_id": book_id,
                "purchase_type": PurchaseType.ONE_TIME.value,
            }
        )

        if one_time_purchase:
            expires_at = one_time_purchase.get("access_expires_at")
            # Ensure expires_at is timezone-aware for comparison
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at > datetime.now(timezone.utc):
                logger.info(
                    f"📄 User {user_id} accessed chapter (slug, one-time): {book_slug}/{chapter_slug}"
                )
                return ChapterResponse(**chapter)

        # No access - user needs to purchase
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Purchase required to access this chapter",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get chapter content by slug: {e}", exc_info=True)
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

    **Returns:**
    - `presigned_url`: URL for uploading file (use PUT request with file content)
    - `file_url`: Public CDN URL to use in book update
    - `expires_in`: Presigned URL expiration time in seconds (300 = 5 minutes)
    - `image_type`: Type of image (cover, logo, favicon)
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
            folder=folder,
        )

        logger.info(
            f"✅ Generated presigned URL for {request.image_type}: {result['file_url']}"
        )

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
    """Get popular tags from community books"""
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
    """Get top performing books - returns books with slug for SEO"""
    try:
        match_query = {"community_config.is_public": True}

        if period == "week":
            week_ago = datetime.utcnow() - timedelta(days=7)
            match_query["community_config.published_at"] = {"$gte": week_ago}
        elif period == "month":
            month_ago = datetime.utcnow() - timedelta(days=30)
            match_query["community_config.published_at"] = {"$gte": month_ago}

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
                    "slug": 1,  # ✅ SLUG INCLUDED
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
    """Get top performing authors"""
    try:
        match_query = {}

        if period == "week":
            week_ago = datetime.utcnow() - timedelta(days=7)
            match_query["created_at"] = {"$gte": week_ago}
        elif period == "month":
            month_ago = datetime.utcnow() - timedelta(days=30)
            match_query["created_at"] = {"$gte": month_ago}

        authors_cursor = (
            db.book_authors.find(match_query)
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


# ==============================================================================
# DOCUMENT TO CHAPTER CONVERSION
# ==============================================================================


@router.post(
    "/documents/{document_id}/convert-to-chapter",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convert document to book chapter",
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
    - **Link mode** (`copy_content=false`): Creates linked chapter

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
                detail="Failed to convert document to chapter",
            )

        logger.info(
            f"✅ Converted document {document_id} to chapter {chapter['chapter_id']} "
            f"in book {request_data.book_id} (mode: {'copy' if request_data.copy_content else 'link'})"
        )

        return ChapterResponse(**chapter)

    except ValueError as e:
        logger.error(f"❌ Invalid document conversion: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to convert document to chapter: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert document to chapter",
        )
