"""
Pydantic Models for Guide Chapters
Phase 1: Chapter organization and nested structure
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChapterCreate(BaseModel):
    """Request model to add chapter to guide"""

    title: str = Field(..., min_length=1, max_length=200, description="Chapter title")
    slug: Optional[str] = Field(
        None,
        max_length=200,
        description="Chapter URL slug (will be auto-normalized to a-z0-9- format)",
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
    is_preview_free: bool = Field(
        default=False,
        description="Allow free preview on Community Books (no purchase required)",
    )

    # Content fields (for inline chapters)
    content_source: Optional[str] = Field(
        default="inline",
        description="Content storage: 'inline' (in chapter) or 'document' (linked document)",
    )
    content_html: Optional[str] = Field(
        default=None, description="Chapter content in HTML format (for inline chapters)"
    )
    content_json: Optional[Dict[str, Any]] = Field(
        default=None, description="Chapter content in JSON format (TipTap editor)"
    )

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
    slug: Optional[str] = Field(
        None, max_length=200, description="Chapter URL slug (will be auto-normalized)"
    )
    description: Optional[str] = Field(
        None, max_length=5000, description="Chapter description (for SEO and preview)"
    )
    parent_id: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=0)
    is_published: Optional[bool] = None
    is_preview_free: Optional[bool] = Field(
        None, description="Allow free preview on Community Books"
    )


class ChapterContentUpdate(BaseModel):
    """Request model to update chapter content"""

    content_html: str = Field(..., description="Chapter content in HTML format")
    content_json: Optional[Dict[str, Any]] = Field(
        default=None, description="Chapter content in JSON format (TipTap editor)"
    )


class ConvertDocumentToChapterRequest(BaseModel):
    """Request to convert document to chapter"""

    book_id: str = Field(..., description="Target book ID")
    title: Optional[str] = Field(
        None, description="Chapter title (uses document name if not provided)"
    )
    order_index: int = Field(default=0, ge=0, description="Position in chapter list")
    parent_id: Optional[str] = Field(None, description="Parent chapter for nesting")
    copy_content: bool = Field(
        default=True,
        description="If True, copy content to chapter (inline). If False, link to document.",
    )


class ChapterReorder(BaseModel):
    """Request model for single chapter reorder"""

    chapter_id: str
    parent_id: Optional[str] = None
    order_index: int = Field(default=0, ge=0)


class ChapterReorderBulk(BaseModel):
    """Bulk reorder request"""

    updates: List[ChapterReorder]


class ChapterBulkUpdateItem(BaseModel):
    """Single chapter update in bulk operation"""

    chapter_id: str = Field(..., description="Chapter ID to update")
    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="New chapter title"
    )
    slug: Optional[str] = Field(
        None, pattern="^[a-z0-9-]+$", description="New chapter slug"
    )
    description: Optional[str] = Field(
        None, max_length=5000, description="New chapter description"
    )
    parent_id: Optional[str] = Field(
        None, description="New parent chapter ID (null for root)"
    )
    order_index: Optional[int] = Field(
        None, ge=0, description="New position at current level"
    )


class ChapterBulkUpdate(BaseModel):
    """Bulk update chapters (title, slug, order, parent)"""

    updates: List[ChapterBulkUpdateItem] = Field(
        ..., min_items=1, description="List of chapter updates"
    )


class ChapterResponse(BaseModel):
    """Response model for chapter"""

    chapter_id: str
    book_id: str
    title: str
    slug: str
    description: Optional[str] = Field(
        default=None, description="Chapter description (for SEO and preview)"
    )
    document_id: Optional[str] = None
    parent_id: Optional[str] = None
    order_index: int
    depth: int
    is_published: bool
    is_preview_free: bool = Field(
        default=False, description="Free preview on Community Books"
    )
    created_at: datetime
    updated_at: datetime

    # Content fields (when loading chapter content)
    content: Optional[str] = Field(
        default=None,
        description="Chapter content in HTML format (alias for content_html)",
    )
    content_html: Optional[str] = Field(
        default=None,
        description="Chapter content in HTML format (from document or inline)",
    )
    content_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Chapter content in JSON format (TipTap editor format)",
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Name of linked document (if content_source='document')",
    )


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


class TogglePreviewRequest(BaseModel):
    """Request to toggle chapter preview status"""

    is_preview_free: bool = Field(
        description="Set to true to allow free preview on Community Books"
    )
