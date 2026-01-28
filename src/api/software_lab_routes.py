"""
Software Lab API Routes
19 endpoints for Software Lab System (excluding AI endpoints)
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
import json
import zipfile
import io
from pathlib import Path

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.software_lab_models import (
    # Project models
    CreateProjectRequest,
    UpdateProjectRequest,
    CloneProjectRequest,
    ProjectListResponse,
    ProjectDetail,
    ProjectListItem,
    ProjectMetadata,
    # Template models
    TemplateListResponse,
    TemplateDetail,
    CreateFromTemplateRequest,
    TemplateListItem,
    TemplateFile,
    GuideStep,
    # File models
    LabFile,
    LabFileCreate,
    LabFileSave,
    FileTreeResponse,
    FileContentResponse,
    CreateFileResponse,
    SaveFileResponse,
    DeleteFileResponse,
    # Sync models
    SyncToCloudRequest,
    SyncToCloudResponse,
    SnapshotListResponse,
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    # Admin models
    CreateTemplateRequest,
    UpdateTemplateRequest,
    CreateTemplateFileRequest,
    UpdateTemplateFileRequest,
    TemplateCreatedResponse,
    TemplateFileCreatedResponse,
    # Common
    SuccessResponse,
    ImportProjectResponse,
    LabCategory,
    LabDifficulty,
    FileType,
)
from src.services.software_lab_storage import get_software_lab_storage
from src.middleware.admin_check import check_admin_access
import secrets


router = APIRouter(prefix="/software-lab", tags=["Software Lab"])


# ========================================
# UTILITY FUNCTIONS
# ========================================


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension"""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".html": "html",
        ".css": "css",
        ".scss": "css",
        ".sass": "css",
        ".sql": "sql",
        ".json": "json",
        ".md": "markdown",
        ".txt": "plaintext",
        ".yaml": "plaintext",
        ".yml": "plaintext",
    }

    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, "plaintext")


# ========================================
# GROUP 1: PROJECT MANAGEMENT (6 endpoints)
# ========================================


