"""
Task Models for Queue-based Processing
Các model task cho xử lý dựa trên Queue
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from src.models.unified_models import Industry, Language


class ProductsExtractionTask(BaseModel):
    """Task for extracting products/services data via queue"""

    task_id: str = Field(default_factory=lambda: f"extract_{uuid.uuid4().hex[:12]}")
    company_id: str
    r2_url: str
    industry: Industry
    language: Language = Language.VIETNAMESE
    file_metadata: Dict[str, Any]
    company_info: Optional[Dict[str, Any]] = None  # Add company_info field
    target_categories: Optional[List[str]] = None
    callback_url: Optional[str] = None
    upload_to_qdrant: bool = True
    priority: int = 2  # High priority for products/services extraction
    max_retries: int = 3  # Add max_retries field
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DocumentProcessingTask(BaseModel):
    """Task for processing company documents via queue (FILE UPLOAD)"""

    task_id: str = Field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}")
    company_id: str
    r2_url: str
    data_type: str  # document, image, video, audio, other
    industry: Industry
    metadata: Dict[str, Any]
    language: Language
    upload_to_qdrant: bool = True
    callback_url: Optional[str] = None
    priority: int = 1  # Normal priority for documents
    max_retries: int = 3  # Add max_retries field
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExtractionProcessingTask(BaseModel):
    """Task for AI extraction processing via queue (EXTRACTION API)"""

    task_id: str
    company_id: str
    r2_url: str
    file_name: str
    file_type: Optional[str] = "text/plain"
    file_size: Optional[int] = 0
    industry: Industry
    language: Language  # Language from backend request, no default
    data_type: str  # products, services, or auto
    target_categories: List[str] = ["products", "services"]
    callback_url: Optional[str] = None
    company_info: Dict[str, Any] = {}
    created_at: datetime
    processing_metadata: Dict[str, Any] = {}


class TaskResponse(BaseModel):
    """Standard response for queued tasks"""

    task_id: str
    status: str = "queued"
    message: str
    company_id: str
    estimated_processing_time: str = "2-10 minutes"
    status_check_url: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExtractionTaskResponse(TaskResponse):
    """Response for extraction tasks"""

    extraction_type: str = "products_services"
    industry: str


class FileUploadTaskResponse(TaskResponse):
    """Response for file upload tasks"""

    file_type: str
    data_type: str


class StorageProcessingTask(BaseModel):
    """Task for storage processing only - handles Qdrant upload and backend callbacks"""

    task_id: str
    company_id: str
    structured_data: Dict[str, Any]  # AI extraction results from ExtractionWorker
    metadata: Dict[str, Any]  # Original file metadata + extraction metadata
    callback_url: Optional[str] = None
    original_extraction_task_id: str  # Reference to original ExtractionProcessingTask
    created_at: datetime = Field(default_factory=datetime.utcnow)
