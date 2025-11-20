"""
Author Review Models
Models for author reviews, likes, and follows
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AuthorReviewCreate(BaseModel):
    """Create author review"""

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


class AuthorReviewResponse(BaseModel):
    """Author review response"""

    review_id: str
    author_id: str  # Author being reviewed
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


class AuthorReviewListResponse(BaseModel):
    """List of author reviews"""

    reviews: List[AuthorReviewResponse]
    total: int
    skip: int
    limit: int
    average_rating: float
    total_reviews: int


class AuthorFollowResponse(BaseModel):
    """Follow/unfollow response"""

    success: bool
    is_following: bool
    followers_count: int
    message: str


class AuthorStatsResponse(BaseModel):
    """Author profile statistics"""

    author_id: str
    name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

    # Stats
    total_books: int = 0
    total_followers: int = 0
    total_reads: int = 0  # Sum of total_views from all public books
    revenue_points: int = 0  # Total earned points

    # Reviews
    average_rating: float = 0.0
    total_reviews: int = 0
    top_review: Optional[AuthorReviewResponse] = None  # Review with most likes

    # Current user relationship (for authenticated requests)
    is_following: bool = False
    is_owner: bool = False


class AuthorFollowerItem(BaseModel):
    """Follower item"""

    user_id: str
    name: str
    avatar_url: Optional[str] = None
    followed_at: datetime


class AuthorFollowersResponse(BaseModel):
    """List of followers"""

    followers: List[AuthorFollowerItem]
    total: int
    skip: int
    limit: int
