"""
Software Lab Pydantic Models
Models cho Software Lab System - 19 endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ========================================
# ENUMS
# ========================================


class LabCategory(str, Enum):
    """Template category"""

    WEB = "web"
    MOBILE = "mobile"
    GAME = "game"


class LabDifficulty(str, Enum):
    """Template difficulty level"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class FileType(str, Enum):
    """File type"""

    FILE = "file"
    FOLDER = "folder"


class LabLanguage(str, Enum):
    """Programming language"""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    JSON = "json"
    MARKDOWN = "markdown"
    PLAINTEXT = "plaintext"


# ========================================
# LAB FILE MODELS
# ========================================


class LabFile(BaseModel):
    """Lab file (code or asset)"""

    id: str
    path: str
    content: Optional[str] = None  # For code files (text)
    url: Optional[str] = None  # For binary files (R2 URL)
    language: str
    type: FileType = FileType.FILE
    size_bytes: int = 0
    updated_at: Optional[str] = None


class LabFileCreate(BaseModel):
    """Create new file in project"""

    path: str = Field(..., min_length=1, max_length=500)
    type: FileType = FileType.FILE
    content: Optional[str] = None  # For text files
    language: Optional[str] = None  # Auto-detect if not provided


class LabFileSave(BaseModel):
    """Save file content (auto-save)"""

    content: str
    last_modified: Optional[str] = None  # For conflict detection


# ========================================
# PROJECT MODELS
# ========================================


class CreateProjectRequest(BaseModel):
    """Create new project from template"""

    name: str = Field(..., min_length=1, max_length=100)
    template: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(None, max_items=10)


class UpdateProjectRequest(BaseModel):
    """Update project metadata"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(None, max_items=10)
    thumbnail_url: Optional[str] = None


class ProjectListItem(BaseModel):
    """Project item in list view"""

    id: str
    name: str
    template: str
    description: str
    thumbnail_url: Optional[str] = None
    file_count: int
    last_modified: str
    created_at: str


class ProjectMetadata(BaseModel):
    """Project metadata"""

    file_count: int
    total_lines: int
    languages: List[str]


class ProjectDetail(BaseModel):
    """Full project detail with all files"""

    id: str
    name: str
    template: str
    description: str
    user_id: str
    files: List[LabFile]
    metadata: ProjectMetadata
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    """Paginated project list"""

    projects: List[ProjectListItem]
    total: int
    page: int
    total_pages: int


class CloneProjectRequest(BaseModel):
    """Clone project request"""

    new_name: Optional[str] = Field(None, max_length=100)


# ========================================
# TEMPLATE MODELS
# ========================================


class GuideStep(BaseModel):
    """Template guide step"""

    step: int
    title: str
    description: str
    files_to_edit: List[str]


class TemplateListItem(BaseModel):
    """Template item in gallery"""

    id: str
    name: str
    description: str
    thumbnail_url: Optional[str] = None
    category: LabCategory
    difficulty: LabDifficulty
    tags: List[str]
    file_count: int
    estimated_time_minutes: int


class TemplateFile(BaseModel):
    """Template file"""

    path: str
    content: str
    language: str
    is_editable: bool = True


class TemplateDetail(BaseModel):
    """Full template detail"""

    id: str
    name: str
    description: str
    category: LabCategory
    difficulty: LabDifficulty
    tags: List[str]
    files: List[TemplateFile]
    guide_steps: List[GuideStep]


class TemplateListResponse(BaseModel):
    """Template gallery response"""

    templates: List[TemplateListItem]


class CreateFromTemplateRequest(BaseModel):
    """Create project from template"""

    template_id: str
    project_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


# ========================================
# FILE MANAGEMENT MODELS
# ========================================


class FileTreeResponse(BaseModel):
    """File tree structure (without content)"""

    files: List[LabFile]


class FileContentResponse(BaseModel):
    """Single file content"""

    id: str
    path: str
    content: Optional[str] = None  # Text content
    url: Optional[str] = None  # Binary file URL
    language: str
    updated_at: str


class CreateFileResponse(BaseModel):
    """Response after creating file"""

    file: LabFile
    project_updated_at: str


class SaveFileResponse(BaseModel):
    """Response after saving file"""

    file_id: str
    saved: bool
    updated_at: str
    conflict: bool = False


class DeleteFileResponse(BaseModel):
    """Response after deleting file"""

    success: bool
    deleted_count: int


# ========================================
# SYNC & SNAPSHOT MODELS
# ========================================


class SyncFileData(BaseModel):
    """File data for sync"""

    path: str
    content: str
    language: str


class SyncMetadata(BaseModel):
    """Project metadata for sync"""

    name: str
    template: str
    description: Optional[str] = None


class SyncToCloudRequest(BaseModel):
    """Sync project to cloud"""

    files: List[SyncFileData]
    metadata: SyncMetadata


class SyncToCloudResponse(BaseModel):
    """Sync response"""

    synced: bool
    synced_at: str
    files_count: int


class SnapshotListItem(BaseModel):
    """Snapshot item"""

    id: str
    name: str
    created_at: str
    files_count: int


class SnapshotListResponse(BaseModel):
    """Snapshot list"""

    snapshots: List[SnapshotListItem]


class CreateSnapshotRequest(BaseModel):
    """Create snapshot"""

    name: Optional[str] = Field(None, max_length=200)


class CreateSnapshotResponse(BaseModel):
    """Snapshot created"""

    id: str
    name: str
    files_count: int
    created_at: str


# ========================================
# EXPORT/IMPORT MODELS
# ========================================


class ImportProjectResponse(BaseModel):
    """Import project from ZIP"""

    id: str
    name: str
    files_count: int
    created_at: str


# ========================================
# COMMON RESPONSES
# ========================================


class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Error response"""

    error: str
    detail: Optional[str] = None


