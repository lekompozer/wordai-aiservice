"""
StudyHub Content Management Routes
APIs for linking Documents, Tests, Books to StudyHub modules
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional, List
from pydantic import BaseModel, Field

from src.services.studyhub_content_manager import StudyHubContentManager
from src.middleware.firebase_auth import get_current_user


router = APIRouter(
    prefix="/api/studyhub",
    tags=["StudyHub Content Management"],
)


# ==================== REQUEST MODELS ====================


class AddDocumentRequest(BaseModel):
    """Request to add document to module"""

    document_id: str = Field(..., description="ID from online_documents")
    title: str = Field(..., min_length=1, max_length=200)
    is_required: bool = False
    is_preview: bool = False


class UpdateContentRequest(BaseModel):
    """Request to update content settings"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    is_required: Optional[bool] = None
    is_preview: Optional[bool] = None


class AddTestRequest(BaseModel):
    """Request to add test to module"""

    test_id: str = Field(..., description="ID from online_tests")
    title: str = Field(..., min_length=1, max_length=200)
    passing_score: int = Field(70, ge=0, le=100)
    is_required: bool = False
    is_preview: bool = False


class UpdateTestRequest(BaseModel):
    """Request to update test content"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    is_required: Optional[bool] = None
    is_preview: Optional[bool] = None


class AddBookRequest(BaseModel):
    """Request to add book to module"""

    book_id: str = Field(..., description="ID from online_books")
    title: str = Field(..., min_length=1, max_length=200)
    selected_chapters: Optional[List[str]] = Field(
        None, description="Optional: specific chapters to include"
    )
    is_required: bool = False
    is_preview: bool = False


class UpdateBookRequest(BaseModel):
    """Request to update book content"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    selected_chapters: Optional[List[str]] = None
    is_required: Optional[bool] = None
    is_preview: Optional[bool] = None


class LinkExistingFileRequest(BaseModel):
    """Request to link existing file to module"""

    file_id: str = Field(..., description="ID from studyhub_files")
    title: str = Field(..., min_length=1, max_length=200)
    is_required: bool = False
    is_preview: bool = False


# ==================== DOCUMENT CONTENT APIs ====================


