"""
Software Lab AI Models
Pydantic models for AI Code Assistant features
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
from datetime import datetime


# ============================================================================
# Shared: Local File Input (Desktop only)
# ============================================================================


class LocalFileInput(BaseModel):
    """Local file content sent inline from the desktop client.

    Desktop apps can have files stored only on disk (not synced to the cloud).
    In this case, the frontend must send the file content directly instead of
    a ``file_id``.
    """

    content: str = Field(..., description="Full file content")
    path: str = Field(..., description="File path for display, e.g. 'src/main.py'")
    language: str = Field(
        "unknown",
        description="Programming language: python, javascript, typescript, etc.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "def hello():\n    print('Hello, World!')",
                "path": "src/main.py",
                "language": "python",
            }
        }


# ============================================================================
# Feature 1: Generate Code
# ============================================================================


class GenerateCodeRequest(BaseModel):
    """Request to generate new code from natural language description"""

    project_id: str = Field(..., description="Project ID")
    user_query: str = Field(
        ..., min_length=1, max_length=5000, description="Natural language description"
    )

    # Optional: target location
    target_file_id: Optional[str] = Field(None, description="Add to existing file")
    target_path: Optional[str] = Field(None, description="Or create new file at path")
    insert_at_line: Optional[int] = Field(
        None, ge=1, description="Line number to insert"
    )

    # Optional: context files (cloud)
    context_file_ids: Optional[List[str]] = Field(
        None, description="Specific cloud file IDs for context"
    )
    include_all_files: bool = Field(
        False, description="Include entire project as context (cloud files only)"
    )

    # Optional: context files (local — desktop only)
    context_local_files: Optional[List[LocalFileInput]] = Field(
        None,
        description="Local files to include as context (desktop mode). "
        "Send full content here when files are not synced to cloud.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "proj_abc123",
                "user_query": "Create a login form with email and password validation",
                "target_path": "src/components/LoginForm.jsx",
                "include_all_files": False,
                "context_local_files": [
                    {
                        "content": "// existing auth.js content",
                        "path": "src/auth.js",
                        "language": "javascript",
                    }
                ],
            }
        }


class GenerateCodeResponse(BaseModel):
    """Response from generate code job"""

    success: bool
    job_id: str
    status: str  # pending, processing, completed, failed

    # Available when completed
    generated_code: Optional[str] = None
    explanation: Optional[str] = None
    suggested_file: Optional[Dict[str, Any]] = None

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 1
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Feature 2: Explain Code
# ============================================================================

# 8 major languages supported by GLM-5 for code explanation comments
EXPLAIN_LANGUAGES = {
    "vi": "Vietnamese (Tiếng Việt)",
    "en": "English",
    "zh": "Chinese Simplified (中文简体)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "fr": "French (Français)",
    "es": "Spanish (Español)",
    "de": "German (Deutsch)",
    "th": "Thai (ภาษาไทย)",
    "ms": "Malay (Bahasa Melayu)",
    "id": "Indonesian (Bahasa Indonesia)",
}


class ExplainCodeRequest(BaseModel):
    """Request to explain existing code.

    Supports two file modes:
    - **Cloud file**: set ``file_id`` (file is stored in the cloud project)
    - **Local file** (desktop only): set ``local_file`` with full content

    Exactly one of ``file_id`` or ``local_file`` must be provided.
    """

    project_id: str = Field(..., description="Project ID")

    # File source — exactly one required
    file_id: Optional[str] = Field(
        None, description="Cloud file ID (file stored in project)"
    )
    local_file: Optional[LocalFileInput] = Field(
        None,
        description="Local file content (desktop only — file not synced to cloud)",
    )

    # Optional: explain only selected lines
    selection: Optional[Dict[str, int]] = Field(
        None, description="Selected lines: {start_line: int, end_line: int}"
    )

    # Optional: specific question
    question: Optional[str] = Field(
        None, max_length=500, description="Specific question about the code"
    )

    # Language for AI comments/explanations
    explain_language: Optional[str] = Field(
        "vi",
        description=(
            "Language for inline comments and explanations. "
            f"Supported: {', '.join(EXPLAIN_LANGUAGES.keys())}. "
            "Default: vi (Vietnamese)."
        ),
    )

    @model_validator(mode="after")
    def check_file_source(self):
        if not self.file_id and not self.local_file:
            raise ValueError(
                "Either 'file_id' (cloud) or 'local_file' (desktop) must be provided"
            )
        if self.file_id and self.local_file:
            raise ValueError("Provide either 'file_id' or 'local_file', not both")
        return self

    class Config:
        json_schema_extra = {
            "examples": {
                "cloud_file": {
                    "summary": "Cloud file (Vietnamese comments)",
                    "value": {
                        "project_id": "proj_abc123",
                        "file_id": "file_xyz789",
                        "selection": {"start_line": 10, "end_line": 25},
                        "question": "Why is useState used here?",
                        "explain_language": "vi",
                    },
                },
                "local_file_english": {
                    "summary": "Local file (English comments)",
                    "value": {
                        "project_id": "proj_abc123",
                        "local_file": {
                            "content": "def hello():\n    print('hi')",
                            "path": "src/main.py",
                            "language": "python",
                        },
                        "question": "What does this function do?",
                        "explain_language": "en",
                    },
                },
                "local_file_japanese": {
                    "summary": "Local file (Japanese comments)",
                    "value": {
                        "project_id": "proj_abc123",
                        "local_file": {
                            "content": "const add = (a, b) => a + b;",
                            "path": "src/utils.js",
                            "language": "javascript",
                        },
                        "explain_language": "ja",
                    },
                },
            }
        }


class CodeSnippet(BaseModel):
    """Highlighted code snippet with explanation"""

    lines: List[int]
    explanation: str


class ExplainCodeResponse(BaseModel):
    """Response from explain code job"""

    success: bool
    job_id: str
    status: str

    # Available when completed - now returns annotated code
    file_path: Optional[str] = None
    annotated_code: Optional[str] = None  # Code with inline comments added
    explanation: Optional[str] = None  # Overall explanation
    key_concepts: Optional[List[str]] = None
    code_snippets: Optional[List[CodeSnippet]] = None

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 1
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Feature 3: Transform Code
# ============================================================================


class TransformCodeRequest(BaseModel):
    """Request to refactor/optimize/convert existing code.

    Supports two file modes:
    - **Cloud file**: set ``file_id`` (file is stored in the cloud project)
    - **Local file** (desktop only): set ``local_file`` with full content

    Exactly one of ``file_id`` or ``local_file`` must be provided.
    """

    project_id: str = Field(..., description="Project ID")

    # File source — exactly one required
    file_id: Optional[str] = Field(
        None, description="Cloud file ID (file stored in project)"
    )
    local_file: Optional[LocalFileInput] = Field(
        None,
        description="Local file content (desktop only — file not synced to cloud)",
    )

    # Required: transformation type
    transformation: str = Field(
        ..., description="Type: refactor, optimize, convert, fix, add-feature"
    )

    # Required: transformation details
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Specific transformation instruction",
    )

    # Optional: target only selected lines
    selection: Optional[Dict[str, int]] = Field(
        None, description="Selected lines: {start_line: int, end_line: int}"
    )

    @model_validator(mode="after")
    def check_file_source(self):
        if not self.file_id and not self.local_file:
            raise ValueError(
                "Either 'file_id' (cloud) or 'local_file' (desktop) must be provided"
            )
        if self.file_id and self.local_file:
            raise ValueError("Provide either 'file_id' or 'local_file', not both")
        return self

    class Config:
        json_schema_extra = {
            "examples": {
                "cloud_file": {
                    "summary": "Cloud file",
                    "value": {
                        "project_id": "proj_abc123",
                        "file_id": "file_xyz789",
                        "transformation": "convert",
                        "instruction": "Convert class component to functional with hooks",
                        "selection": {"start_line": 1, "end_line": 50},
                    },
                },
                "local_file": {
                    "summary": "Local file (desktop)",
                    "value": {
                        "project_id": "proj_abc123",
                        "local_file": {
                            "content": "class MyComp extends React.Component { ... }",
                            "path": "src/MyComp.jsx",
                            "language": "javascript",
                        },
                        "transformation": "convert",
                        "instruction": "Convert to functional component with hooks",
                    },
                },
            }
        }


class DiffInfo(BaseModel):
    """Code diff information"""

    additions: int
    deletions: int
    preview: str


class TransformCodeResponse(BaseModel):
    """Response from transform code job"""

    success: bool
    job_id: str
    status: str

    # Available when completed
    transformed_code: Optional[str] = None
    changes_summary: Optional[str] = None
    diff: Optional[DiffInfo] = None

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 1
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Feature 4: Analyze Architecture
# ============================================================================


class TechStackPreferences(BaseModel):
    """Tech stack constraints"""

    backend: Optional[List[str]] = Field(None, description="Backend technologies")
    frontend: Optional[List[str]] = Field(None, description="Frontend technologies")
    database: Optional[List[str]] = Field(None, description="Database technologies")
    other: Optional[List[str]] = Field(None, description="Other requirements")


class AnalyzeArchitectureRequest(BaseModel):
    """Request to generate system architecture from requirements"""

    # Optional: attach to existing project
    project_id: Optional[str] = Field(None, description="Existing project ID")

    # Required: user requirements
    requirements: str = Field(
        ...,
        min_length=50,
        max_length=10000,
        description="Project requirements description",
    )

    # Optional: tech stack constraints
    tech_stack: Optional[TechStackPreferences] = None

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "proj_abc123",
                "requirements": "Build a task management app with user auth, task CRUD, categories, deadlines, and team collaboration",
                "tech_stack": {
                    "backend": ["Python", "FastAPI"],
                    "frontend": ["React", "TypeScript"],
                    "database": ["SQLite"],
                },
            }
        }


class Feature(BaseModel):
    """System feature specification"""

    name: str
    description: str
    priority: str  # high, medium, low
    complexity: str  # low, medium, high


class UserFlow(BaseModel):
    """User flow specification"""

    name: str
    steps: List[str]


class TableColumn(BaseModel):
    """Database column specification"""

    name: str
    type: str
    constraints: Optional[List[str]] = None


class DatabaseTable(BaseModel):
    """Database table specification"""

    name: str
    columns: List[TableColumn]


class DatabaseSchema(BaseModel):
    """Database schema specification"""

    tables: List[DatabaseTable]


class FolderStructure(BaseModel):
    """Folder structure specification"""

    backend: List[str]
    frontend: List[str]
    shared: Optional[List[str]] = None


class ImplementationPhase(BaseModel):
    """Implementation phase specification"""

    phase: int
    name: str
    tasks: List[str]
    estimated_hours: int


class ArchitectureDocument(BaseModel):
    """Complete architecture document"""

    system_overview: str
    features_list: List[Feature]
    user_flows: List[UserFlow]
    database_schema: DatabaseSchema
    folder_structure: FolderStructure
    implementation_phases: List[ImplementationPhase]


class AnalyzeArchitectureResponse(BaseModel):
    """Response from analyze architecture job"""

    success: bool
    job_id: str
    status: str

    # Available when completed
    architecture_id: Optional[str] = None
    architecture: Optional[ArchitectureDocument] = None

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 2
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Feature 5: Scaffold Project
# ============================================================================


class ScaffoldProjectRequest(BaseModel):
    """Request to scaffold project structure from architecture"""

    project_id: str = Field(..., description="Project ID")
    architecture_id: str = Field(..., description="Architecture document ID")

    # Optional: customize generation
    include_comments: bool = Field(True, description="Add tutorial comments")
    file_types: Optional[List[str]] = Field(
        None, description="Filter file types: ['py', 'js', 'jsx']"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "proj_abc123",
                "architecture_id": "arch_xyz789",
                "include_comments": True,
                "file_types": ["py", "js", "jsx"],
            }
        }


class ScaffoldedFile(BaseModel):
    """Information about a scaffolded file"""

    path: str
    content: str
    language: str
    size_bytes: int
    file_id: str


class ScaffoldSummary(BaseModel):
    """Summary of scaffolded project"""

    total_files: int
    total_folders: int
    languages: Dict[str, int]  # e.g., {"python": 5, "javascript": 8}


class ScaffoldProjectResponse(BaseModel):
    """Response from scaffold project job"""

    success: bool
    job_id: str
    status: str

    # Available when completed
    files_created: Optional[List[ScaffoldedFile]] = None
    folders_created: Optional[List[str]] = None
    summary: Optional[ScaffoldSummary] = None

    # Token usage
    tokens: Optional[Dict[str, int]] = None

    # Points
    points_deducted: int = 2
    new_balance: Optional[int] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# Job Status Models (for polling)
# ============================================================================


class JobStatusResponse(BaseModel):
    """Generic job status response for polling"""

    success: bool
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: Optional[int] = Field(
        None, ge=0, le=100, description="Progress percentage"
    )

    # Result when completed (polymorphic based on job type)
    result: Optional[Dict[str, Any]] = None

    # Error info
    error: Optional[str] = None
    message: Optional[str] = None

    # Metadata
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    worker_id: Optional[str] = None
