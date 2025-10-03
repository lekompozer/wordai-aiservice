"""
Document Editor Models
Pydantic models for document management and auto-save system
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DocumentCreate(BaseModel):
    """Model để tạo document mới"""

    file_id: str = Field(..., description="ID của file gốc trong user_files")
    title: str = Field(..., description="Tên tài liệu")
    content_html: str = Field(..., description="Nội dung HTML từ Tiptap editor")
    content_text: str = Field(..., description="Nội dung plain text để search")
    original_r2_url: str = Field(..., description="URL file gốc trên R2")
    original_file_type: str = Field(..., description="Loại file gốc: docx, pdf, txt")


class DocumentUpdate(BaseModel):
    """Model để update document"""

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


class DocumentListItem(BaseModel):
    """Model cho danh sách documents"""

    document_id: str
    title: str
    last_saved_at: datetime
    last_opened_at: Optional[datetime] = None
    version: int
    file_size_bytes: int
