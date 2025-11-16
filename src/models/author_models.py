"""
Author Models - Community Books Author System
Authors are public identities for publishing books to community marketplace
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import re


class AuthorCreate(BaseModel):
    """Request to create a new author"""

    author_id: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Unique username (e.g., @john_doe)",
    )
    name: str = Field(..., min_length=2, max_length=100, description="Display name")
    bio: Optional[str] = Field(None, max_length=500, description="Author bio")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    website_url: Optional[str] = Field(None, description="Author website")
    social_links: Optional[dict] = Field(
        default_factory=dict, description="Social media links"
    )

    @validator("author_id")
    def validate_author_id(cls, v):
        """Validate author_id format: must start with @ and contain only alphanumeric + underscore"""
        if not v.startswith("@"):
            raise ValueError("author_id must start with @")

        # Remove @ for validation
        username = v[1:]
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValueError(
                "author_id can only contain letters, numbers, and underscores after @"
            )

        if len(username) < 2:
            raise ValueError("author_id must have at least 2 characters after @")

        return v.lower()  # Store as lowercase


class AuthorUpdate(BaseModel):
    """Update author profile"""

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None
    website_url: Optional[str] = None
    social_links: Optional[dict] = None


class AuthorResponse(BaseModel):
    """Author profile response"""

    author_id: str
    name: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    website_url: Optional[str] = None
    social_links: dict = {}

    # Stats
    total_books: int = 0
    total_followers: int = 0
    total_revenue_points: int = 0

    # User linkage
    user_id: str  # Firebase UID (owner)

    # Timestamps
    created_at: datetime
    updated_at: datetime


class AuthorListItem(BaseModel):
    """Author item in list"""

    author_id: str
    name: str
    avatar_url: Optional[str] = None
    total_books: int = 0
    total_followers: int = 0


class AuthorListResponse(BaseModel):
    """List of authors"""

    authors: List[AuthorListItem]
    total: int
    skip: int = 0
    limit: int = 20


class AuthorBookItem(BaseModel):
    """Book published by author"""

    book_id: str
    title: str
    slug: str
    cover_image_url: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    total_views: int = 0
    total_purchases: int = 0
    average_rating: float = 0.0
    published_at: datetime
