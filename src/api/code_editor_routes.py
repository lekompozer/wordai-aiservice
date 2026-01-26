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
    FileResponse,
    ListFilesResponse,
    DeleteFileResponse,
    IncrementRunResponse,
    CreateFolderRequest,
    UpdateFolderRequest,
    FolderResponse,
    ListFoldersResponse,
    DeleteFolderResponse,
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
    sort_by: FileSortBy = Query(FileSortBy.updated_at),
    order: SortOrder = Query(SortOrder.desc),
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
async def duplicate_file(
    file_id: str, current_user: dict = Depends(get_current_user)
):
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
        language_filter=request.language_filter.value if request.language_filter else None,
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
        language_filter=request.language_filter.value if request.language_filter else None,
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
