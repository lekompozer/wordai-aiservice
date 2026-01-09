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
    request: AddBookRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    **Link book to StudyHub module**

    - Links existing book from `online_books`
    - Optional: specify selected chapters
    - Only subject owner can add books
    """
    manager = StudyHubContentManager(user_id=current_user["uid"])

    content = await manager.add_book_to_module(
        module_id=module_id,
        book_id=request.book_id,
        title=request.title,
        selected_chapters=request.selected_chapters,
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
