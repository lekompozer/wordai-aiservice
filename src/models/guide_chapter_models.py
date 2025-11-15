"""
Pydantic Models for Guide Chapters
Phase 1: Chapter organization and nested structure
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class ChapterCreate(BaseModel):
    """Request model to add chapter to guide"""

    document_id: str = Field(..., description="Document ID to use as chapter")
    parent_chapter_id: Optional[str] = Field(
        None, description="Parent chapter for nesting"
    )
    order: int = Field(..., ge=1, description="Display order")
    title: Optional[str] = Field(
        None, max_length=200, description="Override document title"
    )
    slug: str = Field(..., min_length=1, max_length=100, description="Chapter URL slug")
    icon: Optional[str] = Field(
        default="📘", max_length=10, description="Emoji or icon"
    )
    is_visible: bool = Field(default=True, description="Show in navigation")
    is_expanded: bool = Field(default=True, description="Default expanded state")

    @validator("slug")
    def validate_slug(cls, v):
        """Ensure slug is URL-safe"""
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return v


class ChapterUpdate(BaseModel):
    """Request model to update chapter"""

    parent_chapter_id: Optional[str] = None
    order: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=200)
    icon: Optional[str] = Field(None, max_length=10)
    is_visible: Optional[bool] = None
    is_expanded: Optional[bool] = None


class ChapterReorder(BaseModel):
    """Request model for single chapter reorder"""

    chapter_id: str
    order: int = Field(..., ge=1)
    parent_chapter_id: Optional[str] = None


class ChapterReorderBulk(BaseModel):
    """Bulk reorder request"""

    chapters: List[ChapterReorder]


class ChapterResponse(BaseModel):
    """Response model for chapter"""

    chapter_id: str
    guide_id: str
    document_id: str
    parent_chapter_id: Optional[str] = None
    order: int
    depth: int
    title: str
    slug: str
    icon: str = "📘"
    is_visible: bool = True
    is_expanded: bool = True
    added_at: datetime
    updated_at: datetime


class ChapterTreeNode(BaseModel):
    """Chapter with nested children (tree structure)"""

    chapter_id: str
    title: str
    slug: str
    icon: str
    order: int
    depth: int
    is_visible: bool
    document_id: str
    children: List["ChapterTreeNode"] = []


# Enable forward references for recursive model
ChapterTreeNode.update_forward_refs()


class ChapterListResponse(BaseModel):
    """Response for chapter listing"""

    chapters: List[ChapterTreeNode]
    total_chapters: int
