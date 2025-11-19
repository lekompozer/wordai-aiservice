"""
Pydantic Models for User Guide System
Phase 1: Guide metadata and settings
"""

from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List, Dict, Any
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
    total_saves: int = 0  # NEW: Number of users who saved/bookmarked this book
    average_rating: float = 0.0
    rating_count: int = 0
    version: str = "1.0.0"
    published_at: Optional[datetime] = None


class BookStats(BaseModel):
    """Book revenue statistics"""

    total_revenue_points: int = 0  # Total points collected (100%)
    owner_reward_points: int = 0  # Owner's share (80%)
    system_fee_points: int = 0  # System's share (20%)

    # Purchase breakdown by type (NEW)
    one_time_purchases: int = 0  # Count of one-time purchases
    forever_purchases: int = 0  # Count of forever purchases
    pdf_downloads: int = 0  # Count of PDF downloads

    one_time_revenue: int = 0  # Revenue from one-time purchases
    forever_revenue: int = 0  # Revenue from forever purchases
    pdf_revenue: int = 0  # Revenue from PDF downloads


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

    # Authors (NEW - Support multiple authors)
    authors: List[str] = Field(
        default_factory=list,
        description="List of author IDs (e.g., ['@john_doe', '@jane_smith']). Empty for non-community books.",
    )

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

    # Trash/Soft Delete (NEW)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

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

    # Authors (Support multiple authors - at least 1 required)
    # BACKWARD COMPATIBILITY: Accept either 'author_id' (legacy) or 'authors' (new)
    authors: Optional[List[str]] = Field(
        None,
        min_items=1,
        max_items=5,
        description="List of author IDs (e.g., ['@john_doe', '@jane_smith']). Use check endpoint to verify availability first.",
    )

    # Legacy field for backward compatibility
    author_id: Optional[str] = Field(
        None,
        description="(DEPRECATED) Single author ID. Use 'authors' array instead. Will be converted to authors=[author_id]",
    )

    # Only for NEW authors (if any author_id doesn't exist yet)
    # Format: {"@new_author": {"name": "...", "bio": "...", "avatar_url": "..."}}
    new_authors: Optional[dict] = Field(
        default_factory=dict,
        description="Data for new authors. Keys are author_ids, values are author profile data.",
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

    @model_validator(mode="before")
    @classmethod
    def validate_authors_backward_compat(cls, data: Any) -> Any:
        """
        Backward compatibility validator:
        - If 'authors' provided → use it
        - If 'author_id' provided → convert to authors=[author_id]
        - If both provided → 'authors' takes precedence
        - If neither provided → error
        """
        if isinstance(data, dict):
            authors = data.get("authors")
            author_id = data.get("author_id")

            # If authors already provided, use it
            if authors is not None:
                if not authors:  # Empty list
                    raise ValueError("Authors list cannot be empty")
                return data

            # Fallback to author_id (legacy)
            if author_id:
                data["authors"] = [author_id]
                return data

            # Neither provided
            raise ValueError(
                "Either 'authors' (array) or 'author_id' (string) is required"
            )

        return data

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
    tags: List[str] = Field(default_factory=list)  # Always array (not null)
    difficulty_level: Optional[str] = "beginner"

    # Pricing (if point_based)
    forever_view_points: int = 0  # Main price to display

    # Stats
    total_views: int = 0
    total_purchases: int = 0
    total_saves: int = 0  # NEW: Number of users who saved/bookmarked
    average_rating: float = 0.0
    rating_count: int = 0

    # Author - Use PreviewAuthor for consistency
    author: Optional[Dict[str, Any]] = None  # {"author_id": "@user", "name": "Name"}

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


# ============ TRASH MODELS (NEW) ============


class TrashBookItem(BaseModel):
    """Trash book item for listing"""

    book_id: str
    title: str
    slug: str
    deleted_at: datetime
    deleted_by: str
    chapters_count: int = 0
    can_restore: bool = True
    # Published book info (for DELETE_PROTECTION_FLOW)
    is_published: bool = False  # Still on Community marketplace
    total_purchases: int = 0  # Total number of purchases
    forever_purchases: int = 0  # Forever access purchases
    one_time_purchases: int = 0  # One-time purchases
    pdf_downloads: int = 0  # PDF download purchases


class TrashListResponse(BaseModel):
    """Response for trash listing with pagination"""

    items: List[TrashBookItem]
    total: int
    page: int
    limit: int
    total_pages: int


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


# ==============================================================================
# MY PUBLISHED BOOKS MODELS (For creators to track earnings)
# ==============================================================================


class MyPublishedBookStats(BaseModel):
    """Detailed stats for my published books"""

    # Purchase stats
    total_one_time_purchases: int = Field(0, description="Total one-time purchases")
    total_forever_purchases: int = Field(0, description="Total forever purchases")
    total_pdf_downloads: int = Field(0, description="Total PDF downloads")
    total_purchases: int = Field(0, description="Total all purchases (sum)")

    # Revenue stats (in points)
    total_revenue_points: int = Field(0, description="Total revenue collected (100%)")
    owner_reward_points: int = Field(0, description="Owner's share (80%)")
    system_fee_points: int = Field(0, description="System fee (20%)")
    pending_transfer_points: int = Field(
        0, description="Points not yet transferred to wallet"
    )

    # Engagement stats
    total_views: int = Field(0, description="Total book views")
    total_readers: int = Field(0, description="Unique readers/buyers")
    average_rating: float = Field(0.0, ge=0, le=5, description="Average rating (0-5)")
    rating_count: int = Field(0, description="Total ratings")


class MyPublishedBookResponse(BaseModel):
    """Response model for creator's published book with earnings"""

    book_id: str
    title: str
    slug: str
    description: Optional[str] = None

    # Author info
    author_name: Optional[str] = Field(None, description="Author display name")
    authors: List[str] = Field(default_factory=list, description="List of author IDs")

    # Community config
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    difficulty_level: Optional[str] = None
    cover_image_url: Optional[str] = None

    # Pricing
    access_config: Optional[AccessConfig] = None

    # Stats
    stats: MyPublishedBookStats

    # Trash status (DELETE_PROTECTION_FLOW)
    is_deleted: bool = Field(False, description="Book in trash but still on Community")

    # Metadata
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MyPublishedBooksListResponse(BaseModel):
    """Response for list of my published books"""

    books: List[MyPublishedBookResponse]
    total: int
    pagination: dict


class TransferEarningsRequest(BaseModel):
    """Request to transfer book earnings to user wallet"""

    book_id: str = Field(..., description="Book ID to transfer earnings from")
    amount_points: Optional[int] = Field(
        None, gt=0, description="Amount to transfer (optional, default: all pending)"
    )


class TransferEarningsResponse(BaseModel):
    """Response after transferring earnings"""

    book_id: str
    transferred_points: int
    new_wallet_balance: int
    transaction_id: str
    timestamp: datetime


class TopEarningBook(BaseModel):
    """Top earning book info"""

    book_id: str
    title: str
    revenue: int


class EarningsBreakdown(BaseModel):
    """Revenue breakdown by access type"""

    one_time_revenue: int = Field(0, description="Revenue from one-time purchases")
    forever_revenue: int = Field(0, description="Revenue from forever purchases")
    pdf_revenue: int = Field(0, description="Revenue from PDF downloads")


class EarningsSummaryResponse(BaseModel):
    """Earnings summary for all published books"""

    total_books_published: int = Field(0, description="Total number of published books")
    total_revenue: int = Field(0, description="Total revenue from all books (100%)")
    owner_reward: int = Field(0, description="Owner's share (80% of revenue)")
    platform_fee: int = Field(0, description="Platform fee (20% of revenue)")
    breakdown: EarningsBreakdown = Field(
        default_factory=EarningsBreakdown, description="Revenue breakdown by type"
    )
    top_earning_book: Optional[TopEarningBook] = Field(
        None, description="Top earning book"
    )


# ==============================================================================
# BOOK PURCHASE MODELS (Point-based purchases)
# ==============================================================================


class PurchaseType(str, Enum):
    """Types of book purchases"""

    ONE_TIME = "one_time"  # One-time view access
    FOREVER = "forever"  # Permanent view access
    PDF_DOWNLOAD = "pdf_download"  # PDF download


class PurchaseBookRequest(BaseModel):
    """Request to purchase book access"""

    purchase_type: PurchaseType = Field(..., description="Type of purchase")


class PurchaseBookResponse(BaseModel):
    """Response after purchasing book"""

    success: bool
    purchase_id: str
    book_id: str
    purchase_type: PurchaseType
    points_spent: int
    remaining_balance: int
    access_expires_at: Optional[datetime] = Field(
        None, description="Expiry for one-time purchases"
    )
    timestamp: datetime


class BookAccessResponse(BaseModel):
    """Response for user's book access status"""

    has_access: bool = Field(False, description="Whether user has any access")
    access_type: Optional[str] = Field(
        None, description="Type of access: one_time | forever | owner"
    )
    expires_at: Optional[datetime] = Field(None, description="Access expiry (one-time)")
    can_download_pdf: bool = Field(False, description="Can download PDF")


class MyPurchaseItem(BaseModel):
    """Single purchase item in my purchases list"""

    purchase_id: str
    book_id: str
    book_title: str
    book_slug: str
    book_cover_url: Optional[str] = None
    book_is_deleted: bool = Field(
        False, description="Book is in trash (still accessible)"
    )
    purchase_type: PurchaseType
    points_spent: int
    purchased_at: datetime
    access_expires_at: Optional[datetime] = Field(
        None, description="For one-time purchases"
    )
    access_status: str = Field(
        ..., description="active | expired | book_deleted_unpublished"
    )


class MyPurchasesResponse(BaseModel):
    """Response for listing user's purchases"""

    purchases: List[MyPurchaseItem]
    total: int
    page: int
    limit: int
    total_pages: int
    is_owner: bool = Field(False, description="Is book owner")
    purchase_details: Optional[dict] = Field(None, description="Purchase info if any")


# ==============================================================================
# BOOK PREVIEW MODELS (Community Books Preview Page)
# ==============================================================================


class PreviewAuthor(BaseModel):
    """Author info for book preview"""

    author_id: str = Field(..., description="Author ID (e.g., @username)")
    name: str = Field(..., description="Author display name")
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class PreviewChapterItem(BaseModel):
    """Chapter item in preview (table of contents)"""

    chapter_id: str
    title: str
    slug: str
    order_index: int
    depth: int = Field(default=0, description="Nesting level (0=root, 1=sub, 2=subsub)")
    is_preview_free: bool = Field(
        default=False, description="Can read without purchase"
    )


class PreviewStats(BaseModel):
    """Book stats for preview page"""

    total_views: int = 0
    total_purchases: int = 0
    forever_purchases: int = 0
    one_time_purchases: int = 0
    pdf_downloads: int = 0
    total_saves: int = 0  # NEW: Number of users who saved/bookmarked this book
    average_rating: float = 0.0
    rating_count: int = 0


class BookPreviewResponse(BaseModel):
    """Response for book preview page (public, no auth)"""

    # Basic info
    book_id: str
    title: str
    slug: str
    description: Optional[str] = None

    # Visual
    cover_image_url: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None

    # Author (MUST be object, not null)
    author: PreviewAuthor = Field(..., description="Book author info")
    authors: List[str] = Field(
        default_factory=list, description="All author IDs (for multi-author books)"
    )

    # Community metadata (MUST be array, not null)
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list, description="Tags array (not null)")
    difficulty_level: Optional[str] = None

    # Access config (can be null for free books)
    access_config: Optional[AccessConfig] = Field(
        None, description="null for public books"
    )

    # Chapters (table of contents)
    chapters: List[PreviewChapterItem] = Field(
        default_factory=list, description="Chapter list for TOC"
    )

    # Stats (MUST be object, not null)
    stats: PreviewStats = Field(
        default_factory=PreviewStats, description="Book stats (use 0 if no data)"
    )

    # Metadata
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # User access (if authenticated)
    user_access: Optional[dict] = Field(
        None,
        description="User's purchase status if logged in: {has_access, access_type, expires_at}",
    )
