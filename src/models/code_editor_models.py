"""
Code Editor Models
Pydantic models for Code Editor file management, templates, exercises
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# ==================== ENUMS ====================


class CodeLanguage(str, Enum):
    """Supported programming languages"""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    HTML = "html"
    CSS = "css"
    SQL = "sql"


class FileSortBy(str, Enum):
    """Sort options for file listing"""

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    RUN_COUNT = "run_count"


class SortOrder(str, Enum):
    """Sort order"""

    ASC = "asc"
    DESC = "desc"


class ExerciseDifficulty(str, Enum):
    """Exercise difficulty levels"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ExerciseStatus(str, Enum):
    """Exercise completion status"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SubmissionStatus(str, Enum):
    """Submission grading status"""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class ShareAccessLevel(str, Enum):
    """Share link access levels"""

    VIEW_ONLY = "view_only"
    CAN_COPY = "can_copy"
    CAN_EDIT = "can_edit"


# ==================== FILE MODELS ====================


class FileMetadata(BaseModel):
    """File metadata"""

    size_bytes: int = 0
    run_count: int = 0
    last_run_at: Optional[datetime] = None
    lines_of_code: int = 0


class CreateFileRequest(BaseModel):
    """Request to create/save a code file"""

    id: Optional[str] = None  # If updating existing file
    name: str = Field(..., min_length=1, max_length=255)
    language: CodeLanguage
    code: str = Field(..., max_length=1_000_000)  # 1MB limit
    folder_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool = False
    description: Optional[str] = Field(None, max_length=500)

    @validator("name")
    def validate_file_name(cls, v):
        """Validate file name format"""
        import re

        if not re.match(r"^[\w\-. ]+\.(py|js|html|css|sql)$", v):
            raise ValueError(
                "Invalid file name. Must end with .py, .js, .html, .css, or .sql"
            )
        return v

    @validator("tags")
    def validate_tags(cls, v):
        """Limit number of tags"""
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return v


class UpdateFileRequest(BaseModel):
    """Request to update a file (all fields optional)"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=1_000_000)
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)

    @validator("name")
    def validate_file_name(cls, v):
        """Validate file name format"""
        if v is not None:
            import re

            if not re.match(r"^[\w\-. ]+\.(py|js|html|css|sql)$", v):
                raise ValueError(
                    "Invalid file name. Must end with .py, .js, .html, .css, or .sql"
                )
        return v


class FileResponse(BaseModel):
    """Code file response"""

    id: str
    user_id: str
    name: str
    language: CodeLanguage
    code: str
    folder_id: Optional[str] = None
    tags: List[str]
    is_public: bool
    description: Optional[str] = None
    metadata: FileMetadata
    created_at: datetime
    updated_at: datetime
    share_link: Optional[str] = None  # If file has active share


class FileListItem(BaseModel):
    """Simplified file info for list view"""

    id: str
    name: str
    language: CodeLanguage
    folder_id: Optional[str] = None
    tags: List[str]
    is_public: bool
    description: Optional[str] = None
    size_bytes: int
    run_count: int
    created_at: datetime
    updated_at: datetime


class ListFilesResponse(BaseModel):
    """Response for file listing"""

    success: bool = True
    files: List[FileListItem]
    pagination: Dict[str, Any]


class FileOperationResponse(BaseModel):
    """Generic file operation response"""

    success: bool = True
    file: FileResponse


class DeleteFileResponse(BaseModel):
    """Response for file deletion"""

    success: bool = True
    message: str
    file_id: str
    deleted_at: datetime


class IncrementRunResponse(BaseModel):
    """Response for incrementing run count"""

    success: bool = True
    run_count: int


# ==================== FOLDER MODELS ====================


class CreateFolderRequest(BaseModel):
    """Request to create a folder"""

    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    language_filter: Optional[CodeLanguage] = None