@router.post("/projects", response_model=ProjectDetail)
async def create_project(
    request: CreateProjectRequest, current_user: dict = Depends(get_current_user)
):
    """
    Create new project from template.
    Copies all template files to new project.
    """
    db_manager = DBManager()
    db = db_manager.db

    # 1. Verify template exists
    template = db.software_lab_templates.find_one({"id": request.template})
    if not template:
        raise HTTPException(404, f"Template '{request.template}' not found")

    # 2. Create project
    project_id = f"proj_{uuid4().hex[:12]}"
    now = datetime.utcnow()

    project_doc = {
        "id": project_id,
        "user_id": current_user["uid"],
        "name": request.name,
        "template": request.template,
        "description": request.description or "",
        "tags": request.tags or [],
        "is_public": False,
        "file_count": 0,
        "total_lines": 0,
        "languages": [],
        "created_at": now,
        "updated_at": now,
    }

    db.software_lab_projects.insert_one(project_doc)

    # 3. Copy template files to project files
    template_files = db.software_lab_template_files.find(
        {"template_id": request.template}
    )

    files_result = []
    total_lines = 0
    languages = set()

    for template_file in template_files:
        file_id = f"file_{uuid4().hex[:12]}"

        file_doc = {
            "id": file_id,
            "project_id": project_id,
            "path": template_file["path"],
            "content": template_file["content"],  # Code stored in MongoDB
            "url": None,  # Binary files would have R2 URL
            "language": template_file["language"],
            "type": "file",
            "size_bytes": len(template_file["content"]),
            "created_at": now,
            "updated_at": now,
        }

        db.software_lab_files.insert_one(file_doc)

        files_result.append(
            LabFile(
                id=file_id,
                path=file_doc["path"],
                content=file_doc["content"],
                url=file_doc["url"],
                language=file_doc["language"],
                type=FileType(file_doc["type"]),
                size_bytes=file_doc["size_bytes"],
                updated_at=now.isoformat(),
            )
        )

        # Count lines
        total_lines += file_doc["content"].count("\n") + 1
        languages.add(file_doc["language"])

    # 4. Update project metadata
    db.software_lab_projects.update_one(
        {"id": project_id},
        {
            "$set": {
                "file_count": len(files_result),
                "total_lines": total_lines,
                "languages": list(languages),
            }
        },
    )

    # 5. Initialize progress tracking
    db.software_lab_progress.insert_one(
        {
            "id": f"progress_{uuid4().hex[:12]}",
            "user_id": current_user["uid"],
            "project_id": project_id,
            "template_id": request.template,
            "completed_steps": 0,
            "total_steps": len(template.get("guide_steps", [])),
            "time_spent_seconds": 0,
            "last_accessed_at": now,
            "created_at": now,
        }
    )

    return ProjectDetail(
        id=project_id,
        name=project_doc["name"],
        template=project_doc["template"],
        description=project_doc["description"],
        user_id=project_doc["user_id"],
        files=files_result,
        metadata=ProjectMetadata(
            file_count=len(files_result),
            total_lines=total_lines,
            languages=list(languages),
        ),
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    page: int = 1,
    limit: int = 20,
    template: Optional[str] = None,
    sortBy: str = "updatedAt",
    order: str = "desc",
    current_user: dict = Depends(get_current_user),
):
    """
    Get user's projects with pagination and filters.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Build query
    query = {"user_id": current_user["uid"]}

    if template:
        query["template"] = template

    # Sort field
    sort_field_map = {
        "updatedAt": "updated_at",
        "createdAt": "created_at",
        "name": "name",
    }
    sort_field = sort_field_map.get(sortBy, "updated_at")
    sort_order = -1 if order == "desc" else 1

    # Pagination
    skip = (page - 1) * limit
    total = db.software_lab_projects.count_documents(query)

    projects_cursor = (
        db.software_lab_projects.find(query)
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )

    projects = []
    for project in projects_cursor:
        projects.append(
            ProjectListItem(
                id=project["id"],
                name=project["name"],
                template=project["template"],
                description=project.get("description", ""),
                thumbnail_url=project.get("thumbnail_url"),
                file_count=project.get("file_count", 0),
                last_modified=project["updated_at"].isoformat(),
                created_at=project["created_at"].isoformat(),
            )
        )

    total_pages = (total + limit - 1) // limit

    return ProjectListResponse(
        projects=projects, total=total, page=page, total_pages=total_pages
    )


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get full project detail with all files.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Get project
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get all files
    files_cursor = db.software_lab_files.find({"project_id": project_id})

    files_result = []
    total_lines = 0
    languages = set()

    for file_doc in files_cursor:
        files_result.append(
            LabFile(
                id=file_doc["id"],
                path=file_doc["path"],
                content=file_doc.get("content"),  # Code files
                url=file_doc.get("url"),  # Binary files
                language=file_doc["language"],
                type=FileType(file_doc.get("type", "file")),
                size_bytes=file_doc.get("size_bytes", 0),
                updated_at=file_doc["updated_at"].isoformat(),
            )
        )

        if file_doc.get("content"):
            total_lines += file_doc["content"].count("\n") + 1

        languages.add(file_doc["language"])

    return ProjectDetail(
        id=project["id"],
        name=project["name"],
        template=project["template"],
        description=project.get("description", ""),
        user_id=project["user_id"],
        files=files_result,
        metadata=ProjectMetadata(
            file_count=len(files_result),
            total_lines=total_lines,
            languages=list(languages),
        ),
        created_at=project["created_at"].isoformat(),
        updated_at=project["updated_at"].isoformat(),
    )


@router.put("/projects/{project_id}")
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update project metadata (name, description, thumbnail).
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Build update
    update_fields = {"updated_at": datetime.utcnow()}

    if request.name:
        update_fields["name"] = request.name
    if request.description is not None:
        update_fields["description"] = request.description
    if request.tags is not None:
        update_fields["tags"] = request.tags
    if request.thumbnail_url:
        update_fields["thumbnail_url"] = request.thumbnail_url

    # Update
    db.software_lab_projects.update_one({"id": project_id}, {"$set": update_fields})

    # Get updated project
    updated = db.software_lab_projects.find_one({"id": project_id})

    return {
        "id": updated["id"],
        "name": updated["name"],
        "description": updated.get("description", ""),
        "updated_at": updated["updated_at"].isoformat(),
    }


@router.delete("/projects/{project_id}", response_model=SuccessResponse)
async def delete_project(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete project and all related data (files, snapshots, progress).
    Also deletes binary files from R2 storage.
    """
    db_manager = DBManager()
    db = db_manager.db
    storage = get_software_lab_storage()

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Delete R2 files (binary assets)
    storage.delete_project_files(project_id)

    # Delete MongoDB data
    db.software_lab_files.delete_many({"project_id": project_id})
    db.software_lab_snapshots.delete_many({"project_id": project_id})
    db.software_lab_progress.delete_many({"project_id": project_id})
    db.software_lab_projects.delete_one({"id": project_id})

    return SuccessResponse(
        success=True, message=f"Project '{project['name']}' deleted successfully"
    )


