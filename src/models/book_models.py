"""
Pydantic Models for User Guide System
Phase 1: Guide metadata and settings
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class BookVisibility(str, Enum):
    """Guide visibility options"""

    PUBLIC = "public"  # Free access, no login required
    PRIVATE = "private"  # Only owner and invited users
    UNLISTED = "unlisted"  # Anyone with link (not in public listings)
    POINT_BASED = "point_based"  # Requires points to access (NEW)


class AccessConfig(BaseModel):
    """Point-based access configuration"""

    one_time_view_points: int = Field(0, ge=0, description="Points for one-time view")
    forever_view_points: int = Field(0, ge=0, description="Points for unlimited view")
    download_pdf_points: int = Field(0, ge=0, description="Points to download PDF")
    is_one_time_enabled: bool = Field(True, description="Enable one-time view option")
    is_forever_enabled: bool = Field(True, description="Enable forever view option")
    is_download_enabled: bool = Field(True, description="Enable download option")


class CommunityConfig(BaseModel):
    """Community marketplace configuration"""

    is_public: bool = Field(False, description="Published to community?")
    category: Optional[str] = Field(None, description="Book category")
    tags: List[str] = Field(default_factory=list, description="Tags for search")
    short_description: Optional[str] = Field(None, max_length=200)
    difficulty_level: Optional[str] = Field(
        None, description="beginner|intermediate|advanced|expert"
    )
    cover_image_url: Optional[str] = None
    total_views: int = 0
    total_downloads: int = 0
    total_purchases: int = 0
    average_rating: float = 0.0
    rating_count: int = 0
    version: str = "1.0.0"
    published_at: Optional[datetime] = None


class BookStats(BaseModel):
    """Book revenue statistics"""

    total_revenue_points: int = 0  # Total points collected (100%)
    owner_reward_points: int = 0  # Owner's share (80%)
    system_fee_points: int = 0  # System's share (20%)


class BookCreate(BaseModel):
    """Request model to create a new guide"""

    title: str = Field(..., min_length=1, max_length=200, description="Guide title")
    description: Optional[str] = Field(
        None, max_length=500, description="Guide description"
    )
    slug: str = Field(
        ..., min_length=1, max_length=100, description="URL-friendly slug"
    )
    visibility: BookVisibility = Field(
        default=BookVisibility.PRIVATE,
        description="Visibility setting (default: private)",
    )
    is_published: bool = Field(default=False, description="Published state")

    # Point-based access (NEW)
    access_config: Optional[AccessConfig] = Field(
        default=None,
        description="Point pricing config (required if visibility=point_based)",
    )

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

    @validator("access_config")
    def validate_access_config(cls, v, values):
        """Validate access_config is provided when visibility is point_based"""
        if values.get("visibility") == BookVisibility.POINT_BASED and not v:
            raise ValueError("access_config is required when visibility is point_based")
        return v


class BookUpdate(BaseModel):
    """Request model to update guide"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    visibility: Optional[BookVisibility] = None
    is_published: Optional[bool] = None

    # Point-based access (NEW)
    access_config: Optional[AccessConfig] = None

    # Branding
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    meta_title: Optional[str] = Field(None, max_length=100)
    meta_description: Optional[str] = Field(None, max_length=200)


class BookResponse(BaseModel):
    """Response model for guide"""

    book_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    slug: str
    visibility: BookVisibility
    is_published: bool

    # Point-based access (NEW)
    access_config: Optional[AccessConfig] = None

    # Community marketplace (NEW)
    community_config: Optional[CommunityConfig] = None

    # Revenue stats (NEW)
    stats: Optional[BookStats] = None

    # Branding
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str = "#4F46E5"
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    # Analytics
    view_count: int = 0
    unique_visitors: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_published_at: Optional[datetime] = None


class GuideListItem(BaseModel):
    """Simplified guide info for listing"""

    book_id: str
    title: str
    slug: str
    description: Optional[str] = None
    visibility: BookVisibility
    is_published: bool
    chapter_count: int = 0
    view_count: int = 0
    updated_at: datetime
    last_published_at: Optional[datetime] = None


class BookListResponse(BaseModel):
    """Response for guide listing with pagination"""

    books: List[GuideListItem]  # Changed from 'guides' to 'books' for consistency
    pagination: dict
    total: int


# ============ COMMUNITY BOOKS MODELS (NEW) ============


