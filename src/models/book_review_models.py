"""
Book Review Models
Models for book reviews and likes
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BookReviewCreate(BaseModel):
    """Create book review"""

    text: str = Field(..., min_length=10, max_length=1000, description="Review text")
    image_url: Optional[str] = Field(None, description="Optional review image URL")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5 stars")
    reviewer_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Custom reviewer name (fallback to Firebase if not provided)",
    )
    reviewer_avatar_url: Optional[str] = Field(
        None,
        description="Custom reviewer avatar URL (fallback to Firebase if not provided)",
    )


class BookReviewResponse(BaseModel):
    """Book review response"""

    review_id: str
    book_id: str  # Book being reviewed
    reviewer_user_id: str  # User who wrote the review
    reviewer_name: str
    reviewer_avatar_url: Optional[str] = None
    text: str
    image_url: Optional[str] = None
    rating: int
    likes_count: int = 0
    is_liked_by_current_user: bool = False  # For authenticated requests
    created_at: datetime
    updated_at: datetime


class BookReviewListResponse(BaseModel):
    """List of book reviews"""

    reviews: List[BookReviewResponse]
    total: int
    skip: int
    limit: int
    average_rating: float
    total_reviews: int
