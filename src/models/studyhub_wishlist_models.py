"""
Pydantic models for StudyHub Wishlist API
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CourseInWishlist(BaseModel):
    """Course information in wishlist"""

    id: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None

    # Creator info
    creator_id: str
    creator_name: str
    creator_avatar: Optional[str] = None

    # Stats
    rating: float = 0.0
    students_count: int = 0
    total_modules: int = 0

    # Metadata
    level: str = "beginner"
    category: str
    tags: List[str] = []
    is_free: bool = True
    price: Optional[float] = None

    # Wishlist metadata
    added_at: datetime


class WishlistResponse(BaseModel):
    """Response for get wishlist endpoint"""

    courses: List[CourseInWishlist]
    total: int
    skip: int
    limit: int


class AddToWishlistRequest(BaseModel):
    """Request body for adding to wishlist (optional - can use URL params)"""

    course_id: str = Field(..., description="Course ObjectId to add to wishlist")


class AddToWishlistResponse(BaseModel):
    """Response for add to wishlist"""

    message: str
    course_id: str
    added_at: datetime


class RemoveFromWishlistResponse(BaseModel):
    """Response for remove from wishlist"""

    message: str
    course_id: str


class CheckWishlistResponse(BaseModel):
    """Response for checking if course is in wishlist"""

    is_wishlisted: bool
    course_id: str
