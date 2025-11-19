"""
Author API Routes - Community Books Author Management
Endpoints for creating and managing author profiles
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, Optional
import logging

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

    - **author_id**: The @username to check (e.g., @john_doe)

    Returns:
    ```json
    {
        "available": true,
        "author_id": "@john_doe"
    }
    ```
    """
    try:
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

    - author_id: Author username (e.g., @john_doe)
    """
    try:
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
    "/{author_id}/avatar",
    summary="Upload author avatar",
)
async def upload_author_avatar(
    author_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Upload author avatar image**

    - Only the owner can upload
    - Accepts: JPEG, PNG, WebP (max 5MB)
    - Returns: Base64 data URL

    **Request:**
    - Content-Type: multipart/form-data
    - Field: file (image file)

    **Returns:**
    ```json
    {
        "success": true,
        "message": "Avatar uploaded successfully",
        "avatar_url": "data:image/jpeg;base64,...",
        "size_bytes": 12345
    }
    ```
    """
    from fastapi import UploadFile, File
    import base64
    from io import BytesIO
    from PIL import Image

    user_id = user["uid"]

    logger.info(f"📸 User {user_id} uploading avatar for author {author_id}")

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

        # Note: This endpoint expects multipart/form-data
        # Frontend should send FormData with file field
        # For now, return placeholder - implement with actual file upload

        return {
            "success": False,
            "message": "Avatar upload endpoint ready - send multipart/form-data with 'file' field",
            "author_id": author_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to upload avatar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar: {str(e)}",
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
        logger.info(f"📚 Listing books by author {author_id} (sort={sort})")

        # Check author exists
        author = author_manager.get_author(author_id)
        if not author:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Author {author_id} not found",
            )

        # Build query
        query = {
            "author_id": author_id,
            "community_config.is_public": True,
            "is_published": True,
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
        total = db.books.count_documents(query)

        # Determine sort order
        sort_order = []
        if sort == "popular":
            sort_order = [("community_config.total_views", -1)]
        elif sort == "top_rated":
            sort_order = [("community_config.average_rating", -1)]
        else:  # newest
            sort_order = [("community_config.published_at", -1)]

        # Get books
        books_cursor = db.books.find(query).sort(sort_order).skip(skip).limit(limit)

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
