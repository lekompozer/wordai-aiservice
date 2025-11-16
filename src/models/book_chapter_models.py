"""
Pydantic Models for Guide Chapters
Phase 1: Chapter organization and nested structure
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class ChapterCreate(BaseModel):
    """Request model to add chapter to guide"""

    title: str = Field(..., min_length=1, max_length=200, description="Chapter title")
    slug: Optional[str] = Field(
        None,
        pattern="^[a-z0-9-]+$",
        description="Chapter URL slug (auto-generated from title if not provided)",
    )
    document_id: Optional[str] = Field(
        None,
        description="Document ID to use as chapter content (can create empty chapter)",
    )
    parent_id: Optional[str] = Field(
        None, description="Parent chapter ID for nesting (null for root)"
    )
    order_index: int = Field(
        default=0, ge=0, description="Display order at current level"
    )
    order: Optional[int] = Field(
        None, ge=0, description="Alias for order_index (for backward compatibility)"
    )
    is_published: bool = Field(default=True, description="Published status")

    @property
    def get_order_index(self) -> int:
        """Get order index, preferring order_index but falling back to order"""
        return (
            self.order
            if self.order is not None and self.order_index == 0
            else self.order_index
        )


class ChapterUpdate(BaseModel):
    """Request model to update chapter"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, pattern="^[a-z0-9-]+$")
    parent_id: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=0)
    is_published: Optional[bool] = None


class ChapterReorder(BaseModel):
    """Request model for single chapter reorder"""

    chapter_id: str
    parent_id: Optional[str] = None
    order_index: int = Field(default=0, ge=0)


class ChapterReorderBulk(BaseModel):
    """Bulk reorder request"""

    updates: List[ChapterReorder]


class ChapterResponse(BaseModel):
    """Response model for chapter"""

    chapter_id: str
    book_id: str
    title: str
    slug: str
    document_id: Optional[str] = None
    parent_id: Optional[str] = None
    order_index: int
    depth: int
    is_published: bool
    created_at: datetime
    updated_at: datetime


class ChapterTreeNode(BaseModel):
    """Chapter with nested children (tree structure)"""

    chapter_id: str
    title: str
    slug: str
    order_index: int
    depth: int
    is_published: bool
    document_id: Optional[str] = None
    children: List["ChapterTreeNode"] = []


# Enable forward references for recursive model
ChapterTreeNode.model_rebuild()


class ChapterListResponse(BaseModel):
    """Response for chapter listing"""

    chapters: List[ChapterTreeNode]
    total_chapters: int