class UpdateFolderRequest(BaseModel):
    """Request to update a folder"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    language_filter: Optional[CodeLanguage] = None


class FolderResponse(BaseModel):
    """Folder response"""

    id: str
    user_id: str
    name: str
    parent_id: Optional[str] = None
    color: Optional[str] = None
    language_filter: Optional[CodeLanguage] = None
    file_count: int = 0
    created_at: datetime
    updated_at: datetime


class ListFoldersResponse(BaseModel):
    """Response for folder listing"""

    success: bool = True
    folders: List[FolderResponse]


class FolderOperationResponse(BaseModel):
    """Generic folder operation response"""

    success: bool = True
    folder: FolderResponse


class DeleteFolderResponse(BaseModel):
    """Response for folder deletion"""

    success: bool = True
    message: str
    files_moved_to_root: int


# ==================== TEMPLATE MODELS ====================


class TemplateMetadata(BaseModel):
    """Template metadata"""

    author: str = "WordAI Team"
    version: str = "1.0"
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    dependencies: List[str] = Field(default_factory=list)


class TemplateResponse(BaseModel):
    """Code template response"""

    id: str
    name: str
    language: CodeLanguage
    category: str
    difficulty: ExerciseDifficulty
    code: str
    description: str
    tags: List[str]
    metadata: TemplateMetadata
    is_featured: bool = False
    display_order: int = 0


class CategoryResponse(BaseModel):
    """Template category response"""

    id: str
    name: str
    slug: str
    language: CodeLanguage
    description: str
    icon: Optional[str] = None
    color: Optional[str] = None
    template_count: int = 0
    display_order: int = 0


class ListTemplatesResponse(BaseModel):
    """Response for template listing"""

    success: bool = True
    templates: List[TemplateResponse]
    categories: List[CategoryResponse]


class UseTemplateRequest(BaseModel):
    """Request to create file from template"""

    file_name: str = Field(..., min_length=1, max_length=255)
    folder_id: Optional[str] = None


class UseTemplateResponse(BaseModel):
    """Response for using template"""

    success: bool = True
    file: FileResponse


# ==================== EXERCISE MODELS ====================


class TestCase(BaseModel):
    """Test case for exercise"""

    test_number: int
    input: str
    expected_output: str
    points: int = 1
    is_hidden: bool = False
    test_type: str = "unit_test"


class ExerciseHint(BaseModel):
    """Exercise hint"""

    hint_number: int
    text: str
    unlock_after_attempts: int = 0


class ExerciseMetadata(BaseModel):
    """Exercise metadata"""

    total_attempts: int = 0
    success_count: int = 0
    average_time_minutes: float = 0.0
    estimated_time_minutes: int = 30
    author: str = "WordAI Team"
    tags: List[str] = Field(default_factory=list)


class ExerciseResponse(BaseModel):
    """Exercise response"""

    id: str
    title: str
    slug: str
    description: str
    language: CodeLanguage
    category: str
    difficulty: ExerciseDifficulty
    points: int
    starter_code: str
    hints: List[ExerciseHint]
    test_cases: List[TestCase]  # Hidden test cases excluded
    metadata: ExerciseMetadata
    user_status: ExerciseStatus = ExerciseStatus.NOT_STARTED
    user_score: int = 0
    total_submissions: int = 0
    success_rate: float = 0.0


class SubmitSolutionRequest(BaseModel):
    """Request to submit exercise solution"""

    code: str = Field(..., max_length=1_000_000)


class TestResult(BaseModel):
    """Individual test result"""

    test_number: int
    passed: bool
    input: str
    expected: str
    actual: str
    error_message: Optional[str] = None
    points_earned: int
    execution_time_ms: int


class SubmissionResponse(BaseModel):
    """Submission grading response"""

    success: bool = True
    submission: Dict[str, Any]
    leaderboard_rank: Optional[int] = None
    points_earned: int


class LeaderboardEntry(BaseModel):
    """Leaderboard entry"""

    rank: int
    user_id: str
    display_name: str
    score: int
    execution_time_ms: int
    submitted_at: datetime


class LeaderboardResponse(BaseModel):
    """Leaderboard response"""

    success: bool = True
    leaderboard: List[LeaderboardEntry]
    current_user_rank: Optional[int] = None
    current_user_score: int = 0


# ==================== SHARE MODELS ====================


class CreateShareRequest(BaseModel):
    """Request to create share link"""

    access_level: ShareAccessLevel = ShareAccessLevel.VIEW_ONLY
    expires_at: Optional[datetime] = None
    require_password: bool = False
    password: Optional[str] = None

    @validator("password")
    def validate_password(cls, v, values):
        """Validate password if required"""
        if values.get("require_password") and not v:
            raise ValueError("Password required when require_password is True")
        return v


class ShareResponse(BaseModel):
    """Share link response"""

    id: str
    file_id: str
    share_code: str
    share_url: str
    access_level: ShareAccessLevel
    expires_at: Optional[datetime] = None
    require_password: bool
    view_count: int
    created_at: datetime


class CreateShareLinkResponse(BaseModel):
    """Response for creating share link"""

    success: bool = True
    share: ShareResponse


class SharedFileResponse(BaseModel):
    """Shared file response (public access)"""

    success: bool = True
    file: Dict[str, Any]


class RevokeShareResponse(BaseModel):
    """Response for revoking share link"""

    success: bool = True
    message: str


# ==================== ANALYTICS MODELS ====================


class UserStats(BaseModel):
    """User statistics"""

    total_files: int = 0
    total_folders: int = 0
    total_runs: int = 0
    exercises_completed: int = 0
    exercises_in_progress: int = 0
    total_points: int = 0
    storage_used_bytes: int = 0
    storage_limit_bytes: int = 10_485_760  # 10MB
    most_used_tags: List[str] = Field(default_factory=list)
    streak_days: int = 0
    last_activity: Optional[datetime] = None


class StatsResponse(BaseModel):
    """User stats response"""

    success: bool = True
    stats: UserStats


class ActivityItem(BaseModel):
    """Activity history item"""

    id: str
    type: str
    description: str
    file_id: Optional[str] = None
    exercise_id: Optional[str] = None
    score: Optional[int] = None
    timestamp: datetime


class ActivityResponse(BaseModel):
    """Activity history response"""

    success: bool = True
    activities: List[ActivityItem]
    pagination: Dict[str, Any]
