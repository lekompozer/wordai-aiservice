"""
Code Editor API Routes
Endpoints for managing code files, folders, templates, exercises
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query

from src.middleware.firebase_auth import get_current_user
from src.services.code_editor_manager import CodeEditorManager
from src.models.code_editor_models import (
    CreateFileRequest,
    UpdateFileRequest,
    UseTemplateRequest,
    FileResponse,
    ListFilesResponse,
    DeleteFileResponse,
    IncrementRunResponse,
    CreateFolderRequest,
    UpdateFolderRequest,
    FolderResponse,
    ListFoldersResponse,
    DeleteFolderResponse,
    CreateNoteRequest,
    UpdateNoteRequest,
    NoteResponse,
    CodeLanguage,
    FileSortBy,
    SortOrder,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/code-editor", tags=["Code Editor"])


# ==================== FILE MANAGEMENT ====================


@router.post("/files", response_model=dict)
async def create_file(
    request: CreateFileRequest, current_user: dict = Depends(get_current_user)
):
    """
    Create or save a code file

    - **name**: File name with extension (.py, .js, .html, .css)
    - **language**: Programming language (python, javascript, html, css)
    - **code**: File content (max 1MB)
    - **folder_id**: Optional folder ID
    - **tags**: Optional tags (max 10)
    - **is_public**: Make file publicly accessible
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.create_file(
        user_id=user_id,
        name=request.name,
        language=request.language.value,
        code=request.code,
        folder_id=request.folder_id,
        tags=request.tags,
        is_public=request.is_public,
        description=request.description,
    )

    return result


