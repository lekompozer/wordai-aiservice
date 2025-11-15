"""
Pydantic Models for User Guide System
Phase 1: Guide metadata and settings
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class GuideVisibility(str, Enum):
    """Guide visibility options"""

    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"


class GuideCreate(BaseModel):
    """Request model to create a new guide"""

    title: str = Field(..., min_length=1, max_length=200, description="Guide title")
    description: Optional[str] = Field(
        None, max_length=500, description="Guide description"
    )
    slug: str = Field(
        ..., min_length=1, max_length=100, description="URL-friendly slug"
    )
    visibility: GuideVisibility = Field(
        default=GuideVisibility.PUBLIC, description="Visibility setting"
    )
    is_published: bool = Field(default=False, description="Published state")

    # Branding (optional)
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(default="#4F46E5", pattern="^#[0-9A-Fa-f]{6}$")

    # SEO
    meta_title: Optional[str] = Field(None, max_length=100)
    meta_description: Optional[str] = Field(None, max_length=200)

    @validator("slug")
    def validate_slug(cls, v):
        """Ensure slug is URL-safe"""
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return v


class GuideUpdate(BaseModel):
    """Request model to update guide"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    visibility: Optional[GuideVisibility] = None
    is_published: Optional[bool] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    meta_title: Optional[str] = Field(None, max_length=100)
    meta_description: Optional[str] = Field(None, max_length=200)


class GuideResponse(BaseModel):
    """Response model for guide"""

    guide_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    slug: str
    visibility: GuideVisibility
    is_published: bool
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str = "#4F46E5"
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    view_count: int = 0
    unique_visitors: int = 0
    created_at: datetime
    updated_at: datetime
    last_published_at: Optional[datetime] = None


class GuideListItem(BaseModel):
    """Simplified guide info for listing"""

    guide_id: str
    title: str
    slug: str
    description: Optional[str] = None
    visibility: GuideVisibility
    is_published: bool
    chapter_count: int = 0
    view_count: int = 0
    updated_at: datetime
    last_published_at: Optional[datetime] = None


class GuideListResponse(BaseModel):
    """Response for guide listing with pagination"""

    guides: List[GuideListItem]
    pagination: dict
    total: int