class CommunityPublishRequest(BaseModel):
    """Request to publish book to community"""

    # Author (NEW - required for community publishing)
    author_id: str = Field(
        ...,
        description="Author ID (e.g., @john_doe). Can be existing or new - use check endpoint to verify availability first.",
    )
    # Only for NEW authors (if author_id doesn't exist yet)
    author_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Display name (required only if creating new author)",
    )
    author_bio: Optional[str] = Field(
        None, max_length=500, description="Author bio (optional, for new author)"
    )
    author_avatar_url: Optional[str] = Field(
        None, description="Author avatar (optional, for new author)"
    )

    # Visibility & Pricing
    visibility: BookVisibility = Field(
        ...,
        description="public (free) or point_based (paid)",
    )
    access_config: Optional[AccessConfig] = Field(
        None,
        description="Required if visibility=point_based",
    )

    # Community metadata
    category: str = Field(
        ..., description="Book category (programming, business, marketing, etc.)"
    )
    tags: List[str] = Field(..., min_items=1, max_items=10, description="Search tags")
    difficulty_level: Optional[str] = Field(
        None, description="beginner|intermediate|advanced|expert (optional)"
    )
    short_description: str = Field(..., min_length=10, max_length=200)
    cover_image_url: Optional[str] = Field(None, description="Cover image URL")

    @validator("visibility")
    def validate_visibility(cls, v):
        """Only allow public or point_based when publishing to community"""
        if v not in [BookVisibility.PUBLIC, BookVisibility.POINT_BASED]:
            raise ValueError(
                "visibility must be 'public' (free) or 'point_based' (paid) when publishing to community"
            )
        return v

    @validator("access_config")
    def validate_access_config(cls, v, values):
        """Validate access_config is provided when visibility is point_based"""
        if values.get("visibility") == BookVisibility.POINT_BASED and not v:
            raise ValueError("access_config is required when visibility is point_based")
        return v


class CommunityBookItem(BaseModel):
    """Community book listing item"""

    book_id: str
    title: str
    slug: str
    short_description: Optional[str] = None
    cover_image_url: Optional[str] = None
    category: Optional[str] = "uncategorized"
    tags: List[str] = []
    difficulty_level: Optional[str] = "beginner"

    # Pricing (if point_based)
    forever_view_points: int = 0  # Main price to display

    # Stats
    total_views: int = 0
    total_purchases: int = 0
    average_rating: float = 0.0
    rating_count: int = 0

    # Author
    author_id: str
    author_name: Optional[str] = None

    # Timestamps
    published_at: Optional[datetime] = None


class CommunityBooksResponse(BaseModel):
    """Response for community books listing"""

    items: List[CommunityBookItem]
    total: int
    page: int
    limit: int
    total_pages: int


# ============ DOCUMENT INTEGRATION MODELS (NEW) ============


class ChapterFromDocumentRequest(BaseModel):
    """Request to create chapter from existing document"""

    document_id: str = Field(..., description="Document ID to convert")
    title: Optional[str] = Field(
        None, description="Override title (uses document title if not provided)"
    )
    order_index: int = Field(..., ge=0, description="Position in chapter list")
    parent_id: Optional[str] = Field(
        None, description="Parent chapter ID for nested structure"
    )


# ============ IMAGE UPLOAD MODELS (NEW) ============


class BookImageUploadRequest(BaseModel):
    """Request model for generating presigned URL for book image upload"""

    filename: str = Field(
        ..., min_length=1, max_length=255, description="Image filename"
    )
    content_type: str = Field(
        "image/jpeg",
        description="MIME type (image/jpeg, image/png, image/webp, image/svg+xml)",
    )
    image_type: str = Field(
        ...,
        description="Type of image: 'cover' (cover_image_url), 'logo' (logo_url), 'favicon' (favicon_url)",
    )
    file_size_mb: float = Field(
        ..., gt=0, le=10, description="File size in MB (max 10MB for images)"
    )

    @validator("content_type")
    def validate_content_type(cls, v):
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/svg+xml",
            "image/gif",
        ]
        if v not in allowed_types:
            raise ValueError(
                f"Invalid content type. Allowed: {', '.join(allowed_types)}"
            )
        return v

    @validator("image_type")
    def validate_image_type(cls, v):
        allowed_types = ["cover", "logo", "favicon"]
        if v not in allowed_types:
            raise ValueError(f"Invalid image type. Allowed: {', '.join(allowed_types)}")
        return v