@router.post("/projects/{project_id}/clone", response_model=ProjectDetail)
async def clone_project(
    project_id: str,
    request: CloneProjectRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Clone existing project (duplicate all files).
    """
    db_manager = DBManager()
    db = db_manager.db

    # Get original project
    original = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not original:
        raise HTTPException(404, "Project not found")

    # Create new project
    new_project_id = f"proj_{uuid4().hex[:12]}"
    new_name = request.new_name or f"Copy of {original['name']}"
    now = datetime.utcnow()

    new_project_doc = {
        "id": new_project_id,
        "user_id": current_user["uid"],
        "name": new_name,
        "template": original["template"],
        "description": original.get("description", ""),
        "tags": original.get("tags", []),
        "is_public": False,
        "file_count": original.get("file_count", 0),
        "total_lines": original.get("total_lines", 0),
        "languages": original.get("languages", []),
        "created_at": now,
        "updated_at": now,
    }

    db.software_lab_projects.insert_one(new_project_doc)

    # Copy all files
    original_files = db.software_lab_files.find({"project_id": project_id})

    files_result = []

    for file_doc in original_files:
        new_file_id = f"file_{uuid4().hex[:12]}"

        new_file_doc = {
            "id": new_file_id,
            "project_id": new_project_id,
            "path": file_doc["path"],
            "content": file_doc.get("content"),
            "url": file_doc.get("url"),
            "language": file_doc["language"],
            "type": file_doc.get("type", "file"),
            "size_bytes": file_doc.get("size_bytes", 0),
            "created_at": now,
            "updated_at": now,
        }

        db.software_lab_files.insert_one(new_file_doc)

        files_result.append(
            LabFile(
                id=new_file_id,
                path=new_file_doc["path"],
                content=new_file_doc.get("content"),
                url=new_file_doc.get("url"),
                language=new_file_doc["language"],
                type=FileType(new_file_doc["type"]),
                size_bytes=new_file_doc["size_bytes"],
                updated_at=now.isoformat(),
            )
        )

    return ProjectDetail(
        id=new_project_id,
        name=new_name,
        template=new_project_doc["template"],
        description=new_project_doc["description"],
        user_id=new_project_doc["user_id"],
        files=files_result,
        metadata=ProjectMetadata(
            file_count=len(files_result),
            total_lines=new_project_doc["total_lines"],
            languages=new_project_doc["languages"],
        ),
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


# ========================================
# GROUP 2: TEMPLATES (3 endpoints)
# ========================================


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[LabCategory] = None, difficulty: Optional[LabDifficulty] = None
):
    """
    Get template gallery (public endpoint - no auth required).
    """
    db_manager = DBManager()
    db = db_manager.db

    # Build query
    query = {"is_active": True}

    if category:
        query["category"] = category.value
    if difficulty:
        query["difficulty"] = difficulty.value

    # Get templates
    templates_cursor = db.software_lab_templates.find(query).sort("category", 1)

    templates = []
    for template in templates_cursor:
        templates.append(
            TemplateListItem(
                id=template["id"],
                name=template["name"],
                description=template["description"],
                thumbnail_url=template.get("thumbnail_url", ""),
                category=LabCategory(template["category"]),
                difficulty=LabDifficulty(template["difficulty"]),
                tags=template.get("tags", []),
                file_count=template.get("file_count", 0),
                estimated_time_minutes=template.get("estimated_time_minutes", 60),
            )
        )

    return TemplateListResponse(templates=templates)


@router.get("/templates/{template_id}", response_model=TemplateDetail)
async def get_template_detail(template_id: str):
    """
    Get full template detail with all starter files and guide.
    Public endpoint - no auth required.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Get template
    template = db.software_lab_templates.find_one({"id": template_id})

    if not template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    # Get template files
    files_cursor = db.software_lab_template_files.find({"template_id": template_id})

    files = []
    for file_doc in files_cursor:
        files.append(
            TemplateFile(
                path=file_doc["path"],
                content=file_doc["content"],
                language=file_doc["language"],
                is_editable=file_doc.get("is_editable", True),
            )
        )

    # Get guide steps
    guide_steps = []
    for step_data in template.get("guide_steps", []):
        guide_steps.append(
            GuideStep(
                step=step_data["step"],
                title=step_data["title"],
                description=step_data["description"],
                files_to_edit=step_data.get("files_to_edit", []),
            )
        )

    return TemplateDetail(
        id=template["id"],
        name=template["name"],
        description=template["description"],
        category=LabCategory(template["category"]),
        difficulty=LabDifficulty(template["difficulty"]),
        tags=template.get("tags", []),
        files=files,
        guide_steps=guide_steps,
    )


@router.post("/projects/from-template", response_model=ProjectDetail)
async def create_from_template(
    request: CreateFromTemplateRequest, current_user: dict = Depends(get_current_user)
):
    """
    Create project from template (alias for POST /projects).
    """
    create_request = CreateProjectRequest(
        name=request.project_name,
        template=request.template_id,
        description=request.description,
    )

    return await create_project(create_request, current_user)


# ========================================
# GROUP 3: FILES MANAGEMENT (5 endpoints)
# ========================================


@router.get("/projects/{project_id}/files", response_model=FileTreeResponse)
async def get_file_tree(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get file tree structure (without content - only paths).
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get files (exclude content for performance)
    files_cursor = db.software_lab_files.find(
        {"project_id": project_id}, {"content": 0}  # Exclude content field
    )

    files = []
    for file_doc in files_cursor:
        files.append(
            LabFile(
                id=file_doc["id"],
                path=file_doc["path"],
                content=None,  # Not included
                url=file_doc.get("url"),
                language=file_doc["language"],
                type=FileType(file_doc.get("type", "file")),
                size_bytes=file_doc.get("size_bytes", 0),
                updated_at=file_doc["updated_at"].isoformat(),
            )
        )

    return FileTreeResponse(files=files)


@router.get(
    "/projects/{project_id}/files/{file_id}", response_model=FileContentResponse
)
async def get_file_content(
    project_id: str, file_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get single file content.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify project ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get file
    file_doc = db.software_lab_files.find_one({"id": file_id, "project_id": project_id})

    if not file_doc:
        raise HTTPException(404, "File not found")

    return FileContentResponse(
        id=file_doc["id"],
        path=file_doc["path"],
        content=file_doc.get("content"),  # Code files
        url=file_doc.get("url"),  # Binary files
        language=file_doc["language"],
        updated_at=file_doc["updated_at"].isoformat(),
    )


@router.post("/projects/{project_id}/files", response_model=CreateFileResponse)
async def create_file(
    project_id: str,
    request: LabFileCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create new file or folder in project.
    Code files stored in MongoDB, binary files in R2.
    """
    db_manager = DBManager()
    db = db_manager.db
    storage = get_software_lab_storage()

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Check if file already exists
    existing = db.software_lab_files.find_one(
        {"project_id": project_id, "path": request.path}
    )

    if existing:
        raise HTTPException(400, f"File '{request.path}' already exists")

    # Detect language
    language = request.language or detect_language(request.path)

    # Create file
    file_id = f"file_{uuid4().hex[:12]}"
    content = request.content or ""
    now = datetime.utcnow()

    file_doc = {
        "id": file_id,
        "project_id": project_id,
        "path": request.path,
        "content": content if request.type == FileType.FILE else None,
        "url": None,  # Binary files would be uploaded separately
        "language": language,
        "type": request.type.value,
        "size_bytes": len(content) if content else 0,
        "created_at": now,
        "updated_at": now,
    }

    db.software_lab_files.insert_one(file_doc)

    # Update project
    db.software_lab_projects.update_one(
        {"id": project_id}, {"$set": {"updated_at": now}, "$inc": {"file_count": 1}}
    )

    return CreateFileResponse(
        file=LabFile(
            id=file_id,
            path=request.path,
            content=content if request.type == FileType.FILE else None,
            url=None,
            language=language,
            type=request.type,
            size_bytes=file_doc["size_bytes"],
            updated_at=now.isoformat(),
        ),
        project_updated_at=now.isoformat(),
    )


@router.put("/projects/{project_id}/files/{file_id}", response_model=SaveFileResponse)
async def save_file(
    project_id: str,
    file_id: str,
    request: LabFileSave,
    current_user: dict = Depends(get_current_user),
):
    """
    Save file content (auto-save from editor).
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get file
    file_doc = db.software_lab_files.find_one({"id": file_id, "project_id": project_id})

    if not file_doc:
        raise HTTPException(404, "File not found")

    # Conflict detection (optional)
    conflict = False
    if request.last_modified:
        try:
            last_mod = datetime.fromisoformat(request.last_modified)
            if file_doc["updated_at"] > last_mod:
                conflict = True
        except:
            pass

    # Update file
    now = datetime.utcnow()

    db.software_lab_files.update_one(
        {"id": file_id},
        {
            "$set": {
                "content": request.content,
                "size_bytes": len(request.content),
                "updated_at": now,
            }
        },
    )

    # Update project timestamp
    db.software_lab_projects.update_one(
        {"id": project_id}, {"$set": {"updated_at": now}}
    )

    return SaveFileResponse(
        file_id=file_id, saved=True, updated_at=now.isoformat(), conflict=conflict
    )


@router.delete(
    "/projects/{project_id}/files/{file_id}", response_model=DeleteFileResponse
)
async def delete_file(
    project_id: str, file_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Delete file or folder.
    If folder, deletes all files inside.
    """
    db_manager = DBManager()
    db = db_manager.db
    storage = get_software_lab_storage()

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get file
    file_doc = db.software_lab_files.find_one({"id": file_id, "project_id": project_id})

    if not file_doc:
        raise HTTPException(404, "File not found")

    # Delete from R2 if binary file
    if file_doc.get("url"):
        storage.delete_file(project_id, file_doc["path"])

    deleted_count = 0

    # If folder, delete all files inside
    if file_doc.get("type") == "folder":
        # Get all files in folder
        folder_files = db.software_lab_files.find(
            {"project_id": project_id, "path": {"$regex": f"^{file_doc['path']}/"}}
        )

        # Delete from R2 if needed
        for f in folder_files:
            if f.get("url"):
                storage.delete_file(project_id, f["path"])

        # Delete from MongoDB
        result = db.software_lab_files.delete_many(
            {"project_id": project_id, "path": {"$regex": f"^{file_doc['path']}/"}}
        )
        deleted_count = result.deleted_count

    # Delete the file/folder itself
    db.software_lab_files.delete_one({"id": file_id})
    deleted_count += 1

    # Update project file count
    db.software_lab_projects.update_one(
        {"id": project_id},
        {
            "$inc": {"file_count": -deleted_count},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    return DeleteFileResponse(success=True, deleted_count=deleted_count)


# ========================================
# GROUP 4: SYNC & SNAPSHOTS (3 endpoints)
# ========================================


@router.post("/projects/{project_id}/sync", response_model=SyncToCloudResponse)
async def sync_to_cloud(
    project_id: str,
    request: SyncToCloudRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Sync project from client (IndexedDB) to cloud (MongoDB).
    Creates or updates project with all files.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Get or create project
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    now = datetime.utcnow()

    if not project:
        # Create new project if not exists
        project_doc = {
            "id": project_id,
            "user_id": current_user["uid"],
            "name": request.metadata.name,
            "template": request.metadata.template,
            "description": request.metadata.description or "",
            "file_count": len(request.files),
            "is_public": False,
            "created_at": now,
            "updated_at": now,
        }
        db.software_lab_projects.insert_one(project_doc)

    # Delete old files
    db.software_lab_files.delete_many({"project_id": project_id})

    # Insert new files from sync
    for file_data in request.files:
        file_id = f"file_{uuid4().hex[:12]}"

        file_doc = {
            "id": file_id,
            "project_id": project_id,
            "path": file_data.path,
            "content": file_data.content,  # Code stored in MongoDB
            "url": None,
            "language": file_data.language,
            "type": "file",
            "size_bytes": len(file_data.content),
            "created_at": now,
            "updated_at": now,
        }

        db.software_lab_files.insert_one(file_doc)

    # Update project
    db.software_lab_projects.update_one(
        {"id": project_id},
        {
            "$set": {
                "name": request.metadata.name,
                "description": request.metadata.description or "",
                "file_count": len(request.files),
                "updated_at": now,
            }
        },
    )

    return SyncToCloudResponse(
        synced=True, synced_at=now.isoformat(), files_count=len(request.files)
    )


@router.get("/projects/{project_id}/snapshots", response_model=SnapshotListResponse)
async def get_snapshots(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get version history (snapshots) of project.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get snapshots
    snapshots_cursor = db.software_lab_snapshots.find({"project_id": project_id}).sort(
        "created_at", -1
    )

    snapshots = []
    for snapshot in snapshots_cursor:
        snapshots.append(
            {
                "id": snapshot["id"],
                "name": snapshot.get("name", "Unnamed snapshot"),
                "created_at": snapshot["created_at"].isoformat(),
                "files_count": len(snapshot.get("files_snapshot", [])),
            }
        )

    return SnapshotListResponse(snapshots=snapshots)


@router.post("/projects/{project_id}/snapshot", response_model=CreateSnapshotResponse)
async def create_snapshot(
    project_id: str,
    request: CreateSnapshotRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create manual snapshot (backup) of current project state.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get all current files
    files_cursor = db.software_lab_files.find({"project_id": project_id})

    files_snapshot = []
    for file_doc in files_cursor:
        files_snapshot.append(
            {
                "path": file_doc["path"],
                "content": file_doc.get("content", ""),
                "language": file_doc["language"],
            }
        )

    # Create snapshot
    snapshot_id = f"snapshot_{uuid4().hex[:12]}"
    now = datetime.utcnow()
    snapshot_name = request.name or f"Snapshot {now.strftime('%Y-%m-%d %H:%M')}"

    snapshot_doc = {
        "id": snapshot_id,
        "project_id": project_id,
        "name": snapshot_name,
        "files_snapshot": files_snapshot,
        "created_at": now,
    }

    db.software_lab_snapshots.insert_one(snapshot_doc)

    return CreateSnapshotResponse(
        id=snapshot_id,
        name=snapshot_name,
        files_count=len(files_snapshot),
        created_at=now.isoformat(),
    )


# ========================================
# GROUP 5: EXPORT/IMPORT (2 endpoints)
# ========================================


@router.get("/projects/{project_id}/export")
async def export_project(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Export project as ZIP file for download.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Verify ownership
    project = db.software_lab_projects.find_one(
        {"id": project_id, "user_id": current_user["uid"]}
    )

    if not project:
        raise HTTPException(404, "Project not found")

    # Get all files
    files_cursor = db.software_lab_files.find({"project_id": project_id})

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add project metadata
        project_meta = {
            "name": project["name"],
            "template": project["template"],
            "description": project.get("description", ""),
            "created_at": project["created_at"].isoformat(),
        }
        zip_file.writestr("project.json", json.dumps(project_meta, indent=2))

        # Add all files
        for file_doc in files_cursor:
            # Only export code files (text content)
            if file_doc.get("content"):
                zip_file.writestr(file_doc["path"], file_doc["content"])

    zip_buffer.seek(0)

    # Sanitize filename
    safe_name = "".join(
        c for c in project["name"] if c.isalnum() or c in (" ", "-", "_")
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_name}.zip"},
    )


@router.post("/projects/import", response_model=ImportProjectResponse)
async def import_project(
    file: UploadFile = File(...), current_user: dict = Depends(get_current_user)
):
    """
    Import project from ZIP file.
    """
    db_manager = DBManager()
    db = db_manager.db

    # Read ZIP file
    zip_content = await file.read()
    zip_buffer = io.BytesIO(zip_content)

    try:
        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            # Read project metadata
            project_json = json.loads(zip_file.read("project.json"))

            # Create new project
            project_id = f"proj_{uuid4().hex[:12]}"
            now = datetime.utcnow()

            project_doc = {
                "id": project_id,
                "user_id": current_user["uid"],
                "name": project_json["name"],
                "template": project_json.get("template", "custom"),
                "description": project_json.get("description", ""),
                "file_count": 0,
                "is_public": False,
                "created_at": now,
                "updated_at": now,
            }

            db.software_lab_projects.insert_one(project_doc)

            # Extract and save files
            file_count = 0

            for file_path in zip_file.namelist():
                if file_path == "project.json":
                    continue

                # Skip directories
                if file_path.endswith("/"):
                    continue

                content = zip_file.read(file_path).decode("utf-8", errors="ignore")
                language = detect_language(file_path)

                file_id = f"file_{uuid4().hex[:12]}"
                file_doc = {
                    "id": file_id,
                    "project_id": project_id,
                    "path": file_path,
                    "content": content,
                    "url": None,
                    "language": language,
                    "type": "file",
                    "size_bytes": len(content),
                    "created_at": now,
                    "updated_at": now,
                }

                db.software_lab_files.insert_one(file_doc)
                file_count += 1

            # Update project file count
            db.software_lab_projects.update_one(
                {"id": project_id}, {"$set": {"file_count": file_count}}
            )

            return ImportProjectResponse(
                id=project_id,
                name=project_doc["name"],
                files_count=file_count,
                created_at=now.isoformat(),
            )

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


# ========================================
# ADMIN: TEMPLATE MANAGEMENT (WordAI Team Only)
# ========================================


@router.post("/admin/templates", response_model=TemplateCreatedResponse)
async def create_template(
    request: CreateTemplateRequest,
    admin_user: dict = Depends(check_admin_access)
):
    """
    Admin: Create new template
    Only tienhoi.lh@gmail.com can access this endpoint
    """
    db_manager = DBManager()
    db = db_manager.db

    # Check if template ID already exists
    existing = db.software_lab_templates.find_one({"id": request.id})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Template with ID '{request.id}' already exists"
        )

    now = datetime.utcnow()
    template_doc = {
        "id": request.id,
        "name": request.name,
        "description": request.description,
        "category": request.category.value,
        "difficulty": request.difficulty.value,
        "language": request.language,
        "estimated_time_minutes": request.estimated_time_minutes,
        "thumbnail_url": request.thumbnail_url,
        "guide_steps": request.guide_steps,
        "tags": request.tags,
        "created_at": now,
        "updated_at": now
    }

    db.software_lab_templates.insert_one(template_doc)

    # Convert to response
    template_detail = TemplateDetail(
        id=template_doc["id"],
        name=template_doc["name"],
        description=template_doc["description"],
        category=template_doc["category"],
        difficulty=template_doc["difficulty"],
        language=template_doc["language"],
        estimated_time_minutes=template_doc["estimated_time_minutes"],
        thumbnail_url=template_doc.get("thumbnail_url"),
        guide_steps=template_doc["guide_steps"],
        tags=template_doc["tags"],
        files=[]
    )

    return TemplateCreatedResponse(
        message=f"Template '{request.name}' created successfully",
        template=template_detail
    )


@router.put("/admin/templates/{template_id}", response_model=TemplateCreatedResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    admin_user: dict = Depends(check_admin_access)
):
    """
    Admin: Update template metadata
    Only tienhoi.lh@gmail.com can access this endpoint
    """
    db_manager = DBManager()
    db = db_manager.db

    # Check if template exists
    template = db.software_lab_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    # Build update fields
    update_fields = {"updated_at": datetime.utcnow()}

    if request.name is not None:
        update_fields["name"] = request.name
    if request.description is not None:
        update_fields["description"] = request.description
    if request.category is not None:
        update_fields["category"] = request.category.value
    if request.difficulty is not None:
        update_fields["difficulty"] = request.difficulty.value
    if request.language is not None:
        update_fields["language"] = request.language
    if request.estimated_time_minutes is not None:
        update_fields["estimated_time_minutes"] = request.estimated_time_minutes
    if request.thumbnail_url is not None:
        update_fields["thumbnail_url"] = request.thumbnail_url
    if request.guide_steps is not None:
        update_fields["guide_steps"] = request.guide_steps
    if request.tags is not None:
        update_fields["tags"] = request.tags

    # Update template
    db.software_lab_templates.update_one(
        {"id": template_id},
        {"$set": update_fields}
    )

    # Get updated template
    updated_template = db.software_lab_templates.find_one({"id": template_id})

    # Get template files
    template_files = list(db.software_lab_template_files.find({"template_id": template_id}))
    files_list = [
        TemplateFile(
            path=f["path"],
            name=f["name"],
            type=f["type"],
            language=f["language"],
            content=f.get("content")
        )
        for f in template_files
    ]

    template_detail = TemplateDetail(
        id=updated_template["id"],
        name=updated_template["name"],
        description=updated_template["description"],
        category=updated_template["category"],
        difficulty=updated_template["difficulty"],
        language=updated_template["language"],
        estimated_time_minutes=updated_template["estimated_time_minutes"],
        thumbnail_url=updated_template.get("thumbnail_url"),
        guide_steps=updated_template["guide_steps"],
        tags=updated_template.get("tags", []),
        files=files_list
    )

    return TemplateCreatedResponse(
        message=f"Template '{template_id}' updated successfully",
        template=template_detail
    )


@router.delete("/admin/templates/{template_id}")
async def delete_template(
    template_id: str,
    admin_user: dict = Depends(check_admin_access)
):
    """
    Admin: Delete template
    Only tienhoi.lh@gmail.com can access this endpoint
    """
    db_manager = DBManager()
    db = db_manager.db

    # Check if template exists
    template = db.software_lab_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    # Delete template files first
    files_result = db.software_lab_template_files.delete_many({"template_id": template_id})

    # Delete template
    db.software_lab_templates.delete_one({"id": template_id})

    return SuccessResponse(
        message=f"Template '{template_id}' and {files_result.deleted_count} files deleted successfully"
    )


@router.post("/admin/templates/{template_id}/files", response_model=TemplateFileCreatedResponse)
async def create_template_file(
    template_id: str,
    request: CreateTemplateFileRequest,
    admin_user: dict = Depends(check_admin_access)
):
    """
    Admin: Add file to template
    Only tienhoi.lh@gmail.com can access this endpoint
    """
    db_manager = DBManager()
    db = db_manager.db

    # Check if template exists
    template = db.software_lab_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    # Check if file already exists
    existing_file = db.software_lab_template_files.find_one({
        "template_id": template_id,
        "path": request.path
    })
    if existing_file:
        raise HTTPException(
            status_code=409,
            detail=f"File '{request.path}' already exists in template '{template_id}'"
        )

    # Create file
    file_id = f"tf_{secrets.token_hex(8)}"
    now = datetime.utcnow()

    file_doc = {
        "id": file_id,
        "template_id": template_id,
        "path": request.path,
        "name": request.name,
        "type": request.type.value,
        "language": request.language,
        "content": request.content,
        "created_at": now
    }

    db.software_lab_template_files.insert_one(file_doc)

    template_file = TemplateFile(
        path=file_doc["path"],
        name=file_doc["name"],
        type=file_doc["type"],
        language=file_doc["language"],
        content=file_doc.get("content")
    )

    return TemplateFileCreatedResponse(
        message=f"File '{request.path}' added to template '{template_id}'",
        file=template_file
    )


@router.put("/admin/templates/{template_id}/files/{file_id}", response_model=TemplateFileCreatedResponse)
async def update_template_file(
    template_id: str,
    file_id: str,
    request: UpdateTemplateFileRequest,
    admin_user: dict = Depends(check_admin_access)
):
    """
    Admin: Update template file
    Only tienhoi.lh@gmail.com can access this endpoint
    """
    db_manager = DBManager()
    db = db_manager.db

    # Check if template file exists
    template_file = db.software_lab_template_files.find_one({
        "id": file_id,
        "template_id": template_id
    })
    if not template_file:
        raise HTTPException(
            status_code=404,
            detail=f"File '{file_id}' not found in template '{template_id}'"
        )

    # Build update fields
    update_fields = {}

    if request.path is not None:
        # Check if new path already exists
        existing = db.software_lab_template_files.find_one({
            "template_id": template_id,
            "path": request.path,
            "id": {"$ne": file_id}
        })
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"File with path '{request.path}' already exists"
            )
        update_fields["path"] = request.path

    if request.name is not None:
        update_fields["name"] = request.name
    if request.language is not None:
        update_fields["language"] = request.language
    if request.content is not None:
        update_fields["content"] = request.content

    # Update file
    db.software_lab_template_files.update_one(
        {"id": file_id},
        {"$set": update_fields}
    )

    # Get updated file
    updated_file = db.software_lab_template_files.find_one({"id": file_id})

    template_file_response = TemplateFile(
        path=updated_file["path"],
        name=updated_file["name"],
        type=updated_file["type"],
        language=updated_file["language"],
        content=updated_file.get("content")
    )

    return TemplateFileCreatedResponse(
        message=f"Template file updated successfully",
        file=template_file_response
    )


@router.delete("/admin/templates/{template_id}/files/{file_id}")
async def delete_template_file(
    template_id: str,
    file_id: str,
    admin_user: dict = Depends(check_admin_access)
):
    """
    Admin: Delete template file
    Only tienhoi.lh@gmail.com can access this endpoint
    """
    db_manager = DBManager()
    db = db_manager.db

    # Check if template file exists
    template_file = db.software_lab_template_files.find_one({
        "id": file_id,
        "template_id": template_id
    })
    if not template_file:
        raise HTTPException(
            status_code=404,
            detail=f"File '{file_id}' not found in template '{template_id}'"
        )

    # Delete file
    db.software_lab_template_files.delete_one({"id": file_id})

    return SuccessResponse(
        message=f"Template file '{template_file['path']}' deleted successfully"
    )
            )

    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")
    except KeyError:
        raise HTTPException(400, "Invalid project ZIP (missing project.json)")
    except Exception as e:
        raise HTTPException(500, f"Import failed: {str(e)}")
