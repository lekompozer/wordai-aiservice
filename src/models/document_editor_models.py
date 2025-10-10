"""
Document Editor Models
Pydantic models for document management and auto-save system
Supports both file-based documents and created-from-scratch documents
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DocumentCreate(BaseModel):
    """Model để tạo document mới - hỗ trợ cả file-based và created"""

    # File reference (optional - only for file-based documents)
    file_id: Optional[str] = Field(None, description="ID của file gốc (nếu từ upload)")
    original_r2_url: Optional[str] = Field(None, description="URL file gốc trên R2")
    original_file_type: Optional[str] = Field(
        None, description="Loại file gốc: docx, pdf, txt"
    )

    # Document metadata (required for all)
    title: str = Field(..., description="Tên tài liệu")
    content_html: str = Field("", description="Nội dung HTML từ Tiptap editor")
    content_text: str = Field("", description="Nội dung plain text để search")

    # Source tracking
    source_type: str = Field(
        "file", description="Nguồn: 'file' (từ upload) hoặc 'created' (tạo mới)"
    )
    document_type: Optional[str] = Field(
        None, description="Loại document: 'doc', 'slide', 'note' (chỉ cho created)"
    )


class DocumentUpdate(BaseModel):
    """Model để update document"""

    title: Optional[str] = Field(None, description="Tiêu đề tài liệu (optional)")
    content_html: str = Field(..., description="Nội dung HTML đã chỉnh sửa")
    content_text: Optional[str] = Field(
        None, description="Nội dung plain text (optional)"
    )
    is_auto_save: bool = Field(
        False, description="True = auto-save, False = manual save"
    )


class DocumentResponse(BaseModel):
    """Model response trả về frontend"""

    document_id: str
    title: str
    content_html: str
    version: int
    last_saved_at: datetime
    file_size_bytes: int
    auto_save_count: int
    manual_save_count: int
    source_type: str = "file"  # "file" | "created"
    document_type: Optional[str] = None  # "doc" | "slide" | "note"
    file_id: Optional[str] = None  # Có thể null nếu là created document


class DocumentListItem(BaseModel):
    """Model cho danh sách documents"""

    document_id: str
    title: str
    last_saved_at: datetime
    last_opened_at: Optional[datetime] = None
    version: int
    file_size_bytes: int
    source_type: str = "file"
    document_type: Optional[str] = None
