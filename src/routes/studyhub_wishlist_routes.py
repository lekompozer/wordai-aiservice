"""
FastAPI routes for StudyHub Wishlist
Provides 3 endpoints for course wishlists
"""

from fastapi import APIRouter, Query, Depends

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.studyhub_wishlist_models import (
    WishlistResponse,
    AddToWishlistResponse,
    RemoveFromWishlistResponse,
    CheckWishlistResponse,
)
from src.services.studyhub_wishlist_manager import StudyHubWishlistManager


router = APIRouter(prefix="/api/marketplace/wishlist", tags=["StudyHub - Wishlist"])

db_manager = DBManager()
db = db_manager.db


@router.post("/{course_id}", response_model=AddToWishlistResponse)
async def add_to_wishlist(
    course_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-55: Add to Wishlist**

    Add a course to the user's wishlist.

    - **Requires authentication**
    - **course_id**: Course ObjectId to add

    **Response**: Success message with course_id and timestamp

    **Business Logic**:
    - Only public marketplace courses can be added
    - One entry per user per course (enforced by unique constraint)

    **Errors**:
    - 400: Already in wishlist
    - 400: Cannot add private course
    - 404: Course not found
    """
    manager = StudyHubWishlistManager(db)

    result = await manager.add_to_wishlist(
        course_id=course_id, user_id=current_user["uid"]
    )

    return result


@router.get("", response_model=WishlistResponse)
async def get_wishlist(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """
    **API-56: Get Wishlist**

    Get the user's wishlist with full course details.

    - **Requires authentication**
    - **skip**: Pagination offset
    - **limit**: Items per page (1-100)

    **Response**: List of wishlisted courses with:
    - Course info (title, description, cover)
    - Creator info (name, avatar)
    - Stats (rating, students, modules)
    - Metadata (level, category, tags, price)
    - added_at timestamp

    **Note**: Courses sorted by most recently added first
    """
    manager = StudyHubWishlistManager(db)

    result = await manager.get_wishlist(
        user_id=current_user["uid"], skip=skip, limit=limit
    )

    return result


@router.delete("/{course_id}", response_model=RemoveFromWishlistResponse)
async def remove_from_wishlist(
    course_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-57: Remove from Wishlist**

    Remove a course from the user's wishlist.

    - **Requires authentication**
    - **course_id**: Course ObjectId to remove

    **Response**: Success message with course_id

    **Errors**:
    - 404: Course not found in wishlist
    """
    manager = StudyHubWishlistManager(db)

    result = await manager.remove_from_wishlist(
        course_id=course_id, user_id=current_user["uid"]
    )

    return result


@router.get("/{course_id}/check", response_model=CheckWishlistResponse)
async def check_wishlist(
    course_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **Bonus API: Check if Course is in Wishlist**

    Check if a specific course is in the user's wishlist.

    - **Requires authentication**
    - **course_id**: Course ObjectId to check

    **Response**:
    - **is_wishlisted**: true if in wishlist, false otherwise
    - **course_id**: Echoed course ID

    **Use Case**: Show wishlist heart icon state on course cards
    """
    manager = StudyHubWishlistManager(db)

    result = await manager.check_wishlist(
        course_id=course_id, user_id=current_user["uid"]
    )

    return result