# ========================================
# PROGRESS TRACKING MODELS
# ========================================


class ProgressData(BaseModel):
    """User progress on a project"""

    id: str
    user_id: str
    project_id: str
    template_id: str
    completed_steps: int
    total_steps: int
    time_spent_seconds: int
    last_accessed_at: str
    created_at: str


class UpdateProgressRequest(BaseModel):
    """Update progress"""

    completed_steps: Optional[int] = None
    time_spent_seconds: Optional[int] = None


# ========================================
# ADMIN TEMPLATE MANAGEMENT MODELS
# ========================================


class CreateTemplateRequest(BaseModel):
    """Admin: Create new template"""

    id: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique template ID (e.g., 'react_todo')",
    )
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    description: str = Field(..., min_length=1, max_length=500)
    category: LabCategory
    difficulty: LabDifficulty
    language: str = Field(
        ..., min_length=1, max_length=50, description="Primary language"
    )
    estimated_time_minutes: int = Field(..., ge=15, le=600)
    thumbnail_url: Optional[str] = None
    guide_steps: List[str] = Field(..., min_items=1, max_items=20)
    tags: List[str] = Field(default_factory=list, max_items=10)


class UpdateTemplateRequest(BaseModel):
    """Admin: Update template metadata"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    category: Optional[LabCategory] = None
    difficulty: Optional[LabDifficulty] = None
    language: Optional[str] = Field(None, min_length=1, max_length=50)
    estimated_time_minutes: Optional[int] = Field(None, ge=15, le=600)
    thumbnail_url: Optional[str] = None
    guide_steps: Optional[List[str]] = Field(None, min_items=1, max_items=20)
    tags: Optional[List[str]] = Field(None, max_items=10)


class CreateTemplateFileRequest(BaseModel):
    """Admin: Add file to template"""

    path: str = Field(
        ..., min_length=1, max_length=500, description="File path (e.g., 'src/App.js')"
    )
    name: str = Field(..., min_length=1, max_length=255, description="Filename")
    type: FileType = FileType.FILE
    language: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1, description="File content (code)")


class UpdateTemplateFileRequest(BaseModel):
    """Admin: Update template file"""

    path: Optional[str] = Field(None, min_length=1, max_length=500)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    language: Optional[str] = Field(None, min_length=1, max_length=50)
    content: Optional[str] = Field(None, min_length=1)


class TemplateCreatedResponse(BaseModel):
    """Response for template creation"""

    message: str
    template: TemplateDetail


class TemplateFileCreatedResponse(BaseModel):
    """Response for template file creation"""

    message: str
    file: TemplateFile
