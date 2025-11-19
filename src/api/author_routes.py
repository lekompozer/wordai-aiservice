"""
Author API Routes - Community Books Author Management
Endpoints for creating and managing author profiles
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional
import logging
import uuid
from datetime import datetime

# Authentication
from src.middleware.firebase_auth import get_current_user

# Models
from src.models.author_models import (
    AuthorCreate,
    AuthorUpdate,
    AuthorResponse,
    AuthorListItem,
    AuthorListResponse,
)
from src.models.author_review_models import (
    AuthorReviewCreate,
    AuthorReviewResponse,
    AuthorReviewListResponse,
    AuthorFollowResponse,
    AuthorStatsResponse,
    AuthorFollowersResponse,
    AuthorFollowerItem,
)

# Services
from src.services.author_manager import AuthorManager

# Database
from src.database.db_manager import DBManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/authors", tags=["Authors"])

# Initialize DB connection
db_manager = DBManager()
db = db_manager.db

# Initialize manager
author_manager = AuthorManager(db)


@router.post(
    "",
    response_model=AuthorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new author profile",
)
async def create_author(
    author_data: AuthorCreate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a new author profile**

    - author_id: Unique username starting with @ (e.g., @john_doe)
    - name: Display name (can be duplicate)
    - One user can create multiple authors
    - Each author belongs to only one user
    """
    user_id = user["uid"]

    try:
        created_author = author_manager.create_author(user_id, author_data.dict())

        if not created_author:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create author",
            )

        logger.info(f"✅ User {user_id} created author: {author_data.author_id}")
        return AuthorResponse(**created_author)

    except Exception as e:
        if "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Author ID already exists: {author_data.author_id}",
            )

        logger.error(f"❌ Failed to create author: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create author",
        )


@router.get(
    "/check/{author_id}",
    summary="Check author ID availability",
    description="Check if an author ID (@username) is available for use. Public endpoint, no auth required.",
)
async def check_author_availability(author_id: str):
    """
    **Check if author ID is available**

    Returns whether the provided @username is available for registration.

    - **author_id**: The @username to check (e.g., @john_doe or john_doe)

    Returns:
    ```json
    {
        "available": true,
        "author_id": "@john_doe"
    }
    ```
    """
    try:
        # Normalize author_id: ensure it starts with @ and is lowercase
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        # Check if author exists
        existing = author_manager.get_author(author_id)
        available = existing is None

        return {"available": available, "author_id": author_id}

    except Exception as e:
        logger.error(f"Error checking author availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check author availability",
        )


@router.get(
    "/my-authors",
    response_model=AuthorListResponse,
    summary="List my author profiles",
)
async def list_my_authors(
    user: Dict[str, Any] = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    **List all author profiles created by current user**

    One user can have multiple author profiles.
    """
    user_id = user["uid"]

    try:
        authors, total = author_manager.get_author_by_user(user_id, skip, limit)

        items = [AuthorListItem(**author) for author in authors]

        return AuthorListResponse(authors=items, total=total, skip=skip, limit=limit)

    except Exception as e:
        logger.error(f"❌ Failed to list authors: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list authors",
        )


@router.get(
    "/{author_id}",
    response_model=AuthorResponse,
    summary="Get author profile",
)
async def get_author(author_id: str):
    """
    **Get author profile by ID (public endpoint)**

    - author_id: Author username (e.g., @john_doe or john_doe)

    Note: Accepts both @username and username formats. The @ symbol may be
    URL-encoded as %40 by the client.
    """
    try:
        # Normalize author_id: ensure it starts with @ and is lowercase
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        author = author_manager.get_author(author_id)

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author not found: {author_id}",
            )

        return AuthorResponse(**author)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get author: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get author",
        )


@router.patch(
    "/{author_id}",
    response_model=AuthorResponse,
    summary="Update author profile",
)
async def update_author(
    author_id: str,
    update_data: AuthorUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Update author profile**

    - Only the owner can update
    - Cannot change author_id
    """
    user_id = user["uid"]

    try:
        updated_author = author_manager.update_author(
            author_id, user_id, update_data.dict(exclude_unset=True)
        )

        if not updated_author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Author not found or you don't own this profile",
            )

        logger.info(f"✅ User {user_id} updated author: {author_id}")
        return AuthorResponse(**updated_author)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update author: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update author",
        )


