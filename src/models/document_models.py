"""
Pydantic models for AI Service Document Processing API
Phase 1 - Clean and focused models
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class DocumentStatus(Enum):
    """Document processing status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# ✅ A. Document Processing Request Model
class DocumentProcessRequest(BaseModel):
    """Request model for processing a document"""
    document_id: str = Field(..., description="Unique document identifier")
    user_id: str = Field(..., description="User identifier")
    r2_key: str = Field(..., description="R2 object key for the document")
    file_name: str = Field(..., description="Original filename") 
    content_type: str = Field(..., description="MIME type of the file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    callback_url: str = Field(..., description="Backend callback URL")
    processing_options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional processing settings")

class DocumentProcessResponse(BaseModel):
    """Response model for document processing initiation"""
    success: bool = Field(..., description="Whether the request was accepted")
    task_id: str = Field(..., description="Processing task identifier")
    document_id: str
    user_id: str
    status: str = Field(default="queued", description="Initial status")
    message: str = Field(default="Document processing initiated")
    estimated_time: Optional[int] = Field(None, description="Estimated processing time in seconds")

# ✅ B. Processing Result Models
class ProcessingResult(BaseModel):
    """Detailed processing result"""
    chunks_created: int = Field(..., description="Number of chunks created")
    vectors_stored: int = Field(..., description="Number of vectors stored in Qdrant")
    collection_name: str = Field(..., description="Qdrant collection name")
    document_length: int = Field(..., description="Original document length in characters")
    processing_time: float = Field(..., description="Total processing time in seconds")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")

class CallbackPayload(BaseModel):
    """Payload sent to backend callback"""
    document_id: str
    user_id: str
    task_id: str
    status: str = Field(..., description="completed, failed, or error")
    processing_details: Optional[ProcessingResult] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ✅ C. Document Search Models
class DocumentSearchRequest(BaseModel):
    """Request for searching user documents"""
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="Search query")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum results to return")
    score_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum similarity score")
    document_ids: Optional[List[str]] = Field(None, description="Filter by specific document IDs")

class DocumentSearchResult(BaseModel):
    """Individual search result"""
    chunk_id: str
    document_id: str
    content: str = Field(..., description="Chunk content")
    score: float = Field(..., description="Similarity score")
    chunk_index: int = Field(..., description="Position in original document")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentSearchResponse(BaseModel):
    """Response for document search"""
    success: bool = True
    user_id: str
    query: str
    results: List[DocumentSearchResult] = Field(default_factory=list)
    total_found: int = Field(..., description="Number of results found")
    processing_time: float = Field(..., description="Search processing time")

# ✅ D. Document Management Models  
class DocumentDeleteRequest(BaseModel):
    """Request to delete a document"""
    user_id: str = Field(..., description="User identifier")
    document_id: str = Field(..., description="Document to delete")

class DocumentDeleteResponse(BaseModel):
    """Response for document deletion"""
    success: bool
    user_id: str
    document_id: str
    message: str
    chunks_deleted: Optional[int] = None

class UserDocumentsResponse(BaseModel):
    """Response for listing user documents"""
    success: bool = True
    user_id: str
    collection_info: Dict[str, Any] = Field(default_factory=dict)
    document_count: int = 0
    total_chunks: int = 0
    document_ids: List[str] = Field(default_factory=list)

# ✅ E. Health Check Models
class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="healthy, degraded, or unhealthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool] = Field(default_factory=dict, description="Status of each service")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
    version: str = Field(default="1.0.0")

# ✅ F. Error Response Models
class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Human readable error message")
    error_code: Optional[str] = Field(None, description="Machine readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ✅ G. Task Status Models
class TaskStatusResponse(BaseModel):
    """Response for checking task status"""
    success: bool = True
    task_id: str
    document_id: str
    user_id: str
    status: str = Field(..., description="queued, processing, completed, failed")
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None
    result: Optional[ProcessingResult] = None
    error_message: Optional[str] = None

# ✅ H. Validation Functions
def validate_file_type(mime_type: str) -> bool:
    """Check if file type is supported"""
    supported_types = {
        'text/plain', 'text/markdown', 'text/csv',
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/json'
    }
    return mime_type in supported_types

def validate_file_size(file_size: int, max_size: int = 100 * 1024 * 1024) -> bool:
    """Check if file size is within limits (default 100MB)"""
    return 0 < file_size <= max_size

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage"""
    import re
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + '.' + ext if ext else name[:255]
    return filename

def generate_document_id() -> str:
    """Generate unique document ID"""
    import uuid
    return f"doc_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"

def generate_chunk_id(document_id: str, chunk_index: int) -> str:
    """Generate unique chunk ID"""
    return f"{document_id}_chunk_{chunk_index:03d}"