@router.get("/files", response_model=dict)
async def list_files(
    folder_id: Optional[str] = Query(None, description="Filter by folder"),
    language: Optional[CodeLanguage] = Query(None, description="Filter by language"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: FileSortBy = Query(FileSortBy.UPDATED_AT),
    order: SortOrder = Query(SortOrder.DESC),
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's code files with filters and pagination

    - **folder_id**: Filter by folder (use 'root' for files without folder)
    - **language**: Filter by programming language
    - **tags**: Filter by tags (comma-separated)
    - **search**: Search text in file name or description
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20, max: 100)
    - **sort_by**: Sort field (created_at, updated_at, name, run_count)
    - **order**: Sort order (asc, desc)
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.get_user_files(
        user_id=user_id,
        folder_id=folder_id,
        language=language.value if language else None,
        tags=tags,
        search=search,
        page=page,
        limit=limit,
        sort_by=sort_by.value,
        order=order.value,
    )

    return result


@router.get("/files/{file_id}", response_model=dict)
async def get_file(file_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get file by ID with full code content

    Returns file details including code, metadata, and access permissions
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.get_file_by_id(file_id=file_id, user_id=user_id)

    return result


@router.put("/files/{file_id}", response_model=dict)
async def update_file(
    file_id: str,
    request: UpdateFileRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update file metadata and/or code

    All fields are optional. Only provided fields will be updated.
    Code changes will trigger syntax validation.
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.update_file(
        file_id=file_id,
        user_id=user_id,
        name=request.name,
        code=request.code,
        folder_id=request.folder_id,
        tags=request.tags,
        is_public=request.is_public,
        description=request.description,
    )

    return result


@router.delete("/files/{file_id}", response_model=dict)
async def delete_file(file_id: str, current_user: dict = Depends(get_current_user)):
    """
    Soft delete file (move to trash)

    Files are soft deleted and can be recovered within 30 days
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.delete_file(file_id=file_id, user_id=user_id)

    return result


@router.post("/files/{file_id}/run", response_model=dict)
async def increment_run_count(
    file_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Increment file run count

    Called when user executes the code (frontend Pyodide)
    Tracks usage analytics and last run time
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.increment_run_count(file_id=file_id, user_id=user_id)

    return result


@router.post("/files/{file_id}/duplicate", response_model=dict)
async def duplicate_file(file_id: str, current_user: dict = Depends(get_current_user)):
    """
    Clone/duplicate a file

    Creates a copy of the file with '_copy' suffix
    Duplicates are always private (is_public=False)
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.duplicate_file(file_id=file_id, user_id=user_id)

    return result


# ==================== FOLDER MANAGEMENT ====================


@router.post("/folders", response_model=dict)
async def create_folder(
    request: CreateFolderRequest, current_user: dict = Depends(get_current_user)
):
    """
    Create a folder

    - **name**: Folder name (max 100 chars)
    - **parent_id**: Optional parent folder for nested structure
    - **color**: Hex color code for UI (#RRGGBB)
    - **language_filter**: Auto-filter files by language
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.create_folder(
        user_id=user_id,
        name=request.name,
        parent_id=request.parent_id,
        color=request.color,
        language_filter=(
            request.language_filter.value if request.language_filter else None
        ),
    )

    return result


@router.get("/folders", response_model=dict)
async def list_folders(current_user: dict = Depends(get_current_user)):
    """
    Get user's folders

    Returns all folders with file counts
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.get_user_folders(user_id=user_id)

    return result


@router.put("/folders/{folder_id}", response_model=dict)
async def update_folder(
    folder_id: str,
    request: UpdateFolderRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update folder metadata

    All fields are optional. Only provided fields will be updated.
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.update_folder(
        folder_id=folder_id,
        user_id=user_id,
        name=request.name,
        color=request.color,
        language_filter=(
            request.language_filter.value if request.language_filter else None
        ),
    )

    return result


@router.delete("/folders/{folder_id}", response_model=dict)
async def delete_folder(
    folder_id: str,
    delete_files: bool = Query(
        False, description="Delete files in folder (default: move to root)"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Delete folder

    - **delete_files=false**: Move files to root (default)
    - **delete_files=true**: Soft delete all files in folder
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.delete_folder(
        folder_id=folder_id, user_id=user_id, delete_files=delete_files
    )

    return result


# ==================== TEMPLATE LIBRARY ====================


@router.get("/templates", response_model=dict)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category ID"),
    language: Optional[CodeLanguage] = Query(None, description="Filter by language"),
    difficulty: Optional[str] = Query(
        None, description="beginner/intermediate/advanced"
    ),
    search: Optional[str] = Query(None, description="Search in title/description"),
    featured: Optional[bool] = Query(None, description="Show only featured templates"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    List code templates with filtering

    - **category**: Filter by category ID (e.g., 'python-lop10-gioi-thieu')
    - **language**: Filter by language (python, javascript, html, css, sql)
    - **difficulty**: Filter by difficulty level
    - **search**: Search in title and description
    - **featured**: Show only featured templates
    """
    manager = CodeEditorManager()

    result = await manager.list_templates(
        category=category,
        language=language,
        difficulty=difficulty,
        search=search,
        featured=featured,
        limit=limit,
        skip=skip,
    )

    return result


@router.get("/categories", response_model=dict)
async def list_categories(
    language: Optional[CodeLanguage] = Query(None, description="Filter by language"),
    current_user: dict = Depends(get_current_user),
):
    """
    List template categories

    - **language**: Filter by programming language
    """
    manager = CodeEditorManager()

    result = await manager.list_categories(language=language)

    return result


@router.get("/templates/{template_id}", response_model=dict)
async def get_template(
    template_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get template details including full code
    """
    manager = CodeEditorManager()

    result = await manager.get_template(template_id=template_id)

    return result


@router.post("/templates/{template_id}/use", response_model=dict)
async def use_template(
    template_id: str,
    request: UseTemplateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create new file from template

    - **file_name**: Name for the new file (with extension)
    - **folder_id**: Optional folder to create file in

    Creates a new file with template code and increments template usage count
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.use_template(
        template_id=template_id,
        user_id=user_id,
        file_name=request.file_name,
        folder_id=request.folder_id,
    )

    return result


# ==================== EXERCISES & GRADING ====================


@router.post("/exercises/{exercise_id}/grade-sql", response_model=dict)
async def grade_sql_exercise(
    exercise_id: str,
    code: str = Query(..., description="SQL code to grade"),
    current_user: dict = Depends(get_current_user),
):
    """
    Grade SQL exercise submission

    - **exercise_id**: Exercise ID to grade
    - **code**: SQL code submission

    Executes SQL against test database and validates results
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.grade_sql_exercise(
        exercise_id=exercise_id,
        user_id=user_id,
        code=code,
    )

    return result


# ==================== FILE NOTES ====================


@router.post("/files/{file_id}/notes", response_model=dict)
async def create_note(
    file_id: str,
    request: CreateNoteRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a note for a code file

    - **file_id**: Target file ID
    - **content**: Note content (max 5000 chars)
    - **color**: Highlight color (default: yellow)
    - **line_number**: Optional line number to attach note to
    - **is_pinned**: Pin note to top (default: false)
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.create_note(
        file_id=file_id,
        user_id=user_id,
        content=request.content,
        color=request.color,
        line_number=request.line_number,
        is_pinned=request.is_pinned,
    )

    return result


@router.get("/files/{file_id}/notes", response_model=dict)
async def get_file_notes(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get all notes for a file

    Returns list of notes sorted by pinned first, then by creation date
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.get_file_notes(
        file_id=file_id,
        user_id=user_id,
    )

    return result


@router.get("/notes/{note_id}", response_model=dict)
async def get_note(
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific note by ID"""
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.get_note(
        note_id=note_id,
        user_id=user_id,
    )

    return result


@router.put("/notes/{note_id}", response_model=dict)
async def update_note(
    note_id: str,
    request: UpdateNoteRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update a note

    All fields optional - only provided fields will be updated
    """
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.update_note(
        note_id=note_id,
        user_id=user_id,
        content=request.content,
        color=request.color,
        line_number=request.line_number,
        is_pinned=request.is_pinned,
    )

    return result


@router.delete("/notes/{note_id}", response_model=dict)
async def delete_note(
    note_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a note"""
    user_id = current_user["uid"]
    manager = CodeEditorManager()

    result = await manager.delete_note(
        note_id=note_id,
        user_id=user_id,
    )

    return result