@router.delete(
    "/{author_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete author profile",
)
async def delete_author(
    author_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Delete author profile**

    - Only the owner can delete
    - Cannot delete if author has published books
    """
    user_id = user["uid"]

    try:
        deleted = author_manager.delete_author(author_id, user_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete author (not found, not owned, or has published books)",
            )

        logger.info(f"✅ User {user_id} deleted author: {author_id}")
        return

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete author: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete author",
        )


@router.get(
    "",
    response_model=AuthorListResponse,
    summary="Browse all authors (public)",
)
async def list_authors(
    search: Optional[str] = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    **Browse all authors (public endpoint)**

    - No authentication required
    - Search by author name
    - Sorted by total books + followers
    """
    try:
        authors, total = author_manager.list_authors(search, skip, limit)

        items = [AuthorListItem(**author) for author in authors]

        return AuthorListResponse(authors=items, total=total, skip=skip, limit=limit)

    except Exception as e:
        logger.error(f"❌ Failed to list authors: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list authors",
        )


@router.post(
    "/{author_id}/avatar/presigned-url",
    summary="Generate presigned URL for avatar upload",
)
async def get_avatar_presigned_url(
    author_id: str,
    filename: str = Query(..., description="Avatar filename (e.g., avatar.jpg)"),
    content_type: str = Query(..., description="MIME type (e.g., image/jpeg)"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Generate presigned URL for author avatar upload**

    This endpoint generates a presigned URL for uploading author avatar directly to R2 storage.

    **Supported Image Types:**
    - JPEG (image/jpeg)
    - PNG (image/png)
    - WebP (image/webp)

    **Flow:**
    1. Frontend calls this endpoint with filename and content_type
    2. Backend validates ownership and generates presigned URL (valid for 5 minutes)
    3. Frontend uploads file directly to presigned URL using PUT request
    4. Frontend calls /avatar/confirm with file_url to save to database

    **Image Constraints:**
    - Max file size: 5MB
    - Recommended size: 512x512px (square)

    **Returns:**
    - `presigned_url`: URL for uploading file (use PUT request)
    - `file_url`: Public CDN URL to use in confirm endpoint
    - `expires_in`: Presigned URL expiration time in seconds (300 = 5 minutes)

    **Example Usage:**
    ```javascript
    // 1. Get presigned URL
    const response = await fetch('/api/v1/authors/@john_doe/avatar/presigned-url?filename=avatar.jpg&content_type=image/jpeg', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    })
    const { presigned_url, file_url } = await response.json()

    // 2. Upload file to presigned URL
    await fetch(presigned_url, {
        method: 'PUT',
        body: fileBlob,
        headers: { 'Content-Type': 'image/jpeg' }
    })

    // 3. Confirm upload
    await fetch('/api/v1/authors/@john_doe/avatar/confirm', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ avatar_url: file_url })
    })
    ```
    """
    from src.services.r2_storage_service import get_r2_service

    user_id = user["uid"]

    # Normalize author_id: ensure it starts with @ and is lowercase
    if not author_id.startswith("@"):
        author_id = f"@{author_id}"
    author_id = author_id.lower()

    logger.info(
        f"📸 Generating presigned URL for avatar: {filename} - Author: {author_id}, User: {user_id}"
    )

    try:
        # Get author
        author = author_manager.get_author(author_id)

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Check ownership
        if author["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this author profile",
            )

        # Validate content type
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid content type. Allowed: {', '.join(allowed_types)}",
            )

        # Get R2 service
        r2_service = get_r2_service()

        # Generate presigned URL with custom folder
        result = r2_service.generate_presigned_upload_url(
            filename=filename,
            content_type=content_type,
            folder="author-avatars",  # Store in organized folder
        )

        logger.info(
            f"✅ Generated presigned URL for avatar: {result['file_url']} - Author: {author_id}"
        )

        return {
            "success": True,
            "presigned_url": result["presigned_url"],
            "file_url": result["file_url"],
            "expires_in": result["expires_in"],
            "author_id": author_id,
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ R2 configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Avatar upload service not configured properly",
        )
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}",
        )


@router.post(
    "/{author_id}/avatar/confirm",
    summary="Confirm avatar upload",
)
async def confirm_avatar_upload(
    author_id: str,
    avatar_url: str = Query(..., description="Public CDN URL from presigned upload"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Confirm avatar upload and save to database**

    Call this endpoint after successfully uploading file to presigned URL.

    **Parameters:**
    - `avatar_url`: The file_url returned from presigned-url endpoint

    **Returns:**
    ```json
    {
        "success": true,
        "message": "Avatar updated successfully",
        "author_id": "@john_doe",
        "avatar_url": "https://cdn.wordai.vn/author-avatars/..."
    }
    ```
    """
    from datetime import datetime

    user_id = user["uid"]

    logger.info(f"💾 Confirming avatar upload for author {author_id}: {avatar_url}")

    try:
        # Get author
        author = author_manager.get_author(author_id)

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Check ownership
        if author["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this author profile",
            )

        # Update author avatar
        result = db.book_authors.update_one(
            {"author_id": author_id},
            {"$set": {"avatar_url": avatar_url, "updated_at": datetime.now()}},
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        logger.info(f"✅ Avatar updated for author {author_id}")

        return {
            "success": True,
            "message": "Avatar updated successfully",
            "author_id": author_id,
            "avatar_url": avatar_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to confirm avatar upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm avatar upload: {str(e)}",
        )


@router.patch(
    "/{author_id}/profile",
    response_model=AuthorResponse,
    summary="Update author profile",
)
async def update_author_profile(
    author_id: str,
    update_data: AuthorUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Update author profile information**

    - Only the owner can update
    - Update: name, bio, website_url, social_links

    **Request Body:**
    ```json
    {
        "name": "John Doe",
        "bio": "Full-stack developer with 10+ years experience",
        "website_url": "https://johndoe.com",
        "social_links": {
            "twitter": "https://twitter.com/johndoe",
            "github": "https://github.com/johndoe",
            "linkedin": "https://linkedin.com/in/johndoe"
        }
    }
    ```

    **Returns:**
    Updated author profile
    """
    user_id = user["uid"]

    # Normalize author_id: ensure it starts with @ and is lowercase
    if not author_id.startswith("@"):
        author_id = f"@{author_id}"
    author_id = author_id.lower()

    logger.info(f"📝 User {user_id} updating profile for author {author_id}")

    try:
        # Get author
        author = author_manager.get_author(author_id)

        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Check ownership
        if author["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this author profile",
            )

        # Update author using manager
        updated_author = author_manager.update_author(author_id, update_data, user)

        logger.info(f"✅ Profile updated for author {author_id}")

        return AuthorResponse(**updated_author)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update author profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update author profile: {str(e)}",
        )


@router.get(
    "/{author_id}/books",
    summary="List books by author",
)
async def list_author_books(
    author_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    sort: str = Query("newest", description="Sort: newest|popular|top_rated"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    **List published books by author (public endpoint)**

    - No authentication required
    - Filter by category and tags
    - Sort by newest, popular (views), or top_rated

    **Returns:**
    ```json
    {
        "books": [...],
        "total": 10,
        "skip": 0,
        "limit": 20,
        "author": {
            "author_id": "@john_doe",
            "name": "John Doe",
            "avatar_url": "..."
        },
        "filters": {
            "category": "technology",
            "tags": ["python", "ai"],
            "sort": "newest"
        }
    }
    ```
    """
    try:
        # Normalize author_id: ensure it starts with @ and is lowercase
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        logger.info(f"📚 Listing books by author {author_id} (sort={sort})")

        # Check author exists
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Build query - lấy tất cả books đã publish lên community
        query = {
            "authors": author_id,  # authors is an array field
            "community_config.is_public": True,
            "deleted_at": None,
        }

        # Apply filters
        if category:
            query["community_config.category"] = category

        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            if tag_list:
                query["community_config.tags"] = {"$in": tag_list}

        # Get total count
        total = db.online_books.count_documents(query)

        # Determine sort order
        sort_order = []
        if sort == "popular":
            sort_order = [("community_config.total_views", -1)]
        elif sort == "top_rated":
            sort_order = [("community_config.average_rating", -1)]
        else:  # newest
            sort_order = [("community_config.published_at", -1)]

        # Get books
        books_cursor = (
            db.online_books.find(query).sort(sort_order).skip(skip).limit(limit)
        )

        books = []
        for book in books_cursor:
            community = book.get("community_config", {})

            books.append(
                {
                    "book_id": book["book_id"],
                    "title": book["title"],
                    "slug": book["slug"],
                    "description": book.get("description"),
                    "cover_image_url": book.get("cover_image_url"),
                    "category": community.get("category"),
                    "tags": community.get("tags", []),
                    "difficulty_level": community.get("difficulty_level"),
                    "total_views": community.get("total_views", 0),
                    "total_purchases": community.get("total_purchases", 0),
                    "total_saves": community.get("total_saves", 0),
                    "average_rating": community.get("average_rating", 0.0),
                    "rating_count": community.get("rating_count", 0),
                    "access_config": book.get("access_config"),
                    "published_at": community.get("published_at"),
                }
            )

        logger.info(
            f"✅ Returning {len(books)} books by author {author_id} (total: {total})"
        )

        return {
            "books": books,
            "total": total,
            "skip": skip,
            "limit": limit,
            "author": {
                "author_id": author["author_id"],
                "name": author["name"],
                "avatar_url": author.get("avatar_url"),
            },
            "filters": {
                "category": category,
                "tags": tag_list,
                "sort": sort,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list author books: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list author books: {str(e)}",
        )


# ============================================================================
# AUTHOR STATISTICS & PROFILE CARD
# ============================================================================
# ============================================================================


@router.get(
    "/{author_id}/stats",
    response_model=AuthorStatsResponse,
    summary="Get author profile statistics (public)",
)
async def get_author_stats(
    author_id: str,
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    **Get author profile statistics for profile card**

    Returns complete author stats including:
    - Basic info (name, avatar, bio)
    - Total books, followers, reads, revenue
    - Average rating and reviews
    - Top review (most liked)
    - Current user relationship (is_following, is_owner)

    No authentication required (public endpoint).
    If authenticated, includes relationship data.
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        # Get author
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Get total books (public only)
        total_books = db.online_books.count_documents(
            {
                "authors": author_id,
                "community_config.is_public": True,
                "deleted_at": None,
            }
        )

        # Get total reads (sum of total_views from all public books)
        pipeline = [
            {
                "$match": {
                    "authors": author_id,
                    "community_config.is_public": True,
                    "deleted_at": None,
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_reads": {"$sum": "$community_config.total_views"},
                }
            },
        ]
        reads_result = list(db.online_books.aggregate(pipeline))
        total_reads = reads_result[0]["total_reads"] if reads_result else 0

        # Get revenue points from author document
        revenue_points = author.get("total_revenue_points", 0)

        # Get total followers
        total_followers = db.author_follows.count_documents({"author_id": author_id})

        # Get review stats
        reviews = list(db.author_reviews.find({"author_id": author_id}))
        total_reviews = len(reviews)
        average_rating = (
            sum(r.get("rating", 0) for r in reviews) / total_reviews
            if total_reviews > 0
            else 0.0
        )

        # Get top review (most liked)
        top_review = None
        if reviews:
            top_review_doc = max(reviews, key=lambda r: r.get("likes_count", 0))
            if top_review_doc.get("likes_count", 0) > 0:
                reviewer = db.users.find_one(
                    {"user_id": top_review_doc["reviewer_user_id"]}
                )
                top_review = AuthorReviewResponse(
                    review_id=top_review_doc["review_id"],
                    author_id=top_review_doc["author_id"],
                    reviewer_user_id=top_review_doc["reviewer_user_id"],
                    reviewer_name=(
                        reviewer.get("name", "Anonymous") if reviewer else "Anonymous"
                    ),
                    reviewer_avatar_url=(
                        reviewer.get("avatar_url") if reviewer else None
                    ),
                    text=top_review_doc["text"],
                    image_url=top_review_doc.get("image_url"),
                    rating=top_review_doc["rating"],
                    likes_count=top_review_doc.get("likes_count", 0),
                    is_liked_by_current_user=False,
                    created_at=top_review_doc["created_at"],
                    updated_at=top_review_doc["updated_at"],
                )

        # Check current user relationship
        is_following = False
        is_owner = False
        if user:
            user_id = user["uid"]
            is_owner = author.get("user_id") == user_id
            is_following = (
                db.author_follows.find_one(
                    {
                        "author_id": author_id,
                        "follower_user_id": user_id,
                    }
                )
                is not None
            )

        return AuthorStatsResponse(
            author_id=author["author_id"],
            name=author["name"],
            avatar_url=author.get("avatar_url"),
            bio=author.get("bio"),
            total_books=total_books,
            total_followers=total_followers,
            total_reads=total_reads,
            revenue_points=revenue_points,
            average_rating=round(average_rating, 1),
            total_reviews=total_reviews,
            top_review=top_review,
            is_following=is_following,
            is_owner=is_owner,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get author stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get author stats",
        )


# ============================================================================
# AUTHOR REVIEWS
# ============================================================================


@router.post(
    "/{author_id}/reviews",
    response_model=AuthorReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create author review",
)
async def create_author_review(
    author_id: str,
    review_data: AuthorReviewCreate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a review for an author**

    - Each user can only review an author once
    - Review includes text, optional image, and rating (1-5 stars)
    - User cannot review their own author profile

    **Authentication required**
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        user_id = user["uid"]

        # Check author exists
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Cannot review own author
        if author.get("user_id") == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot review your own author profile",
            )

        # Check if user already reviewed this author
        existing = db.author_reviews.find_one(
            {
                "author_id": author_id,
                "reviewer_user_id": user_id,
            }
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already reviewed this author",
            )

        # Create review
        review_id = f"review_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        review_doc = {
            "review_id": review_id,
            "author_id": author_id,
            "reviewer_user_id": user_id,
            "text": review_data.text,
            "image_url": review_data.image_url,
            "rating": review_data.rating,
            "likes_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        db.author_reviews.insert_one(review_doc)

        # Get reviewer info
        reviewer_name = user.get("name", user.get("email", "Anonymous"))
        reviewer_avatar = user.get("picture")

        logger.info(f"✅ User {user_id} created review for author {author_id}")

        return AuthorReviewResponse(
            review_id=review_id,
            author_id=author_id,
            reviewer_user_id=user_id,
            reviewer_name=reviewer_name,
            reviewer_avatar_url=reviewer_avatar,
            text=review_data.text,
            image_url=review_data.image_url,
            rating=review_data.rating,
            likes_count=0,
            is_liked_by_current_user=False,
            created_at=now,
            updated_at=now,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create review",
        )


@router.get(
    "/{author_id}/reviews",
    response_model=AuthorReviewListResponse,
    summary="List author reviews (public)",
)
async def list_author_reviews(
    author_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("likes", description="Sort by: likes, newest, rating"),
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    """
    **List reviews for an author**

    - Public endpoint (no authentication required)
    - If authenticated, includes is_liked_by_current_user
    - Sort by: likes (most liked), newest, rating (highest first)

    **Returns:** List of reviews with pagination
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        # Check author exists
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Determine sort order
        if sort == "likes":
            sort_field = [("likes_count", -1), ("created_at", -1)]
        elif sort == "rating":
            sort_field = [("rating", -1), ("created_at", -1)]
        else:  # newest
            sort_field = [("created_at", -1)]

        # Get reviews
        total = db.author_reviews.count_documents({"author_id": author_id})
        reviews_cursor = (
            db.author_reviews.find({"author_id": author_id})
            .sort(sort_field)
            .skip(skip)
            .limit(limit)
        )

        # Build response
        reviews = []
        user_id = user["uid"] if user else None
        user_likes = set()

        # Get user's likes if authenticated
        if user_id:
            likes = db.author_review_likes.find({"user_id": user_id})
            user_likes = {like["review_id"] for like in likes}

        for review_doc in reviews_cursor:
            # Get reviewer info
            reviewer = db.users.find_one({"user_id": review_doc["reviewer_user_id"]})
            reviewer_name = (
                reviewer.get("name", "Anonymous") if reviewer else "Anonymous"
            )
            reviewer_avatar = reviewer.get("avatar_url") if reviewer else None

            reviews.append(
                AuthorReviewResponse(
                    review_id=review_doc["review_id"],
                    author_id=review_doc["author_id"],
                    reviewer_user_id=review_doc["reviewer_user_id"],
                    reviewer_name=reviewer_name,
                    reviewer_avatar_url=reviewer_avatar,
                    text=review_doc["text"],
                    image_url=review_doc.get("image_url"),
                    rating=review_doc["rating"],
                    likes_count=review_doc.get("likes_count", 0),
                    is_liked_by_current_user=review_doc["review_id"] in user_likes,
                    created_at=review_doc["created_at"],
                    updated_at=review_doc["updated_at"],
                )
            )

        # Calculate average rating
        all_reviews = list(db.author_reviews.find({"author_id": author_id}))
        average_rating = (
            sum(r.get("rating", 0) for r in all_reviews) / len(all_reviews)
            if all_reviews
            else 0.0
        )

        return AuthorReviewListResponse(
            reviews=reviews,
            total=total,
            skip=skip,
            limit=limit,
            average_rating=round(average_rating, 1),
            total_reviews=total,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list reviews: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list reviews",
        )


@router.delete(
    "/{author_id}/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete author review",
)
async def delete_author_review(
    author_id: str,
    review_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Delete a review**

    - Author owner can delete any review on their profile
    - Review author can delete their own review

    **Authentication required**
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        user_id = user["uid"]

        # Get review
        review = db.author_reviews.find_one(
            {
                "review_id": review_id,
                "author_id": author_id,
            }
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )

        # Check permission
        author = author_manager.get_author(author_id)
        is_owner = author.get("user_id") == user_id
        is_reviewer = review["reviewer_user_id"] == user_id

        if not (is_owner or is_reviewer):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this review",
            )

        # Delete review
        db.author_reviews.delete_one({"review_id": review_id})

        # Delete all likes for this review
        db.author_review_likes.delete_many({"review_id": review_id})

        logger.info(f"✅ Deleted review {review_id} by user {user_id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete review",
        )


# ============================================================================
# REVIEW LIKES
# ============================================================================


@router.post(
    "/{author_id}/reviews/{review_id}/like",
    status_code=status.HTTP_200_OK,
    summary="Like/unlike a review",
)
async def toggle_review_like(
    author_id: str,
    review_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Toggle like on a review**

    - If not liked → add like
    - If already liked → remove like
    - Each user can only like once per review

    **Authentication required**

    **Returns:**
    ```json
    {
        "success": true,
        "is_liked": true,
        "likes_count": 42
    }
    ```
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        user_id = user["uid"]

        # Check review exists
        review = db.author_reviews.find_one(
            {
                "review_id": review_id,
                "author_id": author_id,
            }
        )
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )

        # Check if already liked
        existing_like = db.author_review_likes.find_one(
            {
                "review_id": review_id,
                "user_id": user_id,
            }
        )

        if existing_like:
            # Unlike
            db.author_review_likes.delete_one(
                {
                    "review_id": review_id,
                    "user_id": user_id,
                }
            )
            db.author_reviews.update_one(
                {"review_id": review_id},
                {"$inc": {"likes_count": -1}},
            )
            is_liked = False
            logger.info(f"👎 User {user_id} unliked review {review_id}")
        else:
            # Like
            db.author_review_likes.insert_one(
                {
                    "review_id": review_id,
                    "user_id": user_id,
                    "liked_at": datetime.utcnow(),
                }
            )
            db.author_reviews.update_one(
                {"review_id": review_id},
                {"$inc": {"likes_count": 1}},
            )
            is_liked = True
            logger.info(f"👍 User {user_id} liked review {review_id}")

        # Get updated likes count
        updated_review = db.author_reviews.find_one({"review_id": review_id})
        likes_count = updated_review.get("likes_count", 0)

        return {
            "success": True,
            "is_liked": is_liked,
            "likes_count": likes_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to toggle like: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle like",
        )


# ============================================================================
# AUTHOR FOLLOWS
# ============================================================================


@router.post(
    "/{author_id}/follow",
    response_model=AuthorFollowResponse,
    summary="Follow/unfollow author",
)
async def toggle_follow_author(
    author_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Toggle follow on an author**

    - If not following → follow
    - If already following → unfollow
    - Cannot follow your own author profile

    **Authentication required**
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        user_id = user["uid"]

        # Check author exists
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Cannot follow own author
        if author.get("user_id") == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot follow your own author profile",
            )

        # Check if already following
        existing_follow = db.author_follows.find_one(
            {
                "author_id": author_id,
                "follower_user_id": user_id,
            }
        )

        if existing_follow:
            # Unfollow
            db.author_follows.delete_one(
                {
                    "author_id": author_id,
                    "follower_user_id": user_id,
                }
            )
            is_following = False
            message = f"Unfollowed {author['name']}"
            logger.info(f"✅ User {user_id} unfollowed author {author_id}")
        else:
            # Follow
            db.author_follows.insert_one(
                {
                    "author_id": author_id,
                    "follower_user_id": user_id,
                    "followed_at": datetime.utcnow(),
                }
            )
            is_following = True
            message = f"Following {author['name']}"
            logger.info(f"✅ User {user_id} followed author {author_id}")

        # Get updated followers count
        followers_count = db.author_follows.count_documents({"author_id": author_id})

        return AuthorFollowResponse(
            success=True,
            is_following=is_following,
            followers_count=followers_count,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to toggle follow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle follow",
        )


@router.get(
    "/{author_id}/follow/status",
    summary="Check if following author",
)
async def check_follow_status(
    author_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Check if current user is following an author**

    **Authentication required**

    **Returns:**
    ```json
    {
        "is_following": true,
        "followers_count": 42
    }
    ```
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        user_id = user["uid"]

        # Check if following
        is_following = (
            db.author_follows.find_one(
                {
                    "author_id": author_id,
                    "follower_user_id": user_id,
                }
            )
            is not None
        )

        # Get followers count
        followers_count = db.author_follows.count_documents({"author_id": author_id})

        return {
            "is_following": is_following,
            "followers_count": followers_count,
        }

    except Exception as e:
        logger.error(f"❌ Failed to check follow status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check follow status",
        )


@router.get(
    "/{author_id}/followers",
    response_model=AuthorFollowersResponse,
    summary="List author followers (public)",
)
async def list_author_followers(
    author_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    **List followers of an author**

    Public endpoint (no authentication required)
    """
    try:
        # Normalize author_id
        if not author_id.startswith("@"):
            author_id = f"@{author_id}"
        author_id = author_id.lower()

        # Check author exists
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Get followers
        total = db.author_follows.count_documents({"author_id": author_id})
        follows_cursor = (
            db.author_follows.find({"author_id": author_id})
            .sort("followed_at", -1)
            .skip(skip)
            .limit(limit)
        )

        followers = []
        for follow in follows_cursor:
            # Get follower user info
            follower_user = db.users.find_one({"user_id": follow["follower_user_id"]})
            if follower_user:
                followers.append(
                    AuthorFollowerItem(
                        user_id=follower_user["user_id"],
                        name=follower_user.get("name", "Anonymous"),
                        avatar_url=follower_user.get("avatar_url"),
                        followed_at=follow["followed_at"],
                    )
                )

        return AuthorFollowersResponse(
            followers=followers,
            total=total,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to list followers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list followers",
        )
