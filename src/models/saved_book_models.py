"""
Saved Books Models - User's saved/bookmarked books
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SaveBookRequest(BaseModel):
    """Request to save a book"""

    book_id: str = Field(..., description="Book ID to save")


class SaveBookResponse(BaseModel):
    """Response after saving a book"""

    success: bool = True
    message: str
    book_id: str
    saved_at: datetime


class SavedBookItem(BaseModel):
    """Saved book item in list"""

    book_id: str
    title: str
    slug: str
    cover_image_url: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    # Author info
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    author_avatar: Optional[str] = None

    # Stats
    total_views: int = 0
    total_saves: int = 0
    average_rating: float = 0.0

    # When user saved it
    saved_at: datetime

    # Book metadata
    published_at: Optional[datetime] = None


class SavedBooksResponse(BaseModel):
    """List of saved books"""

    books: List[SavedBookItem]
    total: int
    skip: int = 0
    limit: int = 20
    filters: dict = Field(
        default_factory=dict,
        description="Applied filters: {category, tags}",
    )


class UnsaveBookResponse(BaseModel):
    """Response after removing saved book"""

    success: bool = True
    message: str
    book_id: str
