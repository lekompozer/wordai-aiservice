"""
Pydantic Models for Book Combo System
Book combos allow grouping multiple books and selling them as a bundle.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ComboPurchaseType(str, Enum):
    """Types of combo purchases — mirrors book PurchaseType"""

    ONE_TIME = "one_time"  # 24-hour access for ALL books in combo
    FOREVER = "lifetime"  # Permanent access for ALL books in combo
    PDF_DOWNLOAD = "pdf_download"  # PDF download access for ALL books in combo


# ==============================================================================
# COMBO ACCESS CONFIG
# ==============================================================================


class ComboAccessConfig(BaseModel):
    """Pricing configuration for a combo"""

    one_time_view_points: int = Field(0, ge=0, description="Points for one-time access")
    forever_view_points: int = Field(0, ge=0, description="Points for forever access")
    download_pdf_points: Optional[int] = Field(
        None, description="Points for PDF download (null = not set)"
    )
    is_one_time_enabled: bool = Field(False)
    is_forever_enabled: bool = Field(True)
    is_download_enabled: bool = Field(False)

    @validator("download_pdf_points")
    def pdf_points_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("download_pdf_points must be >= 0")
        return v


# ==============================================================================
# COMBO STATS
# ==============================================================================


class ComboStats(BaseModel):
    """Revenue and engagement stats for a combo"""

    total_purchases: int = 0
    one_time_purchases: int = 0
    forever_purchases: int = 0
    pdf_purchases: int = 0
    total_revenue_points: int = 0
    owner_reward_points: int = 0  # 80%
    system_fee_points: int = 0  # 20%


# ==============================================================================
# COMBO BOOK ITEM (lightweight — for combo detail response)
# ==============================================================================


class ComboBookItem(BaseModel):
    """Lightweight book info shown inside a combo listing"""

    book_id: str
    title: str
    slug: str
    cover_image_url: Optional[str] = None
    is_available: bool = Field(
        True, description="False if book was unpublished/deleted"
    )


# ==============================================================================
# CREATE / UPDATE COMBO
# ==============================================================================


class CreateComboRequest(BaseModel):
    """Request body to create a new combo"""

    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    cover_image_url: Optional[str] = None
    book_ids: List[str] = Field(
        ..., min_items=2, max_items=50, description="At least 2 books required"
    )
    access_config: ComboAccessConfig

    @validator("book_ids")
    def book_ids_unique(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("book_ids must be unique")
        return v

    @root_validator
    def access_config_has_pricing(cls, values):
        cfg = values.get("access_config")
        if cfg is None:
            return values
        has_forever = cfg.is_forever_enabled and cfg.forever_view_points > 0
        has_one_time = cfg.is_one_time_enabled and cfg.one_time_view_points > 0
        if not has_forever and not has_one_time:
            raise ValueError(
                "Combo phải có ít nhất 1 hình thức giá hợp lệ: "
                "forever_view_points > 0 với is_forever_enabled=true, "
                "hoặc one_time_view_points > 0 với is_one_time_enabled=true"
            )
        return values


class UpdateComboRequest(BaseModel):
    """Request body to update an existing combo (partial update)"""

    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    cover_image_url: Optional[str] = None
    add_book_ids: Optional[List[str]] = Field(None, description="Books to add to combo")
    access_config: Optional[ComboAccessConfig] = None
    is_published: Optional[bool] = None


# ==============================================================================
# COMBO RESPONSE MODELS
# ==============================================================================


class ComboResponse(BaseModel):
    """Full combo detail response"""

    combo_id: str
    owner_user_id: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None

    book_ids: List[str]
    book_count: int
    books: List[ComboBookItem] = Field(
        default_factory=list, description="Resolved book details"
    )

    access_config: ComboAccessConfig
    stats: ComboStats = Field(default_factory=ComboStats)

    is_published: bool = True
    is_deleted: bool = False

    created_at: datetime
    updated_at: datetime


class ComboListItem(BaseModel):
    """Lightweight combo item for list views"""

    combo_id: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    book_count: int
    book_previews: List[ComboBookItem] = Field(
        default_factory=list, description="First 4 books for preview"
    )
    access_config: ComboAccessConfig
    stats: ComboStats = Field(default_factory=ComboStats)
    is_published: bool = True
    created_at: datetime


class ComboListResponse(BaseModel):
    """Paginated list of combos"""

    items: List[ComboListItem]
    total: int
    page: int
    limit: int
    total_pages: int


# ==============================================================================
# PURCHASE COMBO
# ==============================================================================


class PurchaseComboRequest(BaseModel):
    """Request to purchase a combo with points"""

    purchase_type: ComboPurchaseType = Field(
        ..., description="one_time | lifetime | pdf_download"
    )


class PurchaseComboResponse(BaseModel):
    """Response after purchasing a combo"""

    success: bool
    purchase_id: str
    combo_id: str
    purchase_type: ComboPurchaseType
    points_spent: int
    remaining_balance: int
    book_ids: List[str] = Field(description="All books now accessible")
    access_expires_at: Optional[datetime] = Field(
        None, description="Set for one_time purchases"
    )
    timestamp: datetime


# ==============================================================================
# COMBO PURCHASE RECORD (stored in combo_purchases collection)
# ==============================================================================


class ComboPurchaseItem(BaseModel):
    """Single combo purchase record in user's purchase history"""

    purchase_id: str
    combo_id: str
    combo_title: str
    combo_cover_url: Optional[str] = None
    combo_is_deleted: bool = False

    purchase_type: ComboPurchaseType
    points_spent: int
    purchased_at: datetime
    access_expires_at: Optional[datetime] = None
    access_status: str = Field(..., description="active | expired | combo_deleted")

    # Books accessible via this combo purchase
    book_count: int
    books: List[ComboBookItem] = Field(default_factory=list)


class MyComboPurchasesResponse(BaseModel):
    """Response for listing user's combo purchases"""

    purchases: List[ComboPurchaseItem]
    total: int
    page: int
    limit: int
    total_pages: int


# ==============================================================================
# COMBO ACCESS RESPONSE
# ==============================================================================


class ComboAccessResponse(BaseModel):
    """Access check result for a combo"""

    has_access: bool
    access_type: Optional[str] = Field(None, description="forever | one_time | owner")
    expires_at: Optional[datetime] = None
    can_download_pdf: bool = False
    purchase_id: Optional[str] = None


# ==============================================================================
# MY PUBLISHED COMBOS
# ==============================================================================


class MyPublishedComboItem(BaseModel):
    """Creator's view of their combo with earnings"""

    combo_id: str
    title: str
    cover_image_url: Optional[str] = None
    book_count: int
    is_published: bool
    is_deleted: bool
    access_config: ComboAccessConfig
    stats: ComboStats
    created_at: datetime
    updated_at: datetime


class MyPublishedCombosResponse(BaseModel):
    """Response for listing combos I created"""

    items: List[MyPublishedComboItem]
    total: int
    page: int
    limit: int
    total_pages: int
