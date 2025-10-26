"""
Pydantic models for PDF processing endpoints
"""

from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, validator


# ===== Upload PDF with AI =====


class UploadPDFRequest(BaseModel):
    """Request model for PDF upload (multipart form will be converted to this)"""

    title: Optional[str] = None
    document_type: Literal["doc", "slide"] = Field(
        ...,
        description="Type of document: 'doc' for documents, 'slide' for presentations",
    )
    use_ai: bool = Field(
        default=True, description="Whether to use AI (Gemini) for content extraction"
    )
    chunk_size: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Pages per AI processing chunk (max 10 for optimal results)",
    )
    description: Optional[str] = None


class UploadPDFResponse(BaseModel):
    """Response for PDF upload"""

    success: bool
    document_id: str
    document_type: str
    title: str
    total_pages: int
    chunks_processed: int
    ai_used: bool
    ai_provider: str = "gemini"
    processing_time_seconds: float
    created_at: str
    content_preview: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "document_id": "doc_abc123",
                "document_type": "doc",
                "title": "Business Report 2025",
                "total_pages": 50,
                "chunks_processed": 5,
                "ai_used": True,
                "ai_provider": "gemini",
                "processing_time_seconds": 45.2,
                "created_at": "2025-10-25T12:00:00Z",
                "content_preview": "<div>First page content...</div>",
            }
        }


# ===== Preview Split =====


class SplitSuggestion(BaseModel):
    """Single split suggestion"""

    part: int
    title: str
    start_page: int
    end_page: int
    pages_count: int
    estimated_size_mb: float


class PreviewSplitResponse(BaseModel):
    """Response for split preview"""

    success: bool
    document_id: str
    document_title: str
    total_pages: int
    chunk_size: int
    suggested_splits: List[SplitSuggestion]
    total_parts: int
    total_estimated_size_mb: float


# ===== Split Document =====


class ManualSplitRange(BaseModel):
    """Manual split range specification"""

    title: str = Field(..., min_length=1, max_length=200)
    start_page: int = Field(..., ge=1)
    end_page: int = Field(..., ge=1)
    description: Optional[str] = None

    @validator("end_page")
    def end_must_be_greater_than_start(cls, v, values):
        if "start_page" in values and v < values["start_page"]:
            raise ValueError("end_page must be >= start_page")
        return v


class SplitDocumentRequest(BaseModel):
    """Request for splitting document"""

    mode: Literal["auto", "manual"] = Field(
        ...,
        description="Split mode: 'auto' for equal chunks, 'manual' for custom ranges",
    )
    chunk_size: Optional[int] = Field(
        default=10, ge=1, le=10, description="Pages per chunk (auto mode only, max 10)"
    )
    split_ranges: Optional[List[ManualSplitRange]] = Field(
        default=None, description="Custom split ranges (manual mode only)"
    )
    keep_original: bool = Field(
        default=True, description="Whether to keep original document"
    )

    @validator("split_ranges")
    def validate_manual_mode(cls, v, values):
        if values.get("mode") == "manual" and not v:
            raise ValueError("split_ranges required for manual mode")
        return v


class SplitDocumentPart(BaseModel):
    """Information about a split document part"""

    document_id: str
    title: str
    pages: str  # e.g., "1-10"
    pages_count: int
    r2_path: str
    file_size_mb: float
    created_at: str


class SplitDocumentResponse(BaseModel):
    """Response for document splitting"""

    success: bool
    original_document_id: str
    original_kept: bool
    split_documents: List[SplitDocumentPart]
    total_parts: int
    processing_time_seconds: float


# ===== Convert with AI =====


class PageRangeSelection(BaseModel):
    """Page range selection for partial conversion"""

    start_page: int = Field(..., ge=1, description="Starting page number (1-indexed)")
    end_page: int = Field(..., ge=1, description="Ending page number (1-indexed)")

    @validator("end_page")
    def validate_end_page(cls, v, values):
        if "start_page" in values and v < values["start_page"]:
            raise ValueError("end_page must be >= start_page")
        return v


class ConvertWithAIRequest(BaseModel):
    """Request for converting document with Gemini AI"""

    target_type: Literal["doc", "slide"] = Field(
        ..., description="Target document type"
    )
    chunk_size: int = Field(
        default=5, ge=1, le=10, description="Pages per AI processing chunk (default: 5)"
    )
    force_reprocess: bool = Field(
        default=False, description="Force reprocessing even if already AI-processed"
    )
    page_range: Optional[PageRangeSelection] = Field(
        None,
        description="Optional: Convert only specific pages (e.g., pages 1-20). If not provided, converts entire PDF",
    )


class ConvertWithAIResponse(BaseModel):
    """Response for Gemini AI conversion"""

    success: bool
    document_id: str
    title: str  # Document title (filename)
    document_type: str
    content_html: str  # HTML content for immediate use
    ai_processed: bool
    ai_provider: str = "gemini"
    chunks_processed: int
    total_pages: int
    pages_converted: Optional[str] = None  # e.g., "1-20" or "all"
    processing_time_seconds: float
    reprocessed: bool
    updated_at: str


# ===== Split Info =====


class SplitInfoSibling(BaseModel):
    """Information about sibling split part"""

    document_id: str
    title: str
    pages: str  # e.g., "11-20"


class SplitInfoDetail(BaseModel):
    """Split information details"""

    start_page: int
    end_page: int
    total_pages_in_part: int
    part_number: int
    total_parts: int


class SplitInfoResponse(BaseModel):
    """Response for split info"""

    success: bool
    document_id: str
    is_split_part: bool
    original_document_id: Optional[str] = None
    split_info: Optional[SplitInfoDetail] = None
    siblings: Optional[List[SplitInfoSibling]] = None
    can_merge: bool


# ===== Merge Documents =====


class MergedFromInfo(BaseModel):
    """Information about source document in merge"""

    document_id: str
    pages: str  # e.g., "1-10"


class MergeDocumentsRequest(BaseModel):
    """Request for merging documents"""

    document_ids: List[str] = Field(
        ..., min_items=2, description="List of document IDs to merge"
    )
    title: str = Field(..., min_length=1, max_length=200)
    keep_originals: bool = Field(
        default=False, description="Whether to keep original documents after merge"
    )


class MergeDocumentsResponse(BaseModel):
    """Response for document merge"""

    success: bool
    merged_document_id: str
    title: str
    total_pages: int
    merged_from: List[MergedFromInfo]
    originals_deleted: bool
    r2_path: str
    created_at: str