@router.post(
    "/modules/{module_id}/content/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Add document to module",
)
async def add_document_to_module(
    module_id: str,
    request: AddDocumentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Link document to StudyHub module**

    - Links existing document from `online_documents`
    - Sets `studyhub_context.enabled = true` on document
    - Auto-assigns order_index
    - Only subject owner can add documents

    **Permission**: Subject owner only
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.add_document_to_module(
        module_id=module_id,
        document_id=request.document_id,
        title=request.title,
        is_required=request.is_required,
        is_preview=request.is_preview,
    )

    return {
        "id": str(content["_id"]),
        "module_id": str(content["module_id"]),
        "content_type": content["content_type"],
        "title": content["title"],
        "data": content["data"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
        "order_index": content["order_index"],
    }


@router.get(
    "/modules/{module_id}/content/documents",
    summary="Get all documents in module",
)
async def get_module_documents(
    module_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    **Get all documents in module**

    - Returns list of documents with details
    - Includes document metadata from online_documents
    - Ordered by order_index

    **Permission**: Subject owner or enrolled user
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    contents = await manager.get_module_documents(module_id=module_id)

    return {
        "contents": [
            {
                "id": str(content["_id"]),
                "module_id": str(content["module_id"]),
                "title": content["title"],
                "data": content["data"],
                "is_required": content["is_required"],
                "is_preview": content["is_preview"],
                "order_index": content["order_index"],
                "document_details": content.get("document_details"),
            }
            for content in contents
        ],
        "total": len(contents),
    }


@router.put(
    "/content/documents/{content_id}",
    summary="Update document content settings",
)
async def update_document_content(
    content_id: str,
    request: UpdateContentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Update document content settings**

    - Update title, is_required, is_preview flags
    - Updates studyhub_context if preview changed
    - Only subject owner can update

    **Permission**: Subject owner only
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.update_document_content(
        content_id=content_id,
        title=request.title,
        is_required=request.is_required,
        is_preview=request.is_preview,
    )

    return {
        "id": str(content["_id"]),
        "title": content["title"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
    }


@router.delete(
    "/content/documents/{content_id}",
    summary="Remove document from module",
)
async def remove_document_from_module(
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    **Unlink document from module**

    - Removes content record from module
    - Sets `studyhub_context.enabled = false` on document
    - Document remains in online_documents (not deleted)

    **Permission**: Subject owner only
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    await manager.remove_document_from_module(content_id=content_id)

    return {"success": True, "message": "Document removed from module"}


# ==================== TEST CONTENT APIs ====================


@router.post(
    "/modules/{module_id}/content/tests",
    status_code=status.HTTP_201_CREATED,
    summary="Add test to module",
)
async def add_test_to_module(
    module_id: str,
    request: AddTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Link test to StudyHub module**

    - Links existing test from `online_tests`
    - Sets passing_score requirement
    - Only subject owner can add tests
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.add_test_to_module(
        module_id=module_id,
        test_id=request.test_id,
        title=request.title,
        passing_score=request.passing_score,
        is_required=request.is_required,
        is_preview=request.is_preview,
    )

    return {
        "id": str(content["_id"]),
        "module_id": str(content["module_id"]),
        "content_type": content["content_type"],
        "title": content["title"],
        "data": content["data"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
        "order_index": content["order_index"],
    }


@router.get(
    "/modules/{module_id}/content/tests",
    summary="Get all tests in module",
)
async def get_module_tests(
    module_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all tests in module with details"""
    manager = StudyHubContentManager(user_id=current_user["uid"])

    contents = await manager.get_module_tests(module_id=module_id)

    return {
        "contents": [
            {
                "id": str(content["_id"]),
                "module_id": str(content["module_id"]),
                "title": content["title"],
                "data": content["data"],
                "is_required": content["is_required"],
                "is_preview": content["is_preview"],
                "order_index": content["order_index"],
                "test_details": content.get("test_details"),
            }
            for content in contents
        ],
        "total": len(contents),
    }


@router.put(
    "/content/tests/{content_id}",
    summary="Update test content settings",
)
async def update_test_content(
    content_id: str,
    request: UpdateTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update test content settings including passing_score"""
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.update_test_content(
        content_id=content_id,
        title=request.title,
        passing_score=request.passing_score,
        is_required=request.is_required,
        is_preview=request.is_preview,
    )

    return {
        "id": str(content["_id"]),
        "title": content["title"],
        "data": content["data"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
    }


@router.delete(
    "/content/tests/{content_id}",
    summary="Remove test from module",
)
async def remove_test_from_module(
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Unlink test from module"""
    manager = StudyHubContentManager(user_id=current_user["uid"])

    await manager.remove_test_from_module(content_id=content_id)

    return {"success": True, "message": "Test removed from module"}


# ==================== BOOK CONTENT APIs ====================


@router.post(
    "/modules/{module_id}/content/books",
    status_code=status.HTTP_201_CREATED,
    summary="Add book to module",
)
async def add_book_to_module(
    module_id: str,
    body: dict,  # Accept raw dict to handle both wrapped and unwrapped formats
    current_user: dict = Depends(get_current_user),
):
    """
    **Link book to StudyHub module**

    - Links existing book from `online_books`
    - Optional: specify selected chapters
    - Only subject owner can add books
    """
    # Handle both unwrapped and wrapped formats
    # Unwrapped: {book_id: "...", title: "..."}
    # Wrapped: {data: {book_id: "...", title: "..."}}
    data = body.get("data", body)

    # Validate required fields
    if "book_id" not in data or "title" not in data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required fields: book_id, title",
        )

    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.add_book_to_module(
        module_id=module_id,
        book_id=data["book_id"],
        title=data["title"],
        selected_chapters=data.get("selected_chapters"),
        is_required=data.get("is_required", False),
        is_preview=data.get("is_preview", False),
    )

    return {
        "id": str(content["_id"]),
        "module_id": str(content["module_id"]),
        "content_type": content["content_type"],
        "title": content["title"],
        "data": content["data"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
        "order_index": content["order_index"],
    }


@router.get(
    "/modules/{module_id}/content/books",
    summary="Get all books in module",
)
async def get_module_books(
    module_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all books in module with details"""
    manager = StudyHubContentManager(user_id=current_user["uid"])

    contents = await manager.get_module_books(module_id=module_id)

    return {
        "contents": [
            {
                "id": str(content["_id"]),
                "module_id": str(content["module_id"]),
                "title": content["title"],
                "data": content["data"],
                "is_required": content["is_required"],
                "is_preview": content["is_preview"],
                "order_index": content["order_index"],
                "book_details": content.get("book_details"),
            }
            for content in contents
        ],
        "total": len(contents),
    }


@router.put(
    "/content/books/{content_id}",
    summary="Update book content settings",
)
async def update_book_content(
    content_id: str,
    request: UpdateBookRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update book content settings including selected chapters"""
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.update_book_content(
        content_id=content_id,
        title=request.title,
        selected_chapters=request.selected_chapters,
        is_required=request.is_required,
        is_preview=request.is_preview,
    )

    return {
        "id": str(content["_id"]),
        "title": content["title"],
        "data": content["data"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
    }


@router.delete(
    "/content/books/{content_id}",
    summary="Remove book from module",
)
async def remove_book_from_module(
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Unlink book from module"""
    manager = StudyHubContentManager(user_id=current_user["uid"])

    await manager.remove_book_from_module(content_id=content_id)

    return {"success": True, "message": "Book removed from module"}


# ==================== FILE CONTENT APIs ====================


@router.post(
    "/modules/{module_id}/content/files/existing",
    status_code=status.HTTP_201_CREATED,
    summary="Link existing file to module",
)
async def link_existing_file_to_module(
    module_id: str,
    request: LinkExistingFileRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Link existing file to StudyHub module**

    - Links file from My Files (studyhub_files collection)
    - File must belong to user
    - File cannot be already linked to this module
    - Sets `studyhub_context.enabled = true` on file

    **Permission**: Subject owner only
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.link_existing_file_to_module(
        module_id=module_id,
        file_id=request.file_id,
        title=request.title,
        is_required=request.is_required,
        is_preview=request.is_preview,
    )

    return {
        "id": str(content["_id"]),
        "module_id": str(content["module_id"]),
        "content_type": content["content_type"],
        "title": content["title"],
        "data": content["data"],
        "is_required": content["is_required"],
        "is_preview": content["is_preview"],
        "order_index": content["order_index"],
    }


@router.post(
    "/modules/{module_id}/content/files",
    status_code=status.HTTP_201_CREATED,
    summary="Upload file to module",
)
async def upload_file_to_module(
    module_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    **Upload file to StudyHub module**

    - Accepts multipart/form-data
    - Max file size: 500 MB
    - Supported: PDF, videos, audio, images, archives
    - Uploads to Cloudflare R2 storage
    - Virus scanning performed

    **Permission**: Subject owner only

    **Note**: This endpoint requires file upload implementation with multipart/form-data.
    Implementation pending - requires R2 storage integration.
    """
    raise HTTPException(
        status_code=501,
        detail="File upload not implemented yet. Please use link existing file endpoint instead.",
    )


@router.get(
    "/modules/{module_id}/content/files",
    summary="Get all files in module",
)
async def get_module_files(
    module_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    **Get all files in module**

    - Returns list of files with metadata
    - Includes file details (size, type, download count, etc.)
    - Ordered by order_index

    **Permission**: Subject owner or enrolled user
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    contents = await manager.get_module_files(module_id=module_id)

    return {
        "contents": [
            {
                "id": str(content["_id"]),
                "module_id": str(content["module_id"]),
                "title": content["title"],
                "data": content["data"],
                "is_required": content["is_required"],
                "is_preview": content["is_preview"],
                "order_index": content["order_index"],
                "file_details": content.get("file_details"),
            }
            for content in contents
        ],
        "total": len(contents),
    }


@router.delete(
    "/content/files/{content_id}",
    summary="Remove file from module",
)
async def remove_file_from_module(
    content_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    **Unlink file from module**

    - Removes content record from module
    - Marks file as `deleted = true` (soft delete)
    - File remains in storage for 30 days
    - URL still accessible until cleanup

    **Permission**: Subject owner only
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    await manager.remove_file_from_module(content_id=content_id)

    return {"success": True, "message": "File removed from module"}
