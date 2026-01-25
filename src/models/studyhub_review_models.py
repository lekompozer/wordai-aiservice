"""
Pydantic models for StudyHub Reviews & Ratings API
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class ReviewAuthor(BaseModel):
    """Author information for reviews"""

    id: str
    name: str
    avatar: Optional[str] = None


class ReviewItem(BaseModel):
    """Single review item"""

    id: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5 stars")
    title: str
    content: str
    author: ReviewAuthor
    helpful_count: int = 0
    is_helpful: bool = False  # Marked by current user
    verified_enrollment: bool = False  # User completed the course
    created_at: datetime
    updated_at: datetime


class ReviewSummary(BaseModel):
    """Aggregate review statistics"""

    avg_rating: float = 0.0
    total_reviews: int = 0
    rating_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
        description="Count of reviews per star rating",
    )


class ReviewsResponse(BaseModel):
    """Response for list reviews endpoint"""

    reviews: List[ReviewItem]
    total: int
    skip: int
    limit: int
    summary: ReviewSummary


class CreateReviewRequest(BaseModel):
    """Request body for creating a review"""

    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5 stars")
    title: str = Field(
        ..., min_length=5, max_length=100, description="Review title/headline"
    )
    content: str = Field(
        ..., min_length=20, max_length=2000, description="Review content"
    )


class UpdateReviewRequest(BaseModel):
    """Request body for updating a review"""

    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, min_length=5, max_length=100)
    content: Optional[str] = Field(None, min_length=20, max_length=2000)


class ToggleHelpfulResponse(BaseModel):
    """Response for helpful/unhelpful actions"""

    is_helpful: bool
    helpful_count: int


class DeleteResponse(BaseModel):
    """Generic delete response"""

    message: str
