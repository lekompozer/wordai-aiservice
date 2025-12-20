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

    # Folder organization
    folder_id: Optional[str] = Field(None, description="Folder ID to organize document")


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
    slide_elements: Optional[list] = Field(
        None,
        description="Overlay elements for slides only (JSON array) - format: [{slideIndex: int, elements: []}]",
    )
    slide_backgrounds: Optional[list] = Field(
        None,
        description="Background settings for slides (JSON array) - format: [{slideIndex: int, background: {type, value, ...}}]",
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
    slide_elements: Optional[list] = None  # ✅ Overlay elements for slides (JSON array)
    slide_backgrounds: Optional[list] = (
        None  # ✅ Background settings for slides (JSON array)
    )


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
    folder_id: Optional[str] = None


# ============ FOLDER MODELS ============


class FolderCreate(BaseModel):
    """Model to create new folder"""

    name: str = Field(..., description="Folder name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Folder description")
    parent_id: Optional[str] = Field(
        None, description="Parent folder ID for nested folders"
    )


class FolderUpdate(BaseModel):
    """Model to update folder"""

    name: Optional[str] = Field(
        None, description="Folder name", min_length=1, max_length=255
    )
    description: Optional[str] = Field(None, description="Folder description")


class FolderResponse(BaseModel):
    """Model for folder response"""

    id: str = Field(..., alias="folder_id")
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    class Config:
        populate_by_name = True


class FolderWithDocuments(BaseModel):
    """Model for folder with its documents"""

    folder_id: Optional[str] = None  # None for root/ungrouped documents
    folder_name: Optional[str] = None
    folder_description: Optional[str] = None
    document_count: int
    documents: list[DocumentListItem]


class DocumentsByFolderResponse(BaseModel):
    """Model for all documents organized by folders"""

    folders: list[FolderWithDocuments]
    total_documents: int
