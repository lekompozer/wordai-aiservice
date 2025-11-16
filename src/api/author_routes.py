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
