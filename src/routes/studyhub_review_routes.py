"""
FastAPI routes for StudyHub Reviews & Ratings
Provides 4 endpoints for course reviews
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.studyhub_review_models import (
    ReviewsResponse,
    ReviewItem,
    CreateReviewRequest,
    ToggleHelpfulResponse,
    DeleteResponse,
)
from src.services.studyhub_review_manager import StudyHubReviewManager


router = APIRouter(prefix="/api/marketplace/courses", tags=["StudyHub - Reviews"])

db_manager = DBManager()
db = db_manager.db


@router.get("/{course_id}/reviews", response_model=ReviewsResponse)
async def get_course_reviews(
    course_id: str,
    sort_by: str = Query("helpful", regex="^(helpful|recent|rating_high|rating_low)$"),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    **API-51: Get Reviews for Course**

    Get list of reviews for a specific course with summary statistics.

    - **Public endpoint** (auth optional - shows is_helpful if authenticated)
    - **course_id**: Course (studyhub_subjects) ObjectId
    - **sort_by**: Sort order (helpful/recent/rating_high/rating_low)
    - **rating_filter**: Optional filter by rating (1-5)
    - **skip**: Pagination offset
    - **limit**: Items per page (1-100)

    **Response**:
    - List of reviews with author info, helpful counts
    - Summary statistics (avg_rating, total_reviews, rating_distribution)
    """
    manager = StudyHubReviewManager(db)

    user_id = current_user["uid"] if current_user else None

    result = await manager.get_course_reviews(
        course_id=course_id,
        sort_by=sort_by,
        rating_filter=rating_filter,
        skip=skip,
        limit=limit,
        current_user_id=user_id,
    )

    return result


@router.post("/{course_id}/reviews", response_model=ReviewItem)
async def add_review(
    course_id: str,
    request: CreateReviewRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **API-52: Add Review**

    Add a review for a course.

    - **Requires authentication**
    - **course_id**: Course ObjectId
    - **rating**: Rating from 1-5 stars
    - **title**: Review title/headline (5-100 chars)
    - **content**: Review content (20-2000 chars)

    **Response**: Created review with author info

    **Business Logic**:
    - One review per user per course (enforced by unique constraint)
    - verified_enrollment = true if user completed course (progress >= 100%)
    - Auto-updates course.avg_rating after creation

    **Errors**:
    - 400: Already reviewed (use update endpoint instead)
    - 404: Course not found
    """
    manager = StudyHubReviewManager(db)

    result = await manager.add_review(
        course_id=course_id,
        rating=request.rating,
        title=request.title,
        content=request.content,
        user_id=current_user["uid"],
    )

    return result


@router.post("/reviews/{review_id}/helpful", response_model=ToggleHelpfulResponse)
async def toggle_helpful(
    review_id: str, current_user: dict = Depends(get_current_user)
):
    """
    **API-53: Toggle Helpful on Review**

    Mark or unmark a review as helpful (toggle behavior).

    - **Requires authentication**
    - **review_id**: Review ObjectId

    **Response**:
    - **is_helpful**: New helpful status (true = marked, false = unmarked)
    - **helpful_count**: Updated total helpful count

    **Note**: Users can mark multiple reviews as helpful
    """
    manager = StudyHubReviewManager(db)

    result = await manager.toggle_helpful(
        review_id=review_id, user_id=current_user["uid"]
    )

    return result


@router.delete("/reviews/{review_id}", response_model=DeleteResponse)
async def delete_review(review_id: str, current_user: dict = Depends(get_current_user)):
    """
    **API-54: Delete Review**

    Delete a review (hard delete).

    - **Requires authentication** (must be review author)
    - **review_id**: Review ObjectId

    **Response**: Success message

    **Note**:
    - Hard delete - removes review permanently
    - Auto-updates course.avg_rating after deletion
    """
    manager = StudyHubReviewManager(db)

    # TODO: Add admin check if needed
    # is_admin = current_user.get("role") == "admin"

    result = await manager.delete_review(
        review_id=review_id, user_id=current_user["uid"], is_admin=False
    )

    return result
